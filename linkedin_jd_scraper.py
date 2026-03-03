"""
linkedin_jd_scraper.py
Standalone LinkedIn JD scraper using public jobs-guest API.

Usage:
  python linkedin_jd_scraper.py <linkedin_job_url_or_id>
"""

import re
import sys
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup


def extract_linkedin_job_id(url_or_id: str) -> str:
    raw = (url_or_id or "").strip()
    if raw.isdigit():
        return raw

    patterns = [
        r"linkedin\.com/(?:comm/)?jobs/view/(\d+)",
        r"linkedin\.com/jobs/view/[^/?#]*-(\d+)",
        r"[?&]currentJobId=(\d+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw)
        if m:
            return m.group(1)
    return ""


def scrape_linkedin_jd(job_id: str) -> dict:
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

    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 429:
        raise RuntimeError("LinkedIn rate limited (HTTP 429). Retry later.")
    if resp.status_code != 200:
        raise RuntimeError(f"LinkedIn API returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.find("h2", class_="top-card-layout__title")
    company_el = soup.find("a", class_="topcard__org-name-link")
    loc_el = soup.find("span", class_="topcard__flavor--bullet")

    title = title_el.get_text(strip=True) if title_el else ""
    company = company_el.get_text(strip=True) if company_el else ""
    location = loc_el.get_text(strip=True) if loc_el else ""

    criteria = {}
    for item in soup.find_all("li", class_="description__job-criteria-item"):
        subheader = item.find("h3")
        value = item.find("span")
        if subheader and value:
            criteria[subheader.get_text(strip=True)] = value.get_text(strip=True)

    desc_text = ""
    for selector in [
        {"class_": "show-more-less-html__markup"},
        {"class_": "description__text"},
        {"class_": "decorated-job-posting__details"},
    ]:
        el = soup.find("div", **selector)
        if el:
            desc_text = el.get_text(separator="\n", strip=True)
            if len(desc_text) > 200:
                break

    parts = []
    if title:
        parts.append(f"Job Title: {title}")
    if company:
        parts.append(f"Company: {company}")
    if location:
        parts.append(f"Location: {location}")
    if criteria:
        parts.append("")
        for k, v in criteria.items():
            parts.append(f"{k}: {v}")
    if desc_text:
        parts.append("")
        parts.append(desc_text)

    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "criteria": criteria,
        "description": desc_text,
        "raw_text": "\n".join(parts),
    }


CACHE_DIR = Path("scraped-jds")
CACHE_DIR.mkdir(exist_ok=True)


def get_cached_or_scrape(job_id: str) -> str:
    cache_file = CACHE_DIR / f"linkedin_{job_id}.txt"
    if cache_file.exists():
        cached = cache_file.read_text(encoding="utf-8")
        if len(cached) > 300:
            return cached

    result = scrape_linkedin_jd(job_id)
    text = result.get("raw_text", "")
    if text and len(text) > 300:
        cache_file.write_text(text[:10000], encoding="utf-8")
    return text


def batch_scrape(job_ids: list[str], sleep_seconds: int = 2):
    for job_id in job_ids:
        try:
            result = scrape_linkedin_jd(job_id)
            print(f"OK: {result.get('title','')} at {result.get('company','')} ({len(result.get('description',''))} chars)")
        except RuntimeError as e:
            print(f"FAIL: {job_id} - {e}")
        time.sleep(sleep_seconds)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python linkedin_jd_scraper.py <linkedin_job_url_or_id>")
        print("  e.g. python linkedin_jd_scraper.py 4375690866")
        return 1

    input_val = sys.argv[1]
    job_id = extract_linkedin_job_id(input_val)
    if not job_id:
        print(f"ERROR: Could not extract a LinkedIn job ID from: {input_val}")
        return 1

    print(f"Fetching JD for LinkedIn job ID: {job_id}")
    print("-" * 60)

    try:
        result = scrape_linkedin_jd(job_id)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 1

    if not result.get("raw_text") or len(result.get("raw_text", "")) < 100:
        print("WARNING: Got very little content. The job may be expired or delisted.")

    print(f"Title: {result.get('title','')}")
    print(f"Company: {result.get('company','')}")
    print(f"Location: {result.get('location','')}")
    print(f"Criteria: {result.get('criteria',{})}")
    print(f"Description: {len(result.get('description',''))} chars")
    print("-" * 60)
    print(result.get("raw_text", "")[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
