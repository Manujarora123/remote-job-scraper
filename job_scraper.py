"""
Remote Job Scraper - Main Module
Uses APIs where available, falls back to scraping.
Designed for cron-triggered execution with JSON output for agent automation.
"""

import json
import os
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
import hashlib
from pydantic import BaseModel

# Config
CONFIG_PATH = Path(__file__).parent / "config.json"
OUTPUT_DIR = Path(__file__).parent / "output"

# Job Schema - standardized format for all sources
class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    remote: bool
    job_type: str
    source: str
    source_url: str
    description: str
    posted_date: str
    scraped_at: str
    salary: str | None = None
    apply_url: str | None = None

class JobScraper:
    """Main job scraper with source adapters."""
    
    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path) as f:
            self.config = json.load(f)
        self.jobs: List[Job] = []
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(exist_ok=True)
        self.headers = {"User-Agent": "Mozilla/5.0"}
    
    def generate_job_id(self, title: str, company: str, source_url: str) -> str:
        raw = f"{title}-{company}-{source_url}".lower().strip()
        return hashlib.md5(raw.encode()).hexdigest()[:12]
    
    def create_job(self, title: str, company: str, location: str, 
                   source_url: str, description: str = "", 
                   job_type: str = "other", salary: str = None,
                   posted_date: str = None) -> Job:
        remote = any(x in location.lower() for x in ['remote', 'work from home', 'wfh', 'india']) or \
                 location == "" or "global" in location.lower()
        
        return Job(
            id=self.generate_job_id(title, company, source_url),
            title=title,
            company=company or "Unknown",
            location=location or "Remote",
            remote=remote,
            job_type=job_type,
            source="unknown",
            source_url=source_url,
            description=description[:1000] if description else "",
            posted_date=posted_date or datetime.now().isoformat(),
            scraped_at=datetime.now().isoformat(),
            salary=salary,
            apply_url=source_url
        )
    
    def classify_job_type(self, title: str, tags: List[str] = None, description: str = "") -> str:
        title_lower = (title + " " + (description or "")).lower()
        tags_lower = " ".join(tags or []).lower()
        combined = title_lower + " " + tags_lower
        
        cs_keywords = ['customer success', 'customer support', 'customer care', 'cx', 'support', 'success manager']
        bd_keywords = ['business development', 'bd', 'sales', 'account manager', 'account executive', 'partnership', 'revenue', 'growth']
        
        if any(x in combined for x in cs_keywords):
            return "customer_success"
        elif any(x in combined for x in bd_keywords):
            return "business_development"
        else:
            return "other"
    
    async def scrape_all(self) -> List[Job]:
        tasks = []
        
        if self.config["sources"].get("remote_ok", {}).get("enabled"):
            tasks.append(self.scrape_remote_ok())
        
        if self.config["sources"].get("we_work_remotely", {}).get("enabled"):
            tasks.append(self.scrape_we_work_remotely())
        
        if self.config["sources"].get("indeed", {}).get("enabled"):
            tasks.append(self.scrape_indeed())
        
        if self.config["sources"].get("remotive", {}).get("enabled"):
            tasks.append(self.scrape_remotive())
        
        # Note: Google Alerts runs sync (Gmail API)
        if self.config["sources"].get("google_alerts", {}).get("enabled"):
            self.jobs.extend(self.scrape_google_alerts_sync())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                self.jobs.extend(result)
            elif isinstance(result, Exception):
                print(f"Error: {result}")
        
        if self.config.get("dedupe", True):
            self.jobs = self.deduplicate_jobs(self.jobs)
        
        return self.jobs
    
    async def scrape_remote_ok(self) -> List[Job]:
        """Scrape Remote OK via API - most reliable."""
        jobs = []
        
        # Tags that might have our target roles
        tags_to_try = [
            'customer-success', 'customer service', 'support', 
            'sales', 'business-development', 'account-manager',
            'account executive', 'sales-manager'
        ]
        
        seen_ids = set()
        
        for tag in tags_to_try:
            try:
                url = f"https://remoteok.com/api?tag={tag}"
                resp = requests.get(url, headers=self.headers, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # Skip legal notice (first item)
                    for job_data in data[1:]:
                        if not job_data.get('id') or not job_data.get('position'):
                            continue
                        
                        job_id = str(job_data.get('id'))
                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)
                        
                        title = job_data.get('position', '')
                        company = job_data.get('company', 'Unknown')
                        location = job_data.get('location', 'Remote')
                        source_url = job_data.get('url', job_data.get('apply_url', ''))
                        tags = job_data.get('tags', [])
                        date_posted = job_data.get('date', '')
                        
                        job_type = self.classify_job_type(title, tags)
                        
                        # Filter: only keep our target types
                        if job_type in ["customer_success", "business_development"]:
                            job = self.create_job(
                                title=title,
                                company=company,
                                location=location,
                                source_url=source_url,
                                job_type=job_type,
                                posted_date=date_posted
                            )
                            job.source = "remote_ok"
                            
                            # Add salary if available
                            if job_data.get('salary_min') or job_data.get('salary_max'):
                                job.salary = f"{job_data.get('salary_min', 0)}-{job_data.get('salary_max', 0)}"
                            
                            jobs.append(job)
                            
            except Exception as e:
                print(f"Remote OK error ({tag}): {e}")
                continue
        
        print(f"Remote OK: Found {len(jobs)} jobs")
        return jobs
    
    async def scrape_we_work_remotely(self) -> List[Job]:
        """Scrape We Work Remotely via their RSS/JSON or scraping."""
        jobs = []
        
        # WWR doesn't have a public API, scrape main categories
        category_urls = [
            "https://weworkremotely.com/categories/remote-sales-jobs",
            "https://weworkremotely.com/categories/remote-customer-service-jobs",
            "https://weworkremotely.com/categories/remote-account-manager-jobs"
        ]
        
        for url in category_urls:
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                if resp.status_code != 200:
                    continue
                    
                soup = BeautifulSoup(resp.text, "lxml")
                job_cards = soup.select("li.job")
                
                for card in job_cards[:20]:  # Limit per category
                    try:
                        title_elem = card.select_one(".title")
                        company_elem = card.select_one(".company")
                        link = card.select_one("a")
                        
                        if not (title_elem and company_elem):
                            continue
                        
                        title_text = title_elem.get_text(strip=True)
                        job_type = self.classify_job_type(title_text)
                        
                        if job_type not in ["customer_success", "business_development"]:
                            continue
                        
                        source_url = link.get("href", "") if link else ""
                        if not source_url.startswith("http"):
                            source_url = "https://weworkremotely.com" + source_url
                        
                        job = self.create_job(
                            title=title_text,
                            company=company_elem.get_text(strip=True),
                            location="Remote",
                            source_url=source_url,
                            job_type=job_type
                        )
                        job.source = "we_work_remotely"
                        jobs.append(job)
                        
                    except Exception:
                        continue
                        
            except Exception as e:
                print(f"WWR error: {e}")
                continue
        
        print(f"We Work Remotely: Found {len(jobs)} jobs")
        return jobs
    
    async def scrape_indeed(self) -> List[Job]:
        """Scrape Indeed - India remote roles."""
        jobs = []
        
        search_queries = [
            ("customer success remote India", "customer_success"),
            ("business development remote India", "business_development"),
            ("account manager remote India", "business_development"),
        ]
        
        for query, job_type in search_queries[:2]:
            try:
                params = {
                    "q": query,
                    "l": "India",
                    "remotejob": "remote",
                    "fromage": "7"  # Last 7 days
                }
                
                resp = requests.get(
                    "https://www.indeed.com/jobs",
                    params=params,
                    headers=self.headers,
                    timeout=15
                )
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    job_cards = soup.select(".jobsearch-ResultsList > li")
                    
                    for card in job_cards[:15]:
                        try:
                            title_elem = card.select_one("h2.jobTitle")
                            company_elem = card.select_one(".companyName")
                            location_elem = card.select_one(".companyLocation")
                            link = card.select_one("a")
                            
                            if not (title_elem and company_elem):
                                continue
                            
                            title_text = title_elem.get_text(strip=True)
                            source_url = "https://www.indeed.com" + link.get("href", "") if link else ""
                            
                            job = self.create_job(
                                title=title_text,
                                company=company_elem.get_text(strip=True),
                                location=location_elem.get_text(strip=True) if location_elem else "India",
                                source_url=source_url,
                                job_type=job_type
                            )
                            job.source = "indeed"
                            jobs.append(job)
                            
                        except Exception:
                            continue
                            
            except Exception as e:
                print(f"Indeed error: {e}")
                continue
        
        print(f"Indeed: Found {len(jobs)} jobs")
        return jobs
    
    async def scrape_remotive(self) -> List[Job]:
        """Scrape Remotive API."""
        jobs = []
        
        categories = self.config["sources"].get("remotive", {}).get("categories", ["sales", "customer-service", "business"])
        
        for category in categories:
            try:
                url = f"https://remotive.com/api/remote-jobs?category={category}"
                resp = requests.get(url, headers=self.headers, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    job_list = data.get("jobs", [])
                    
                    for job_data in job_list:
                        title = job_data.get("title", "")
                        company = job_data.get("company_name", "Unknown")
                        location = job_data.get("candidate_required_location", "Remote")
                        source_url = job_data.get("url", "")
                        description = job_data.get("description", "")[:500]
                        
                        job_type = self.classify_job_type(title, description=description)
                        
                        # Filter for our target types
                        if job_type in ["customer_success", "business_development"]:
                            job = self.create_job(
                                title=title,
                                company=company,
                                location=location,
                                source_url=source_url,
                                description=description,
                                job_type=job_type,
                                posted_date=job_data.get("publication_date", "")
                            )
                            job.source = "remotive"
                            
                            # Salary if available
                            if job_data.get("salary"):
                                job.salary = job_data.get("salary")
                            
                            jobs.append(job)
                            
            except Exception as e:
                print(f"Remotive error ({category}): {e}")
                continue
        
        print(f"Remotive: Found {len(jobs)} jobs")
        return jobs
    
    def scrape_google_alerts_sync(self) -> List[Job]:
        """Scrape job postings from Gmail Google Alert emails."""
        jobs = []
        seen_urls = set()
        
        GMAIL_API_URL = "http://localhost:3001"
        
        queries = [
            ("subject:Google Alert customer success", "customer_success"),
            ("subject:Google Alert business development", "business_development"),
            ("subject:Google Alert account manager", "business_development"),
            ("from:linkedin.com", "other"),
        ]
        
        for query, job_type in queries:
            try:
                resp = requests.get(f"{GMAIL_API_URL}/search-emails", params={"q": query}, timeout=30)
                result = resp.json()
                messages = result.get("messages", [])[:5]
                
                for msg in messages:
                    try:
                        email_resp = requests.get(f"{GMAIL_API_URL}/read-email", params={"id": msg["id"]}, timeout=30)
                        email_data = email_resp.json()
                        body = email_data.get("email", {}).get("body", "")
                        
                        patterns = [
                            r'linkedin\.com/comm/jobs/view/[0-9]+',
                            r'linkedin\.com/jobs/view/[0-9]+',
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, body)
                            for url in matches:
                                if url in seen_urls:
                                    continue
                                seen_urls.add(url)
                                
                                full_url = 'https://www.' + url
                                
                                job = self.create_job(
                                    title="Job Alert",
                                    company="LinkedIn",
                                    location="Remote",
                                    source_url=full_url,
                                    job_type=job_type
                                )
                                job.source = "google_alert"
                                jobs.append(job)
                                
                    except Exception:
                        continue
                        
            except Exception:
                continue
        
        print(f"Google Alerts: Found {len(jobs)} jobs")
        return jobs
    
    def deduplicate_jobs(self, jobs: List[Job]) -> List[Job]:
        seen = set()
        unique = []
        for job in jobs:
            if job.id not in seen:
                seen.add(job.id)
                unique.append(job)
        return unique
    
    def save_output(self, jobs: List[Job] = None):
        jobs = jobs or self.jobs
        
        if not jobs:
            print("No jobs to save")
            return
        
        all_jobs_file = self.output_dir / "all_jobs.json"
        with open(all_jobs_file, "w") as f:
            json.dump([j.model_dump() for j in jobs], f, indent=2)
        
        cs_jobs = [j for j in jobs if j.job_type == "customer_success"]
        bd_jobs = [j for j in jobs if j.job_type == "business_development"]
        
        if cs_jobs:
            with open(self.output_dir / "customer_success.json", "w") as f:
                json.dump([j.model_dump() for j in cs_jobs], f, indent=2)
        
        if bd_jobs:
            with open(self.output_dir / "business_development.json", "w") as f:
                json.dump([j.model_dump() for j in bd_jobs], f, indent=2)
        
        with open(self.output_dir / "last_run.json", "w") as f:
            json.dump({
                "scraped_at": datetime.now().isoformat(),
                "total_jobs": len(jobs),
                "cs_jobs": len(cs_jobs),
                "bd_jobs": len(bd_jobs)
            }, f, indent=2)
        
        print(f"Saved {len(jobs)} jobs to {self.output_dir}")
        print(f"  - Customer Success: {len(cs_jobs)}")
        print(f"  - Business Development: {len(bd_jobs)}")


async def main():
    print(f"[{datetime.now().isoformat()}] Starting job scrape...")
    
    scraper = JobScraper()
    jobs = await scraper.scrape_all()
    scraper.save_output(jobs)
    
    print(f"[{datetime.now().isoformat()}] Scrape complete!")
    return len(jobs)


if __name__ == "__main__":
    asyncio.run(main())
