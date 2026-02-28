"""Canonical normalization + fingerprint contract (Issue #3)."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "mc_cid", "mc_eid",
    "src", "source", "ref", "referrer", "referral", "feedid", "trackingid",
    "li_fat_id", "trk", "trkemail", "gh_src",
}


def normalize_whitespace(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip().lower()


def normalize_company(value: str | None) -> str:
    return normalize_whitespace(value)


def normalize_title(value: str | None) -> str:
    return normalize_whitespace(value)


def normalize_location(value: str | None) -> str:
    text = normalize_whitespace(value)
    text = re.sub(r"\b(wfh|work from home)\b", "remote", text)
    text = re.sub(r"\bremote\s*[-,/]?\s*india\b", "remote india", text)
    text = re.sub(r"\bindia\s*[-,/]?\s*remote\b", "remote india", text)
    return text


def normalize_apply_url(raw_url: str | None) -> str:
    if not raw_url:
        return ""
    try:
        parts = urlsplit(raw_url.strip())
    except Exception:
        return raw_url.strip().lower()

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if (scheme == "https" and netloc.endswith(":443")) or (scheme == "http" and netloc.endswith(":80")):
        netloc = netloc.rsplit(":", 1)[0]

    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")

    kept = []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        kl = k.lower()
        if kl in TRACKING_QUERY_KEYS or kl.startswith("utm_"):
            continue
        kept.append((k, v))
    kept.sort(key=lambda x: (x[0], x[1]))
    query = urlencode(kept)

    return urlunsplit((scheme, netloc, path, query, ""))


def generate_primary_fingerprint(*, apply_url: str | None, company: str | None, title: str | None, location: str | None) -> str:
    material = (
        normalize_apply_url(apply_url)
        + normalize_company(company)
        + normalize_title(title)
        + normalize_location(location)
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
