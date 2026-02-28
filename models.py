"""
Job data model and JSON output schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field

from canonical import (
    generate_primary_fingerprint,
    normalize_apply_url,
    normalize_company,
    normalize_location,
    normalize_title,
)


class Job(BaseModel):
    """Single job listing — the core unit of scraper output."""

    title: str
    company: str
    location: str = ""
    url: str
    source: str  # linkedin | indeed | remoteok | weworkremotely | naukri
    description: str = ""
    salary: Optional[str] = None
    experience: Optional[str] = None
    posted_date: Optional[str] = None
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: list[str] = Field(default_factory=list)
    remote_type: str = "remote"  # remote | hybrid | onsite
    apply_url: Optional[str] = None
    source_job_id: Optional[str] = None
    source_ids: dict[str, str] = Field(default_factory=dict)

    # Issue #2 scaffold: deterministic eligibility/scoring output fields.
    # Current defaults are permissive pass-through until policy enforcement is enabled.
    eligibility_status: str = "pass"
    score: float = 1.0
    score_breakdown: dict[str, float] = Field(default_factory=lambda: {"baseline_pass_through": 1.0})
    rejection_reasons: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def normalized_apply_url(self) -> str:
        return normalize_apply_url(self.apply_url or self.url)

    @computed_field
    @property
    def company_norm(self) -> str:
        return normalize_company(self.company)

    @computed_field
    @property
    def title_norm(self) -> str:
        return normalize_title(self.title)

    @computed_field
    @property
    def location_norm(self) -> str:
        return normalize_location(self.location)

    @computed_field
    @property
    def primary_fingerprint(self) -> str:
        """Issue #3 canonical key: sha256(normalized_apply_url + company_norm + title_norm + location_norm)."""
        return generate_primary_fingerprint(
            apply_url=self.normalized_apply_url,
            company=self.company_norm,
            title=self.title_norm,
            location=self.location_norm,
        )

    @computed_field
    @property
    def job_id(self) -> str:
        """Backward-compatible short id derived from primary fingerprint."""
        return self.primary_fingerprint[:16]


class ScrapeResult(BaseModel):
    """Output of a single scrape run — written to JSON file."""

    run_id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    total_jobs: int = 0
    new_jobs: int = 0
    sources_scraped: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    jobs: list[Job] = Field(default_factory=list)

    def add_job(self, job: Job) -> None:
        for existing in self.jobs:
            if existing.primary_fingerprint == job.primary_fingerprint:
                # Preserve secondary trace IDs for observability.
                if job.source_job_id and not existing.source_job_id:
                    existing.source_job_id = job.source_job_id
                existing.source_ids = {**existing.source_ids, **job.source_ids}
                return
        self.jobs.append(job)
        self.total_jobs = len(self.jobs)

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "total": self.total_jobs,
            "new": self.new_jobs,
            "by_source": {s: sum(1 for j in self.jobs if j.source == s) for s in self.sources_scraped},
            "errors": len(self.errors),
        }
