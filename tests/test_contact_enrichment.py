from __future__ import annotations

from pipeline.contact_enrichment import (
    ContactEnricher,
    RateLimitError,
    RetryPolicy,
    SOURCE_APOLLO,
    SOURCE_HUNTER,
    SOURCE_PATTERN_GUESS,
    TransientProviderError,
)


class FakeProvider:
    def __init__(self, name: str, responses: list):
        self.name = name
        self._responses = list(responses)

    def lookup_email(self, *, founder_name: str | None, domain: str, company: str | None = None) -> str | None:
        if not self._responses:
            return None
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def test_waterfall_prefers_hunter_then_stops():
    hunter = FakeProvider("hunter", ["ceo@acme.com"])
    apollo = FakeProvider("apollo", ["should-not-be-used@acme.com"])
    enricher = ContactEnricher(hunter_provider=hunter, apollo_provider=apollo)

    result = enricher.enrich(founder_name="Jane Doe", domain="acme.com", company="Acme")

    assert result.contact_email == "ceo@acme.com"
    assert result.contact_email_source == SOURCE_HUNTER
    assert result.contact_confidence == 0.95
    assert len(result.contact_provenance) == 1


def test_waterfall_falls_back_to_apollo():
    hunter = FakeProvider("hunter", [None])
    apollo = FakeProvider("apollo", ["founder@acme.com"])
    enricher = ContactEnricher(hunter_provider=hunter, apollo_provider=apollo)

    result = enricher.enrich(founder_name="Jane Doe", domain="acme.com", company="Acme")

    assert result.contact_email == "founder@acme.com"
    assert result.contact_email_source == SOURCE_APOLLO
    assert [p["source"] for p in result.contact_provenance[:2]] == [SOURCE_HUNTER, SOURCE_APOLLO]


def test_pattern_guess_fallback_is_deterministic():
    hunter = FakeProvider("hunter", [None])
    apollo = FakeProvider("apollo", [None])
    enricher = ContactEnricher(hunter_provider=hunter, apollo_provider=apollo)

    result = enricher.enrich(founder_name="Jane Doe", domain="acme.com", company="Acme")

    assert result.contact_email == "jane@acme.com"
    assert result.contact_email_source == SOURCE_PATTERN_GUESS
    assert result.contact_confidence == 0.55


def test_retry_backoff_and_rate_limit_handling():
    sleeps = []

    hunter = FakeProvider(
        "hunter",
        [
            RateLimitError(2.5, "slow down"),
            TransientProviderError("upstream 502"),
            None,
        ],
    )
    apollo = FakeProvider("apollo", ["apollo@acme.com"])
    enricher = ContactEnricher(
        hunter_provider=hunter,
        apollo_provider=apollo,
        retry_policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.2, max_backoff_seconds=1.0),
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )

    result = enricher.enrich(founder_name="Jane Doe", domain="acme.com", company="Acme")

    assert sleeps == [2.5, 0.2]
    assert result.contact_email_source == SOURCE_APOLLO
    statuses = [p["status"] for p in result.contact_provenance]
    assert "rate_limited" in statuses
    assert "transient_error" in statuses
