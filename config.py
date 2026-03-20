"""
Configuration for remote job scraper.
Tuned for Surbhi's profile: Customer Success, Business Development,
Operations Manager — India remote roles, 8+ years experience.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Search Queries ──────────────────────────────────────────────
# Each source adapter maps these to its own query syntax
SEARCH_QUERIES = [
    "Customer Success Manager remote India",
    "Business Development Manager remote India",
    "Program Delivery Manager remote India",
    "Operations Manager remote India",
    "Client Success Manager remote India",
    "Account Manager remote India",
    "Customer Experience Manager remote India",
]

# Keywords to match in titles (case-insensitive OR match)
TITLE_KEYWORDS = [
    "customer success",
    "business development",
    "program delivery",
    "operations manager",
    "client success",
    "account manager",
    "customer experience",
    "partnership",
    "client relationship",
    "key account",
]

# ── Filters ─────────────────────────────────────────────────────
LOCATION_FILTERS = ["india", "remote", "delhi", "ncr", "work from home", "wfh"]
MIN_EXPERIENCE_YEARS = 5
MAX_EXPERIENCE_YEARS = 15
SALARY_MIN_LPA = 12  # ₹12 LPA floor

# Exclude these title keywords
TITLE_EXCLUDE = [
    "intern",
    "fresher",
    "junior",
    "entry level",
    "associate",
    "executive",  # too junior in Indian context
]

# ── Source Toggles ──────────────────────────────────────────────
SOURCES = {
    "linkedin": {
        "enabled": True,
        "priority": 1,
        "rate_limit_per_minute": 5,
        "cookie": os.getenv("LINKEDIN_LI_AT", ""),
    },
    "indeed": {
        "enabled": True,
        "priority": 2,
        "rate_limit_per_minute": 10,
    },
    "remoteok": {
        "enabled": True,
        "priority": 3,
        "rate_limit_per_minute": 20,
    },
    "weworkremotely": {
        "enabled": True,
        "priority": 4,
        "rate_limit_per_minute": 15,
    },
    "naukri": {
        "enabled": True,
        "priority": 5,
        "rate_limit_per_minute": 8,
        "email": os.getenv("NAUKRI_EMAIL", ""),
        "password": os.getenv("NAUKRI_PASSWORD", ""),
    },
}

# ── Eligibility + Scoring Scaffold (Issue #2) ──────────────────
# NOTE: permissive defaults only. No hard thresholds are enforced yet.
ELIGIBILITY_SCORING = {
    "enabled": os.getenv("ELIGIBILITY_SCORING_ENABLED", "true").lower() == "true",
    "policy": os.getenv("ELIGIBILITY_POLICY", "pass_through"),
    "default_score": float(os.getenv("ELIGIBILITY_DEFAULT_SCORE", "1.0")),
    "hard_filters": {
        # Future use (currently not enforced)
        "title_exclude": TITLE_EXCLUDE,
        "location_include": LOCATION_FILTERS,
        "min_experience_years": MIN_EXPERIENCE_YEARS,
        "max_experience_years": MAX_EXPERIENCE_YEARS,
    },
    "weights": {
        # Future use (currently not enforced)
        "title_match": 0.35,
        "location_match": 0.25,
        "experience_fit": 0.20,
        "salary_fit": 0.20,
    },
    # Reserved for future rollout.
    "thresholds": {
        "review_below": 0.0,
        "reject_below": 0.0,
    },
}

# ── Verification + Compliance (Issue #23) ──────────────────────
VERIFICATION_COMPLIANCE = {
    "provider": os.getenv("EMAIL_VERIFY_PROVIDER", "neverbounce"),
    "neverbounce_api_key": os.getenv("NEVERBOUNCE_API_KEY", ""),
    "zerobounce_api_key": os.getenv("ZEROBOUNCE_API_KEY", ""),
    "enable_mx_precheck": os.getenv("VERIFY_MX_PRECHECK", "true").lower() == "true",
    "enable_catch_all_precheck": os.getenv("VERIFY_CATCHALL_PRECHECK", "true").lower() == "true",
    "max_touches_per_contact": int(os.getenv("MAX_TOUCHES_PER_CONTACT", "3")),
    "send_window_start": os.getenv("SEND_WINDOW_START", "09:00"),
    "send_window_end": os.getenv("SEND_WINDOW_END", "18:00"),
    "suppression_file": os.getenv("SUPPRESSION_FILE", "output/suppression_list.txt"),
    "audit_log_file": os.getenv("COMPLIANCE_AUDIT_LOG", "logs/compliance_audit.log"),
}

# ── Output ──────────────────────────────────────────────────────
OUTPUT_DIR = "output"
LOG_DIR = "logs"
MAX_RESULTS_PER_SOURCE = 30
DEDUP_WINDOW_HOURS = 48  # skip jobs seen in last 48h

# ── Scheduling ──────────────────────────────────────────────────
SCRAPE_INTERVAL_HOURS = 3

# ── HTTP Defaults ───────────────────────────────────────────────
REQUEST_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
