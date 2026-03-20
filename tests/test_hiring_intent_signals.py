import json
import unittest
from datetime import UTC, datetime
from pathlib import Path

from pipeline.hiring_intent_signals import build_hiring_intent_signals

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "hiring_intent_signals"


class TestHiringIntentSignals(unittest.TestCase):
    def _load(self, name: str):
        return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))

    def test_normalized_schema_freshness_and_dedupe(self):
        source_records = {
            "wellfound": self._load("wellfound"),
            "naukri": self._load("naukri"),
            "cutshort": self._load("cutshort"),
            "instahyre": self._load("instahyre"),
            "yc_jobs": self._load("yc_jobs"),
        }

        signals = build_hiring_intent_signals(
            source_records,
            now=datetime(2026, 3, 20, tzinfo=UTC),
        )

        # 8 raw rows -> remove 1 stale + 1 invalid + 1 duplicate = 5 unique fresh signals.
        self.assertEqual(len(signals), 5)

        required_fields = {
            "source",
            "company",
            "role",
            "location",
            "posted_date",
            "source_url",
            "canonical_url",
            "metadata",
        }
        for signal in signals:
            self.assertEqual(set(signal.keys()), required_fields)

            posted = datetime.fromisoformat(signal["posted_date"]).replace(tzinfo=UTC)
            age_days = (datetime(2026, 3, 20, tzinfo=UTC) - posted).days
            self.assertLessEqual(age_days, 60)

        dedupe_keys = {
            (s["company"].lower().strip(), s["role"].lower().strip(), s["canonical_url"]) for s in signals
        }
        self.assertEqual(len(dedupe_keys), len(signals))

        # Canonical URL normalization strips tracking params and normalizes trailing slash.
        acme_urls = [
            s["canonical_url"]
            for s in signals
            if s["company"] == "Acme Labs" and s["role"] == "Customer Success Manager"
        ]
        self.assertEqual(acme_urls, ["https://wellfound.com/jobs/123"])

    def test_ignores_unknown_source(self):
        signals = build_hiring_intent_signals(
            {
                "unknown_source": [
                    {
                        "company": "X",
                        "title": "Y",
                        "url": "https://example.com/job",
                        "posted_date": "2026-03-19",
                    }
                ]
            },
            now=datetime(2026, 3, 20, tzinfo=UTC),
        )

        self.assertEqual(signals, [])


if __name__ == "__main__":
    unittest.main()
