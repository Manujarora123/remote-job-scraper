"""
Resolve LinkedIn application path for scraped jobs.

Outputs per-job application routing metadata:
- application_mode: easy_apply | external | unknown
- application_url: best known apply URL
- ats_vendor: greenhouse | lever | workable | ashby | workday | smartrecruiters | icims | taleo | unknown

Usage:
  python resolve_apply_paths.py
  python resolve_apply_paths.py --input output/all_jobs.json --limit 30
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False


def detect_ats_vendor(url: str) -> Optional[str]:
    if not url:
        return None
    u = url.lower()
    checks = {
        "greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
        "lever": ["lever.co", "jobs.lever.co"],
        "workable": ["workable.com"],
        "ashby": ["ashbyhq.com", "jobs.ashbyhq.com"],
        "workday": ["myworkdayjobs.com", "workday.com"],
        "smartrecruiters": ["smartrecruiters.com"],
        "icims": ["icims.com"],
        "taleo": ["taleo.net"],
    }
    for vendor, needles in checks.items():
        if any(n in u for n in needles):
            return vendor
    try:
        host = urlparse(url).netloc
        return host or "unknown"
    except Exception:
        return "unknown"


def extract_job_id(linkedin_url: str) -> str:
    m = re.search(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)", linkedin_url)
    if m:
        return m.group(1)
    m = re.search(r"linkedin\.com/jobs/view/[^/?#]*-(\d+)", linkedin_url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]currentJobId=(\d+)", linkedin_url)
    if m:
        return m.group(1)
    return ""


def resolve_from_guest(job_id: str) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 429:
        return {"error": "rate_limited"}
    if r.status_code != 200:
        return {"error": f"http_{r.status_code}"}

    html = r.text

    # Heuristic: if Easy Apply button text appears in rendered snippet
    if "Easy Apply" in html:
        return {
            "application_mode": "easy_apply",
            "application_url": f"https://www.linkedin.com/jobs/view/{job_id}",
            "ats_vendor": None,
            "resolver": "guest_api",
        }

    # Try to find external URL in HTML
    m = re.search(r'https?://[^"\'\s<>]+', html)
    if m:
        ext = m.group(0)
        if "linkedin.com" not in ext.lower():
            return {
                "application_mode": "external",
                "application_url": ext,
                "ats_vendor": detect_ats_vendor(ext),
                "resolver": "guest_api",
            }

    return {
        "application_mode": "unknown",
        "application_url": f"https://www.linkedin.com/jobs/view/{job_id}",
        "ats_vendor": None,
        "resolver": "guest_api",
    }


def resolve_with_playwright(linkedin_url: str) -> Dict[str, Any]:
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "playwright_unavailable"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(12000)
        page.goto(linkedin_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Easy Apply signal
        if page.locator("button:has-text('Easy Apply')").count() > 0:
            browser.close()
            return {
                "application_mode": "easy_apply",
                "application_url": linkedin_url,
                "ats_vendor": None,
                "resolver": "playwright",
            }

        # External apply links
        selectors = [
            "a:has-text('Apply')",
            "a:has-text('Apply now')",
            "a[href*='greenhouse']",
            "a[href*='lever.co']",
            "a[href*='workday']",
        ]
        for sel in selectors:
            loc = page.locator(sel)
            if loc.count() > 0:
                href = loc.first.get_attribute("href")
                if href and "linkedin.com" not in href.lower():
                    browser.close()
                    return {
                        "application_mode": "external",
                        "application_url": href,
                        "ats_vendor": detect_ats_vendor(href),
                        "resolver": "playwright",
                    }

        browser.close()
    return {
        "application_mode": "unknown",
        "application_url": linkedin_url,
        "ats_vendor": None,
        "resolver": "playwright",
    }


def resolve_job_apply(job: Dict[str, Any]) -> Dict[str, Any]:
    src_url = (job.get("source_url") or "").strip()
    if "linkedin.com" not in src_url.lower():
        return {
            "application_mode": "external" if job.get("apply_url") else "unknown",
            "application_url": job.get("apply_url") or src_url,
            "ats_vendor": detect_ats_vendor(job.get("apply_url") or src_url),
            "resolver": "passthrough",
        }

    job_id = extract_job_id(src_url)
    if not job_id:
        return {
            "application_mode": "unknown",
            "application_url": src_url,
            "ats_vendor": None,
            "resolver": "id_parse_failed",
        }

    out = resolve_from_guest(job_id)
    if out.get("error") in {"rate_limited", "http_403", "http_404"} or out.get("application_mode") == "unknown":
        pw = resolve_with_playwright(src_url)
        if not pw.get("error") and pw.get("application_mode") != "unknown":
            out = pw
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="output/all_jobs.json")
    ap.add_argument("--output", default="output/apply_resolution.json")
    ap.add_argument("--output-jobs", default="output/all_jobs_resolved.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    in_path = Path(args.input)
    jobs = json.loads(in_path.read_text(encoding="utf-8"))
    if args.limit and args.limit > 0:
        jobs = jobs[: args.limit]

    rows = []
    mode_counts: Dict[str, int] = {"easy_apply": 0, "external": 0, "unknown": 0}

    for i, job in enumerate(jobs, 1):
        resolved = resolve_job_apply(job)
        mode = resolved.get("application_mode", "unknown")
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

        job["application_mode"] = mode
        job["application_url"] = resolved.get("application_url")
        job["ats_vendor"] = resolved.get("ats_vendor")
        job["apply_resolver"] = resolved.get("resolver")

        rows.append({
            "id": job.get("id"),
            "title": job.get("title"),
            "company": job.get("company"),
            "source_url": job.get("source_url"),
            "application_mode": mode,
            "application_url": job.get("application_url"),
            "ats_vendor": job.get("ats_vendor"),
            "resolver": job.get("apply_resolver"),
        })

        print(f"[{i}/{len(jobs)}] {job.get('company','')} - {mode}")
        time.sleep(2)

    Path(args.output).write_text(json.dumps({"summary": mode_counts, "rows": rows}, indent=2), encoding="utf-8")
    Path(args.output_jobs).write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    print("Done:")
    print(json.dumps(mode_counts, indent=2))
    print(f"Wrote: {args.output}")
    print(f"Wrote: {args.output_jobs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
