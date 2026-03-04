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
import dataclasses
import json
import os
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


@dataclasses.dataclass
class ResolverConfig:
    li_at: Optional[str] = None
    jsessionid: Optional[str] = None
    storage_state: Optional[str] = None
    headful: bool = False
    delay_ms: int = 2000
    timeout_s: int = 15


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


def _normalize_apply_result(mode: str, url: Optional[str], resolver: str) -> Dict[str, Any]:
    return {
        "application_mode": mode,
        "application_url": url,
        "ats_vendor": detect_ats_vendor(url or "") if mode == "external" else None,
        "resolver": resolver,
    }


def _extract_best_external_link(html: str) -> Optional[str]:
    # Strong signal: LinkedIn guest offsite apply CTA
    m = re.search(
        r'<a[^>]+data-tracking-control-name="public_jobs_apply-link-offsite_sign-up-modal"[^>]+href="([^"]+)"',
        html,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1)

    # Any outbound non-linkedin URL
    urls = re.findall(r'https?://[^"\'\s<>]+', html)
    for u in urls:
        if "linkedin.com" not in u.lower():
            return u
    return None


def resolve_via_voyager(job_id: str, li_at: str, jsessionid: str, timeout_s: int = 15) -> Dict[str, Any]:
    csrf = jsessionid.strip('"')
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "csrf-token": csrf,
        "x-restli-protocol-version": "2.0.0",
        "Cookie": f"li_at={li_at}; JSESSIONID=\"{csrf}\"",
    }

    url = f"https://www.linkedin.com/voyager/api/jobs/jobPostings/{job_id}"
    try:
        r = requests.get(url, headers=headers, timeout=timeout_s)
    except requests.RequestException as e:
        return {"error": f"voyager_request_error:{e.__class__.__name__}"}

    if r.status_code in (401, 403, 429):
        return {"error": f"voyager_http_{r.status_code}"}
    if r.status_code != 200:
        return {"error": f"voyager_http_{r.status_code}"}

    try:
        data = r.json()
    except Exception:
        return {"error": "voyager_invalid_json"}

    text = json.dumps(data).lower()

    # Look for external company URL first
    possible_urls = re.findall(r'https?://[^"\'\s<>]+', json.dumps(data))
    external = next((u for u in possible_urls if "linkedin.com" not in u.lower()), None)
    if external:
        return _normalize_apply_result("external", external, "voyager_api")

    # Easy apply hints when no external URL
    if "easy apply" in text or "easyapply" in text or "inapply" in text:
        return _normalize_apply_result("easy_apply", f"https://www.linkedin.com/jobs/view/{job_id}", "voyager_api")

    return {
        "application_mode": "unknown",
        "application_url": f"https://www.linkedin.com/jobs/view/{job_id}",
        "ats_vendor": None,
        "resolver": "voyager_api",
    }


def resolve_via_authenticated_playwright(
    linkedin_url: str,
    storage_state: str,
    headful: bool = False,
    timeout_s: int = 15,
) -> Dict[str, Any]:
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "playwright_unavailable"}
    if not Path(storage_state).exists():
        return {"error": "storage_state_missing"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context(storage_state=storage_state)
        page = context.new_page()
        page.set_default_timeout(timeout_s * 1000)

        try:
            page.goto(linkedin_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)

            if page.locator("button:has-text('Easy Apply')").count() > 0:
                return _normalize_apply_result("easy_apply", linkedin_url, "playwright_auth")

            selectors = [
                "a:has-text('Apply')",
                "a:has-text('Apply now')",
                "a[data-tracking-control-name='public_jobs_apply-link-offsite_sign-up-modal']",
                "a[href*='greenhouse']",
                "a[href*='lever.co']",
                "a[href*='workday']",
                "a[href*='ashbyhq']",
                "a[href*='smartrecruiters']",
            ]
            for sel in selectors:
                loc = page.locator(sel)
                if loc.count() > 0:
                    href = loc.first.get_attribute("href")
                    if href and "linkedin.com" not in href.lower():
                        return _normalize_apply_result("external", href, "playwright_auth")

            return {
                "application_mode": "unknown",
                "application_url": linkedin_url,
                "ats_vendor": None,
                "resolver": "playwright_auth",
            }
        finally:
            context.close()
            browser.close()


def resolve_from_guest(job_id: str, timeout_s: int = 15) -> Dict[str, Any]:
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
    try:
        r = requests.get(url, headers=headers, timeout=timeout_s)
    except requests.RequestException as e:
        return {"error": f"guest_request_error:{e.__class__.__name__}"}

    if r.status_code == 429:
        return {"error": "rate_limited"}
    if r.status_code != 200:
        return {"error": f"http_{r.status_code}"}

    html = r.text

    if "Easy Apply" in html:
        return _normalize_apply_result("easy_apply", f"https://www.linkedin.com/jobs/view/{job_id}", "guest_api_v2")

    ext = _extract_best_external_link(html)
    if ext:
        return _normalize_apply_result("external", ext, "guest_api_v2")

    return {
        "application_mode": "unknown",
        "application_url": f"https://www.linkedin.com/jobs/view/{job_id}",
        "ats_vendor": None,
        "resolver": "guest_api_v2",
    }


def resolve_passthrough(job: Dict[str, Any]) -> Dict[str, Any]:
    src_url = (job.get("source_url") or "").strip()
    apply_url = (job.get("apply_url") or "").strip()
    mode = "external" if apply_url else "unknown"
    final_url = apply_url or src_url
    return {
        "application_mode": mode,
        "application_url": final_url,
        "ats_vendor": detect_ats_vendor(final_url),
        "resolver": "passthrough",
    }


def resolve_job_apply(job: Dict[str, Any], cfg: ResolverConfig) -> Dict[str, Any]:
    src_url = (job.get("source_url") or "").strip()
    if "linkedin.com" not in src_url.lower():
        return resolve_passthrough(job)

    job_id = extract_job_id(src_url)
    if not job_id:
        return {
            "application_mode": "unknown",
            "application_url": src_url,
            "ats_vendor": None,
            "resolver": "id_parse_failed",
        }

    # Tier 1: Voyager API with authenticated cookies
    if cfg.li_at and cfg.jsessionid:
        out = resolve_via_voyager(job_id, cfg.li_at, cfg.jsessionid, cfg.timeout_s)
        if not out.get("error") and out.get("application_mode") != "unknown":
            return out

    # Tier 2: Authenticated Playwright with storage state
    if cfg.storage_state:
        out = resolve_via_authenticated_playwright(src_url, cfg.storage_state, cfg.headful, cfg.timeout_s)
        if not out.get("error") and out.get("application_mode") != "unknown":
            return out

    # Tier 3: Guest resolver heuristics
    out = resolve_from_guest(job_id, cfg.timeout_s)
    if not out.get("error") and out.get("application_mode") != "unknown":
        return out

    # Tier 4: Passthrough fallback
    return resolve_passthrough(job)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="output/all_jobs.json")
    ap.add_argument("--output", default="output/apply_resolution.json")
    ap.add_argument("--output-jobs", default="output/all_jobs_resolved.json")
    ap.add_argument("--limit", type=int, default=0)

    ap.add_argument("--linkedin-li-at", default=os.environ.get("LI_AT"))
    ap.add_argument("--linkedin-jsessionid", default=os.environ.get("JSESSIONID"))
    ap.add_argument("--storage-state", default=None)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--delay-ms", type=int, default=2000)
    ap.add_argument("--timeout-s", type=int, default=15)

    args = ap.parse_args()

    cfg = ResolverConfig(
        li_at=args.linkedin_li_at,
        jsessionid=args.linkedin_jsessionid,
        storage_state=args.storage_state,
        headful=args.headful,
        delay_ms=args.delay_ms,
        timeout_s=args.timeout_s,
    )

    in_path = Path(args.input)
    jobs = json.loads(in_path.read_text(encoding="utf-8"))
    if args.limit and args.limit > 0:
        jobs = jobs[: args.limit]

    rows = []
    mode_counts: Dict[str, int] = {"easy_apply": 0, "external": 0, "unknown": 0}
    resolver_counts: Dict[str, int] = {}

    for i, job in enumerate(jobs, 1):
        resolved = resolve_job_apply(job, cfg)
        mode = resolved.get("application_mode", "unknown")
        resolver = resolved.get("resolver", "unknown")

        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        resolver_counts[resolver] = resolver_counts.get(resolver, 0) + 1

        job["application_mode"] = mode
        job["application_url"] = resolved.get("application_url")
        job["ats_vendor"] = resolved.get("ats_vendor")
        job["apply_resolver"] = resolver

        rows.append(
            {
                "id": job.get("id"),
                "title": job.get("title"),
                "company": job.get("company"),
                "source_url": job.get("source_url"),
                "application_mode": mode,
                "application_url": job.get("application_url"),
                "ats_vendor": job.get("ats_vendor"),
                "resolver": resolver,
            }
        )

        print(f"[{i}/{len(jobs)}] {job.get('company', '')} - {mode} ({resolver})")
        time.sleep(cfg.delay_ms / 1000)

    payload = {"summary": mode_counts, "resolver_summary": resolver_counts, "rows": rows}
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    Path(args.output_jobs).write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    print("Done:")
    print(json.dumps(payload["summary"], indent=2))
    print("Resolver summary:")
    print(json.dumps(payload["resolver_summary"], indent=2))
    print(f"Wrote: {args.output}")
    print(f"Wrote: {args.output_jobs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
