"""
Google Alerts Job Scraper
Uses Gmail API to read Google Alert / LinkedIn job alert emails.
"""

import re
import json
from datetime import datetime
from typing import List
import requests

from job_scraper import Job, JobScraper

class GoogleAlertsScraper(JobScraper):
    """Scrape job postings from Google Alert emails via Gmail API."""
    
    GMAIL_API_URL = "http://localhost:3001"
    
    def __init__(self):
        super().__init__()
    
    def _call_gmail_api(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.GMAIL_API_URL}/{endpoint}"
        resp = requests.get(url, params=params, timeout=30)
        return resp.json()
    
    def scrape_google_alerts(self) -> List[Job]:
        jobs = []
        seen_urls = set()
        
        # Search for job-related emails
        queries = [
            ("subject:Google Alert customer success", "customer_success"),
            ("subject:Google Alert business development", "business_development"),
            ("subject:Google Alert account manager", "business_development"),
            ("from:linkedin.com", "other"),
        ]
        
        for query, job_type in queries:
            try:
                result = self._call_gmail_api("search-emails", {"q": query})
                messages = result.get("messages", [])[:5]
                
                print(f"Google Alerts: '{query[:30]}...' -> {len(messages)} emails")
                
                for msg in messages:
                    try:
                        email_data = self._call_gmail_api("read-email", {"id": msg["id"]})
                        email = email_data.get("email", {})
                        body = email.get("body", "")
                        subject = email.get("subject", "")
                        
                        # Extract job URLs
                        url_patterns = [
                            r'linkedin\.com/comm/jobs/view/[0-9]+',
                            r'linkedin\.com/jobs/view/[0-9]+',
                            r'View job: (https?://[^\s]+)',
                            r'https?://[^\s]*indeed\.com[^\s]*',
                            r'https?://[^\s]*naukri\.com[^\s]*',
                        ]
                        
                        for pattern in url_patterns:
                            matches = re.findall(pattern, body)
                            for url in matches:
                                if url in seen_urls:
                                    continue
                                seen_urls.add(url)
                                
                                # Build full URL if needed
                                if not url.startswith('http'):
                                    url = 'https://www.' + url
                                
                                job = self.create_job(
                                    title="Job Alert",
                                    company="See URL",
                                    location="Remote",
                                    source_url=url,
                                    job_type=job_type
                                )
                                job.source = "google_alert"
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
