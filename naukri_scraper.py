"""
Naukri Scraper using undetected-chromedriver
Bypasses bot detection for reliable scraping.
"""

import time
from datetime import datetime
from typing import List

import undetected_chromedriver as uc

from job_scraper import Job, JobScraper

class NaukriScraper(JobScraper):
    """Naukri job scraper using undetected-chromedriver."""
    
    def __init__(self):
        super().__init__()
        self.driver = None
    
    def _init_driver(self):
        """Initialize undetected Chrome."""
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        self.driver = uc.Chrome(options=options, version_main=None)
        return self.driver
    
    def scrape_naukri(self) -> List[Job]:
        """Scrape Naukri for CS and BD jobs."""
        jobs = []
        
        search_queries = [
            ("customer success manager", "customer_success"),
            ("business development manager", "business_development"),
            ("account manager", "business_development"),
        ]
        
        try:
            driver = self._init_driver()
            
            for query, job_type in search_queries:
                try:
                    # Build search URL
                    search_url = f"https://www.naukri.com/{query.replace(' ', '-')}-jobs-in-india"
                    
                    print(f"Naukri: Searching for '{query}'...")
                    driver.get(search_url)
                    
                    # Wait for page to load
                    time.sleep(5)
                    
                    # Get page source for debugging
                    page_source = driver.page_source
                    
                    # Find job cards
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(page_source, "lxml")
                    
                    # Try multiple selectors
                    job_cards = soup.select("article.jobTuple") or soup.select(".job-card") or soup.select(".tuple")
                    
                    print(f"  Found {len(job_cards)} cards")
                    
                    for card in job_cards[:12]:
                        try:
                            # Extract job details
                            title_elem = card.select_one(".title, .jobTitle, a.title")
                            title = title_elem.text.strip() if title_elem else "Unknown"
                            
                            company_elem = card.select_one(".companyInfo .title, .company, .subTitle")
                            company = company_elem.text.strip() if company_elem else "Unknown"
                            
                            location_elem = card.select_one(".location, .location-truncate")
                            location = location_elem.text.strip() if location_elem else "India"
                            
                            link_elem = card.select_one("a.title")
                            source_url = link_elem.get("href", "") if link_elem else ""
                            
                            if source_url and not source_url.startswith("http"):
                                source_url = "https://www.naukri.com" + source_url
                            
                            if not source_url:
                                continue
                            
                            # Create job
                            job = self.create_job(
                                title=title,
                                company=company,
                                location=location,
                                source_url=source_url,
                                job_type=job_type
                            )
                            job.source = "naukri"
                            job.remote = "remote" in location.lower()
                            jobs.append(job)
                            
                        except Exception as e:
                            continue
                    
                except Exception as e:
                    print(f"  Error: {e}")
                    continue
            
        except Exception as e:
            print(f"Naukri fatal error: {e}")
        
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
        
        print(f"Naukri: Found {len(jobs)} jobs")
        return jobs


def main():
    """Test Naukri scraper."""
    print(f"[{datetime.now().isoformat()}] Testing Naukri scraper...")
    
    scraper = NaukriScraper()
    jobs = scraper.scrape_naukri()
    
    print(f"\nFound {len(jobs)} jobs from Naukri")
    for job in jobs[:5]:
        print(f"  - {job.title} @ {job.company} ({job.location})")
    
    return jobs


if __name__ == "__main__":
    main()
