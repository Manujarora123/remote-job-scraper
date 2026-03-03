"""
Google Alerts Job Scraper
Uses Gmail API to read Google Alert / LinkedIn job alert emails.
"""

import re
import json
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import requests
from bs4 import BeautifulSoup

from job_scraper import Job, JobScraper

# Try to import Playwright, fallback to Selenium
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
    SELENIUM_FALLBACK = False
except ImportError:
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
        PLAYWRIGHT_AVAILABLE = False
        SELENIUM_FALLBACK = True
        PlaywrightTimeoutError = Exception
    except ImportError:
        PLAYWRIGHT_AVAILABLE = False
        SELENIUM_FALLBACK = False
        PlaywrightTimeoutError = Exception

class GoogleAlertsScraper(JobScraper):
    """Scrape job postings from Google Alert emails via Gmail API."""
    
    GMAIL_API_URL = "http://localhost:3001"
    
    def __init__(self):
        super().__init__()
        self._last_linkedin_guest_call_ts = 0.0
    
    def _parse_linkedin_job_alert(self, subject: str, body: str) -> Tuple[str, str, str]:
        """
        Parse LinkedIn job alert email to extract job title, company, and location.
        
        Subject format: "search_term": Company - Job Title and more
        Body format:
            Your job alert for search_term in location
            New jobs match your preferences.
            
            Job Title
            Company
            Location
        
        Returns: (title, company, location)
        """
        title = ""
        company = ""
        location = ""
        
        # Try to parse from subject line: "search_term": Company - Job Title and more
        subject_pattern = r'"[^"]+"\s*:\s*(.+?)\s*-\s*(.+?)\s+and\s+more'
        subject_match = re.search(subject_pattern, subject)
        if subject_match:
            company = subject_match.group(1).strip()
            title = subject_match.group(2).strip()
        
        # Parse from body - look for pattern: Job Title\nCompany\nLocation
        # Body typically starts with "Your job alert for X in Y"
        if not location:
            # Extract location from "Your job alert for ... in X"
            location_pattern = r'Your job alert for .+ in (.+?)(?:\n|$)'
            location_match = re.search(location_pattern, body)
            if location_match:
                location = location_match.group(1).strip()
        
        # If we didn't get title from subject, extract from body
        if not title:
            lines = body.split('\n')
            # Job title is typically a few lines down, before company name
            for i, line in enumerate(lines):
                line_clean = line.strip()
                if line_clean and not line_clean.startswith('http') and i > 0:
                    # Skip "New jobs match" and other metadata
                    if ('New jobs' not in line_clean and 
                        'Your job alert' not in line_clean and
                        'View job' not in line_clean and
                        len(line_clean) > 5):
                        title = line_clean
                        # Company is next non-empty line
                        if i + 1 < len(lines) and not company:
                            next_line = lines[i + 1].strip()
                            if next_line and not next_line.startswith('http'):
                                company = next_line
                        break
        
        return title, company, location
    
    def _extract_job_details_from_email(self, subject: str, body: str, from_addr: str) -> Tuple[str, str, str]:
        """
        Extract job title, company, and location from email based on sender/format.
        """
        # LinkedIn job alerts
        if 'jobalerts-noreply@linkedin.com' in from_addr.lower():
            return self._parse_linkedin_job_alert(subject, body)
        
        # Default: return generic values
        return "Job Alert", "See URL", "Remote"
    
    def _call_gmail_api(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.GMAIL_API_URL}/{endpoint}"
        resp = requests.get(url, params=params, timeout=30)
        return resp.json()

    def _extract_linkedin_job_id(self, url_or_id: str) -> str:
        """Extract LinkedIn job ID from URL variants or numeric ID input."""
        raw = (url_or_id or "").strip()
        if raw.isdigit():
            return raw

        match = re.search(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)", raw)
        if match:
            return match.group(1)

        match = re.search(r"linkedin\.com/jobs/view/[^/?#]*-(\d+)", raw)
        if match:
            return match.group(1)

        match = re.search(r"[?&]currentJobId=(\d+)", raw)
        if match:
            return match.group(1)

        return ""

    def _scrape_linkedin_jd_public(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Fetch LinkedIn JD via jobs-guest API (no auth) with throttling/backoff."""
        if not job_id:
            return None

        # Throttle: keep >=2s between guest API calls
        now = time.time()
        gap = now - self._last_linkedin_guest_call_ts
        if gap < 2.0:
            time.sleep(2.0 - gap)

        url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            self._last_linkedin_guest_call_ts = time.time()

            if resp.status_code == 429:
                print(f"  LinkedIn guest API rate limited for job {job_id}; backing off 120s")
                time.sleep(120)
                return None
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            title_el = soup.find("h2", class_="top-card-layout__title")
            company_el = soup.find("a", class_="topcard__org-name-link")
            loc_el = soup.find("span", class_="topcard__flavor--bullet")

            criteria = []
            for item in soup.find_all("li", class_="description__job-criteria-item"):
                subheader = item.find("h3")
                value = item.find("span")
                if subheader and value:
                    criteria.append({
                        "name": subheader.get_text(strip=True),
                        "value": value.get_text(strip=True),
                    })

            description = ""
            for class_name in [
                "show-more-less-html__markup",
                "description__text",
                "decorated-job-posting__details",
            ]:
                el = soup.find("div", class_=class_name)
                if el:
                    text = el.get_text(separator="\n", strip=True)
                    if len(text) > 200:
                        description = text
                        break

            parts = []
            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            location = loc_el.get_text(strip=True) if loc_el else ""
            if title:
                parts.append(f"Job Title: {title}")
            if company:
                parts.append(f"Company: {company}")
            if location:
                parts.append(f"Location: {location}")
            if criteria:
                parts.append("")
                for c in criteria:
                    parts.append(f"{c.get('name','')}: {c.get('value','')}")
            if description:
                parts.append("")
                parts.append(description)
            raw_text = "\n".join(parts)

            # Content validation guard
            if len(raw_text) < 300:
                return None

            return {
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "criteria": criteria,
                "description": description,
                "raw_text": raw_text,
            }
        except requests.RequestException:
            return None

    def _scrape_linkedin_jd_playwright(self, linkedin_url: str) -> Optional[str]:
        """Fallback JD extraction from LinkedIn job page via Playwright."""
        if not PLAYWRIGHT_AVAILABLE:
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(12000)
                page.goto(linkedin_url, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                description = ""
                selectors = [
                    "div.show-more-less-html__markup",
                    "div.description__text",
                    "div.decorated-job-posting__details",
                ]
                for selector in selectors:
                    el = page.query_selector(selector)
                    if el:
                        text = (el.inner_text() or "").strip()
                        if len(text) > 200:
                            description = text
                            break

                browser.close()
                if len(description) >= 300:
                    return description
                return None
        except Exception:
            return None

    def _extract_linkedin_apply_url(self, linkedin_url: str) -> Optional[str]:
        """
        Visit a LinkedIn job URL using Playwright (or Selenium fallback) and extract the actual apply button URL.
        
        Returns the apply URL if found, None if:
        - Easy Apply is not enabled
        - Page cannot be accessed
        - Apply button is not found
        - Browser automation is not available
        """
        if PLAYWRIGHT_AVAILABLE:
            return self._extract_linkedin_apply_url_playwright(linkedin_url)
        elif SELENIUM_FALLBACK:
            return self._extract_linkedin_apply_url_selenium(linkedin_url)
        else:
            print(f"  Browser automation not available, skipping apply URL extraction")
            return None
    
    def _extract_linkedin_apply_url_playwright(self, linkedin_url: str) -> Optional[str]:
        """Extract apply URL using Playwright."""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Set timeout for page operations
                page.set_default_timeout(10000)
                
                # Navigate to LinkedIn job page
                page.goto(linkedin_url, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)  # Wait for dynamic content to load
                
                # Try to find the apply button and extract URL
                apply_url = None
                
                # Method 1: Look for Easy Apply button
                try:
                    easy_apply_button = page.locator('button:has-text("Easy Apply")').first
                    if easy_apply_button:
                        # Try to click and see if it navigates or opens a modal
                        easy_apply_button.click()
                        page.wait_for_timeout(1000)
                        apply_url = page.url
                except:
                    pass
                
                # Method 2: Look for direct apply link in job details
                if not apply_url:
                    try:
                        # Look for apply button/link in various forms
                        apply_selectors = [
                            'a:has-text("Apply now")',
                            'button:has-text("Apply")',
                            'a[href*="apply"]',
                        ]
                        
                        for selector in apply_selectors:
                            try:
                                element = page.locator(selector).first
                                if element:
                                    href = element.get_attribute("href")
                                    if href:
                                        apply_url = href
                                        break
                            except:
                                continue
                    except:
                        pass
                
                # Method 3: Check for external ATS redirect (Greenhouse, Lever, etc.)
                if not apply_url:
                    try:
                        # Look for iframe or redirect to external ATS
                        iframes = page.locator("iframe").count()
                        if iframes > 0:
                            # Try to get frame src
                            for i in range(iframes):
                                frame = page.locator("iframe").nth(i)
                                src = frame.get_attribute("src")
                                if src and any(x in src for x in ["greenhouse", "lever", "workable"]):
                                    apply_url = src
                                    break
                    except:
                        pass
                
                browser.close()
                
                # If we got a relative URL, make it absolute
                if apply_url and not apply_url.startswith("http"):
                    if apply_url.startswith("/"):
                        apply_url = "https://www.linkedin.com" + apply_url
                    else:
                        apply_url = "https://www.linkedin.com/" + apply_url
                
                return apply_url
        
        except PlaywrightTimeoutError:
            print(f"  Timeout visiting: {linkedin_url}")
            return None
        except Exception as e:
            print(f"  Error visiting {linkedin_url}: {str(e)[:100]}")
            return None
    
    def _extract_linkedin_apply_url_selenium(self, linkedin_url: str) -> Optional[str]:
        """Extract apply URL using Selenium (fallback)."""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            driver = webdriver.Chrome(options=options)
            driver.get(linkedin_url)
            
            apply_url = None
            
            # Wait for page to load
            import time
            time.sleep(3)
            
            # Method 1: Look for Easy Apply button
            try:
                easy_apply = driver.find_element(By.XPATH, "//button[contains(text(), 'Easy Apply')]")
                if easy_apply:
                    # Click to see if it opens a form
                    easy_apply.click()
                    time.sleep(1)
                    apply_url = driver.current_url
            except:
                pass
            
            # Method 2: Look for external apply links
            if not apply_url:
                try:
                    apply_links = driver.find_elements(By.XPATH, "//a[contains(text(), 'Apply')]")
                    for link in apply_links:
                        href = link.get_attribute("href")
                        if href and href != "#":
                            apply_url = href
                            break
                except:
                    pass
            
            driver.quit()
            return apply_url
            
        except Exception as e:
            print(f"  Selenium error: {str(e)[:80]}")
            try:
                driver.quit()
            except:
                pass
            return None
    
    def scrape_google_alerts(self) -> List[Job]:
        jobs = []
        seen_urls = set()
        
        # Search for job-related emails (LinkedIn job alerts)
        queries = [
            ("from:jobalerts-noreply@linkedin.com", "other"),
            ("from:linkedin.com subject:job", "other"),
        ]
        
        for query, job_type in queries:
            try:
                result = self._call_gmail_api("search-emails", {"q": query})
                messages = result.get("messages", [])[:10]
                
                print(f"Google Alerts: '{query[:40]}...' -> {len(messages)} emails")
                
                for msg in messages:
                    try:
                        email_data = self._call_gmail_api("read-email", {"id": msg["id"]})
                        email = email_data.get("email", {})
                        body = email.get("body", "")
                        subject = email.get("subject", "")
                        from_addr = email.get("from", "")
                        
                        # Extract job URLs from email body
                        url_patterns = [
                            r'linkedin\.com/comm/jobs/view/[0-9]+',
                            r'linkedin\.com/jobs/view/[0-9]+',
                            r'View job: (https?://[^\s]+)',
                            r'https?://[^\s]*indeed\.com[^\s]*',
                            r'https?://[^\s]*naukri\.com[^\s]*',
                        ]
                        
                        # Extract job details from email
                        title, company, location = self._extract_job_details_from_email(
                            subject, body, from_addr
                        )
                        
                        for pattern in url_patterns:
                            matches = re.findall(pattern, body)
                            for url in matches:
                                if url in seen_urls:
                                    continue
                                seen_urls.add(url)
                                
                                # Build full URL if needed
                                if not url.startswith('http'):
                                    url = 'https://www.' + url
                                
                                # Classify job type based on title
                                classified_job_type = self.classify_job_type(title)
                                
                                job = self.create_job(
                                    title=title or "Job Alert",
                                    company=company or "LinkedIn",
                                    location=location or "Remote",
                                    source_url=url,
                                    job_type=classified_job_type
                                )
                                job.source = "google_alert"
                                
                                # For LinkedIn jobs, enrich via public jobs-guest API (no auth)
                                if "linkedin.com" in url.lower():
                                    job_id = self._extract_linkedin_job_id(url)
                                    if job_id:
                                        jd = self._scrape_linkedin_jd_public(job_id)
                                        if jd:
                                            if jd.get("title"):
                                                job.title = jd["title"]
                                            if jd.get("company"):
                                                job.company = jd["company"]
                                            if jd.get("location"):
                                                job.location = jd["location"]

                                            criteria = jd.get("criteria") or []
                                            criteria_text = "\n".join(
                                                f"{c['name']}: {c['value']}" for c in criteria if c.get("name") and c.get("value")
                                            )
                                            description = jd.get("description") or ""
                                            if criteria_text and description:
                                                job.description = f"{criteria_text}\n\n{description}"[:1000]
                                            elif description:
                                                job.description = description[:1000]
                                            elif criteria_text:
                                                job.description = criteria_text[:1000]
                                        else:
                                            # Fallback for expired/region-locked/short guest responses
                                            fallback_desc = self._scrape_linkedin_jd_playwright(url)
                                            if fallback_desc:
                                                job.description = fallback_desc[:1000]

                                        job.apply_url = url

                                jobs.append(job)
                                
                    except Exception as e:
                        continue
                        
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        print(f"Google Alerts: Found {len(jobs)} jobs")
        return jobs


def main():
    print(f"[{datetime.now().isoformat()}] Testing Google Alerts scraper...")
    
    scraper = GoogleAlertsScraper()
    jobs = scraper.scrape_google_alerts()
    
    print(f"\nFound {len(jobs)} jobs")
    for job in jobs[:10]:
        print(f"  {job.source_url[:80]}")


if __name__ == "__main__":
    main()
