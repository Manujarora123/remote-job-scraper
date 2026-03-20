"""Deterministic founder/business email enrichment waterfall.

Issue #22 scope:
- Ordered waterfall: Hunter -> Apollo -> deterministic pattern guess
- Provenance tracking for every stage/attempt
- Contact confidence scoring with transparent source weighting
- Retry/backoff for transient failures and provider rate-limits
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests


SOURCE_HUNTER = "hunter"
SOURCE_APOLLO = "apollo"
SOURCE_PATTERN_GUESS = "pattern_guess"


class ProviderError(Exception):
    """Base class for provider exceptions."""


class TransientProviderError(ProviderError):
    """Retryable provider error (network, upstream 5xx, timeout)."""


class RateLimitError(ProviderError):
    """Provider asked us to back off for retry_after_seconds."""

    def __init__(self, retry_after_seconds: float = 1.0, message: str = "rate-limited") -> None:
        self.retry_after_seconds = float(max(retry_after_seconds, 0.0))
        super().__init__(message)


class EmailProvider(Protocol):
    """External provider contract used by the waterfall orchestrator."""

    name: str

    def lookup_email(self, *, founder_name: str | None, domain: str, company: str | None = None) -> str | None:
        """Return discovered email or None when not found."""
        ...


class HunterProvider:
    name = SOURCE_HUNTER

    def __init__(self, api_key: str, *, session: requests.Session | None = None) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()

    def lookup_email(self, *, founder_name: str | None, domain: str, company: str | None = None) -> str | None:
        params: dict[str, str] = {"domain": domain, "api_key": self._api_key}
        first, last = _split_name(founder_name)
        if first:
            params["first_name"] = first
        if last:
            params["last_name"] = last

        response = self._session.get("https://api.hunter.io/v2/email-finder", params=params, timeout=12)
        if response.status_code == 429:
            raise RateLimitError(_retry_after(response), "hunter rate-limited")
        if response.status_code >= 500:
            raise TransientProviderError(f"hunter upstream {response.status_code}")
        if response.status_code >= 400:
            raise ProviderError(f"hunter http {response.status_code}")

        data = response.json().get("data", {})
        return data.get("email")


class ApolloProvider:
    name = SOURCE_APOLLO

    def __init__(self, api_key: str, *, session: requests.Session | None = None) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()

    def lookup_email(self, *, founder_name: str | None, domain: str, company: str | None = None) -> str | None:
        payload: dict[str, str] = {"domain": domain}
        if founder_name:
            payload["name"] = founder_name
        if company:
            payload["organization_name"] = company

        response = self._session.post(
            "https://api.apollo.io/api/v1/people/match",
            json=payload,
            headers={"x-api-key": self._api_key},
            timeout=12,
        )
        if response.status_code == 429:
            raise RateLimitError(_retry_after(response), "apollo rate-limited")
        if response.status_code >= 500:
            raise TransientProviderError(f"apollo upstream {response.status_code}")
        if response.status_code >= 400:
            raise ProviderError(f"apollo http {response.status_code}")

        person = response.json().get("person") or {}
        return person.get("email")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0
    backoff_multiplier: float = 2.0


@dataclass
class ContactEnrichmentResult:
    founder_email: str | None = None
    business_email: str | None = None
    contact_email: str | None = None
    contact_email_source: str | None = None
    contact_confidence: float = 0.0
    contact_provenance: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "founder_email": self.founder_email,
            "business_email": self.business_email,
            "contact_email": self.contact_email,
            "contact_email_source": self.contact_email_source,
            "contact_confidence": float(round(self.contact_confidence, 4)),
            "contact_provenance": self.contact_provenance,
        }


CONFIDENCE_BY_SOURCE = {
    SOURCE_HUNTER: 0.95,
    SOURCE_APOLLO: 0.88,
    SOURCE_PATTERN_GUESS: 0.55,
}


class ContactEnricher:
    """Deterministic waterfall orchestrator for founder/business email enrichment."""

    def __init__(
        self,
        *,
        hunter_provider: EmailProvider,
        apollo_provider: EmailProvider,
        retry_policy: RetryPolicy | None = None,
        sleep_fn=time.sleep,
    ) -> None:
        self._hunter = hunter_provider
        self._apollo = apollo_provider
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep_fn = sleep_fn

    def enrich(self, *, founder_name: str | None, domain: str, company: str | None = None) -> ContactEnrichmentResult:
        normalized_domain = _normalize_domain(domain)
        provenance: list[dict[str, Any]] = []

        email = self._lookup_with_retry(
            provider=self._hunter,
            source=SOURCE_HUNTER,
            founder_name=founder_name,
            domain=normalized_domain,
            company=company,
            provenance=provenance,
        )
        if email:
            return _build_result(email=email, source=SOURCE_HUNTER, provenance=provenance)

        email = self._lookup_with_retry(
            provider=self._apollo,
            source=SOURCE_APOLLO,
            founder_name=founder_name,
            domain=normalized_domain,
            company=company,
            provenance=provenance,
        )
        if email:
            return _build_result(email=email, source=SOURCE_APOLLO, provenance=provenance)

        email = _pattern_guess(founder_name=founder_name, domain=normalized_domain)
        provenance.append(
            {
                "source": SOURCE_PATTERN_GUESS,
                "attempt": 1,
                "status": "success" if email else "not_found",
                "email": email,
            }
        )

        if email:
            return _build_result(email=email, source=SOURCE_PATTERN_GUESS, provenance=provenance)

        return ContactEnrichmentResult(contact_provenance=provenance)

    def _lookup_with_retry(
        self,
        *,
        provider: EmailProvider,
        source: str,
        founder_name: str | None,
        domain: str,
        company: str | None,
        provenance: list[dict[str, Any]],
    ) -> str | None:
        attempts = max(self._retry_policy.max_attempts, 1)
        backoff = max(self._retry_policy.initial_backoff_seconds, 0.0)

        for attempt in range(1, attempts + 1):
            try:
                email = provider.lookup_email(founder_name=founder_name, domain=domain, company=company)
                provenance.append(
                    {
                        "source": source,
                        "provider": provider.name,
                        "attempt": attempt,
                        "status": "success" if email else "not_found",
                        "email": email,
                    }
                )
                return _normalize_email(email)
            except RateLimitError as exc:
                provenance.append(
                    {
                        "source": source,
                        "provider": provider.name,
                        "attempt": attempt,
                        "status": "rate_limited",
                        "error": str(exc),
                        "retry_after_seconds": exc.retry_after_seconds,
                    }
                )
                if attempt >= attempts:
                    break
                self._sleep_fn(exc.retry_after_seconds)
            except TransientProviderError as exc:
                provenance.append(
                    {
                        "source": source,
                        "provider": provider.name,
                        "attempt": attempt,
                        "status": "transient_error",
                        "error": str(exc),
                    }
                )
                if attempt >= attempts:
                    break
                self._sleep_fn(backoff)
                backoff = min(backoff * self._retry_policy.backoff_multiplier, self._retry_policy.max_backoff_seconds)
            except Exception as exc:  # deterministic fail-closed; no retries for unknown errors
                provenance.append(
                    {
                        "source": source,
                        "provider": provider.name,
                        "attempt": attempt,
                        "status": "fatal_error",
                        "error": str(exc),
                    }
                )
                break

        return None


def _build_result(*, email: str, source: str, provenance: list[dict[str, Any]]) -> ContactEnrichmentResult:
    normalized_email = _normalize_email(email)
    confidence = CONFIDENCE_BY_SOURCE[source]
    founder_email = normalized_email if source != SOURCE_PATTERN_GUESS or "@" in normalized_email else None
    return ContactEnrichmentResult(
        founder_email=founder_email,
        business_email=normalized_email,
        contact_email=normalized_email,
        contact_email_source=source,
        contact_confidence=confidence,
        contact_provenance=provenance,
    )


def _normalize_domain(domain: str) -> str:
    cleaned = domain.strip().lower()
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = cleaned.split("/")[0]
    return cleaned.removeprefix("www.")


def _normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower()


def _pattern_guess(*, founder_name: str | None, domain: str) -> str | None:
    first, last = _split_name(founder_name)
    if not first:
        return f"info@{domain}" if domain else None

    candidates: list[str] = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}" if last else "",
        f"{first}{last}@{domain}" if last else "",
        f"{first[0]}{last}@{domain}" if last else "",
        f"{first}.{last[0]}@{domain}" if last else "",
        f"info@{domain}",
    ]

    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _split_name(name: str | None) -> tuple[str, str]:
    if not name:
        return "", ""
    parts = [p.lower() for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def _retry_after(response: requests.Response) -> float:
    raw = response.headers.get("Retry-After", "1")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 1.0
