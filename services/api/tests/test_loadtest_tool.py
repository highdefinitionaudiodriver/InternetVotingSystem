from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT / "tools"))

from loadtest import LoadTestConfig, pick_candidate_id, run_load_test


class LoadTestToolTest(unittest.TestCase):
    def test_pick_candidate_id_rotates_through_election_candidates(self) -> None:
        config = LoadTestConfig(
            base_url="http://127.0.0.1:8787",
            election_id="custom-election",
            voters=4,
            concurrency=1,
            timeout=1,
            verify_receipts=False,
            candidate_ids=("alpha", "beta", "gamma"),
        )

        self.assertEqual(
            ["alpha", "beta", "gamma", "alpha"],
            [pick_candidate_id(config, index) for index in range(4)],
        )

    def test_run_load_test_requires_candidate_ids(self) -> None:
        config = LoadTestConfig(
            base_url="http://127.0.0.1:8787",
            election_id="custom-election",
            voters=1,
            concurrency=1,
            timeout=1,
            verify_receipts=False,
            candidate_ids=(),
        )

        with self.assertRaises(ValueError):
            run_load_test(config)


if __name__ == "__main__":
    unittest.main()
