"""Base adapter — all source scrapers inherit from this."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

import config
from models import Job

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """
    Contract for every job source adapter:
      1. Implement `source_name` property
      2. Implement `fetch_jobs(query)` → list[Job]
    """

    def __init__(self):
        self.client = httpx.Client(
            timeout=config.REQUEST_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
            follow_redirects=True,
        )

    @property
    @abstractmethod
    def source_name(self) -> str:
        """e.g. 'linkedin', 'indeed'"""
        ...

    @abstractmethod
    def fetch_jobs(self, query: str) -> list[Job]:
        """Scrape jobs for a given search query. Return list of Job models."""
        ...

    def is_relevant(self, job: Job) -> bool:
        """Filter: does this job match our title keywords and location?"""
        title_lower = job.title.lower()

        # Must match at least one title keyword
        if not any(kw in title_lower for kw in config.TITLE_KEYWORDS):
            return False

        # Must not match excluded terms
        if any(ex in title_lower for ex in config.TITLE_EXCLUDE):
            return False

        # Location check (relaxed — some sources don't populate location)
        if job.location:
            loc_lower = job.location.lower()
            if not any(lf in loc_lower for lf in config.LOCATION_FILTERS):
                return False

        return True

    def scrape(self) -> list[Job]:
        """Run all configured queries through this adapter and return filtered jobs."""
        all_jobs: list[Job] = []
        seen_urls: set[str] = set()

        for query in config.SEARCH_QUERIES:
            try:
                jobs = self.fetch_jobs(query)
                for job in jobs:
                    if job.url in seen_urls:
                        continue
                    seen_urls.add(job.url)
                    if self.is_relevant(job):
                        all_jobs.append(job)
                        if len(all_jobs) >= config.MAX_RESULTS_PER_SOURCE:
                            return all_jobs
            except Exception as e:
                logger.error(f"[{self.source_name}] query '{query}' failed: {e}")

        logger.info(f"[{self.source_name}] scraped {len(all_jobs)} relevant jobs")
        return all_jobs

    def close(self):
        self.client.close()
