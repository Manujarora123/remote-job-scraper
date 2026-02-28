import unittest

from canonical import generate_primary_fingerprint, normalize_apply_url, normalize_location
from models import Job, ScrapeResult


class CanonicalTests(unittest.TestCase):
    def test_url_normalization_drops_tracking(self):
        url = "https://careers.example.com/job/123/?utm_source=linkedin&src=abc&job=1"
        self.assertEqual(normalize_apply_url(url), "https://careers.example.com/job/123?job=1")

    def test_location_variants(self):
        self.assertEqual(normalize_location("WFH India"), "remote india")
        self.assertEqual(normalize_location("India - Remote"), "remote india")

    def test_title_case_same_fingerprint(self):
        a = generate_primary_fingerprint(
            apply_url="https://x.com/jobs/1",
            company="ACME",
            title="Senior Product Manager",
            location="India Remote",
        )
        b = generate_primary_fingerprint(
            apply_url="https://x.com/jobs/1/",
            company="acme",
            title="senior product manager",
            location="remote india",
        )
        self.assertEqual(a, b)

    def test_scrape_result_dedupe(self):
        r = ScrapeResult()
        j1 = Job(title="Ops Manager", company="Foo", location="WFH India", url="https://example.com/job/1", source="linkedin", apply_url="https://example.com/job/1?utm_source=li", source_job_id="111")
        j2 = Job(title="ops manager", company="foo", location="Remote India", url="https://example.com/job/1", source="indeed", apply_url="https://example.com/job/1", source_job_id="abc")
        r.add_job(j1)
        r.add_job(j2)
        self.assertEqual(len(r.jobs), 1)
        self.assertIn("111", [r.jobs[0].source_job_id, r.jobs[0].source_ids.get("linkedin")])


if __name__ == "__main__":
    unittest.main()
