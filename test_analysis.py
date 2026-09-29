from __future__ import annotations

import unittest

import pandas as pd

from ecom_agent.analysis import analyze
from ecom_agent.metrics import calculate_metrics


class MetricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-02-01", "2025-02-01"]),
                "order_id": ["A", "B", "C", "D"],
                "units_sold": [1, 2, 1, 3],
                "gmv": [100, 200, 120, 360],
                "impressions": [1000, 1000, 1000, 1000],
                "clicks": [100, 100, 120, 120],
                "visitors": [80, 80, 90, 90],
                "is_refunded": [False, True, False, False],
                "ad_spend": [50, 50, 60, 60],
                "product": ["P1", "P2", "P1", "P2"],
            }
        )

    def test_metric_formulas(self) -> None:
        metrics = calculate_metrics(self.frame.iloc[:2])
        self.assertEqual(metrics["gmv"].value, 300)
        self.assertEqual(metrics["orders"].value, 2)
        self.assertEqual(metrics["units_sold"].value, 3)
        self.assertEqual(metrics["aov"].value, 150)
        self.assertAlmostEqual(metrics["ctr"].value, 0.1)
        self.assertAlmostEqual(metrics["cvr"].value, 0.01)
        self.assertAlmostEqual(metrics["refund_rate"].value, 0.5)
        self.assertAlmostEqual(metrics["roi"].value, 3.0)

    def test_missing_fields_are_unavailable(self) -> None:
        minimal = self.frame[["date", "gmv"]]
        metrics = calculate_metrics(minimal)
        self.assertTrue(metrics["gmv"].available)
        self.assertFalse(metrics["orders"].available)
        self.assertIsNone(metrics["orders"].value)
        self.assertFalse(metrics["roi"].available)

    def test_comparison_only_when_history_exists(self) -> None:
        comparison_frame = self.frame.copy()
        comparison_frame.loc[1, "date"] = pd.Timestamp("2025-01-02")
        result = analyze(comparison_frame, start="2025-01-02", end="2025-01-02", dimensions=("product",))
        mom_gmv = result.comparisons.loc[
            (result.comparisons["comparison"] == "环比") & (result.comparisons["metric"] == "gmv")
        ].iloc[0]
        self.assertTrue(mom_gmv["available"])
        self.assertAlmostEqual(mom_gmv["change_rate"], 1.0)
        yoy_gmv = result.comparisons.loc[
            (result.comparisons["comparison"] == "同比") & (result.comparisons["metric"] == "gmv")
        ].iloc[0]
        self.assertFalse(yoy_gmv["available"])


if __name__ == "__main__":
    unittest.main()
