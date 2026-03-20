"""Hiring intent signal normalization for startup job sources (Issue #17)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

SUPPORTED_SOURCES = {"wellfound", "naukri", "cutshort", "instahyre", "yc_jobs"}
MAX_SIGNAL_AGE_DAYS = 60
TRACKING_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "mc_cid", "mc_eid",
    "src", "source", "ref", "referrer", "referral", "feedid", "trackingid",
    "li_fat_id", "trk", "trkemail", "gh_src",
}


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").lower().split()).strip()


def _canonicalize_url(raw_url: str | None) -> str:
    if not raw_url:
        return ""

    parts = urlsplit(raw_url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")

    kept = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower in TRACKING_QUERY_KEYS or key_lower.startswith("utm_"):
            continue
        kept.append((key, value))
    kept.sort(key=lambda item: (item[0], item[1]))

    query = urlencode(kept)
    return urlunsplit((scheme, netloc, path, query, ""))


class HiringIntentSignal(BaseModel):
    """Normalized hiring intent record shared across source modules."""

    source: str
    company: str
    role: str
    location: str = ""
    posted_date: str
    source_url: str
    canonical_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def dedupe_key(self) -> str:
        return "|".join(
            [
                _normalize_text(self.company),
                _normalize_text(self.role),
                self.canonical_url,
            ]
        )


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        for parser in (
            lambda t: datetime.fromisoformat(t),
            lambda t: datetime.strptime(t, "%Y-%m-%d"),
            lambda t: datetime.strptime(t, "%d-%m-%Y"),
            lambda t: datetime.strptime(t, "%d/%m/%Y"),
            lambda t: datetime.strptime(t, "%b %d, %Y"),
            lambda t: datetime.strptime(t, "%B %d, %Y"),
        ):
            try:
                parsed = parser(text)
                return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
            except ValueError:
                continue

    return None


def _pick(record: dict[str, Any], candidates: list[str]) -> Any:
    for key in candidates:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _normalize_record(record: dict[str, Any], source: str, now: datetime) -> HiringIntentSignal | None:
    company = _pick(record, ["company", "company_name", "startup", "org", "organization"])
    role = _pick(record, ["role", "title", "job_title", "position"])
    location = _pick(record, ["location", "job_location", "city", "region"]) or ""
    source_url = _pick(record, ["source_url", "url", "job_url", "apply_url", "link"])
    posted_raw = _pick(record, ["posted_date", "posted_at", "created_at", "published_at", "date"])

    if not all([company, role, source_url, posted_raw]):
        return None

    posted_dt = _to_datetime(posted_raw)
    if posted_dt is None:
        return None

    if posted_dt < (now - timedelta(days=MAX_SIGNAL_AGE_DAYS)):
        return None

    canonical_url = _canonicalize_url(str(source_url))

    return HiringIntentSignal(
        source=source,
        company=str(company).strip(),
        role=str(role).strip(),
        location=str(location).strip(),
        posted_date=posted_dt.date().isoformat(),
        source_url=str(source_url).strip(),
        canonical_url=canonical_url,
        metadata={k: v for k, v in record.items() if k not in {"company", "company_name", "startup", "org", "organization", "role", "title", "job_title", "position", "location", "job_location", "city", "region", "source_url", "url", "job_url", "apply_url", "link", "posted_date", "posted_at", "created_at", "published_at", "date"}},
    )


def build_hiring_intent_signals(source_records: dict[str, list[dict[str, Any]]], now: datetime | None = None) -> list[dict[str, Any]]:
    """Normalize, freshness-filter, and dedupe startup hiring intent records.

    Args:
        source_records: Map of source name -> list of raw source records.
        now: Optional fixed timestamp for deterministic tests.

    Returns:
        List of normalized signal dictionaries.
    """

    now_dt = now.astimezone(UTC) if now else datetime.now(tz=UTC)

    deduped: dict[str, HiringIntentSignal] = {}
    for source, records in source_records.items():
        source_name = source.lower().strip()
        if source_name not in SUPPORTED_SOURCES:
            continue

        for record in records:
            signal = _normalize_record(record, source=source_name, now=now_dt)
            if signal is None:
                continue

            if signal.dedupe_key not in deduped:
                deduped[signal.dedupe_key] = signal

    return [signal.model_dump() for signal in deduped.values()]
