from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


performance_baseline = load_runtime_module("performance_baseline")


class PerformanceBaselineTests(unittest.TestCase):
    def test_run_benchmarks_returns_selected_scenario(self) -> None:
        payload = performance_baseline.run_benchmarks(
            scenario_ids=["same-session-routing-rule"],
            iterations=3,
            warmup_iterations=0,
        )

        self.assertEqual(payload["schema"], "openclaw.task-system.performance-benchmark.v1")
        self.assertEqual(payload["summary"]["scenario_count"], 1)
        self.assertEqual(payload["scenarios"][0]["scenario_id"], "same-session-routing-rule")
        self.assertIn("median_ms", payload["scenarios"][0]["summary"])
        self.assertIn("p95_ms", payload["scenarios"][0]["summary"])

    def test_run_benchmarks_can_capture_profile_rows(self) -> None:
        payload = performance_baseline.run_benchmarks(
            scenario_ids=["system-overview"],
            iterations=1,
            warmup_iterations=0,
            profile_scenarios=["system-overview"],
            profile_top=5,
        )

        self.assertIn("system-overview", payload["profiles"])
        self.assertGreaterEqual(len(payload["profiles"]["system-overview"]), 1)
        self.assertIn("function", payload["profiles"]["system-overview"][0])
        self.assertIn("cumulative_time_s", payload["profiles"]["system-overview"][0])


if __name__ == "__main__":
    unittest.main()
