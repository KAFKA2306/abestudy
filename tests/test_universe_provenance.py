import unittest

from src.common import universe


class UniverseProvenanceTests(unittest.TestCase):
    def test_repository_dataset_is_quarantined(self):
        self.assertTrue(universe._PROVENANCE_ERRORS)
        self.assertEqual(universe.ALL_TICKERS, [])
        with self.assertRaisesRegex(RuntimeError, "quarantined"):
            universe.assert_verified_universe()

    def test_verified_record_requires_complete_evidence(self):
        snapshots = {universe.dt.date(2013, 1, 1): {"0000.T": "Example"}}
        provenance = {
            "dataset_status": "verified",
            "snapshots": {
                "2013-01-01": {
                    "as_of": "2013-01-01",
                    "source_url": "https://example.invalid/original.xlsx",
                    "published_at": "2012-12-28",
                    "retrieved_at": "2026-08-02",
                    "file_sha256": "0" * 64,
                    "verified_by": "independent-reviewer",
                }
            },
        }
        self.assertEqual(universe._validate_provenance(snapshots, provenance), [])


if __name__ == "__main__":
    unittest.main()
