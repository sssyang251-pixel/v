"""Export analysis outputs for review or interview demos."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .analysis import AnalysisResult


def export_result(result: AnalysisResult, output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []

    report_path = destination / "analysis_report.md"
    report_path.write_text(result.report_markdown, encoding="utf-8")
    files.append(report_path)

    metrics_path = destination / "metrics.csv"
    pd.DataFrame(
        [
            {
                "metric": metric.key,
                "label": metric.label,
                "value": metric.value,
                "available": metric.available,
                "reason": metric.reason,
                "definition": metric.definition,
            }
            for metric in result.metrics.values()
        ]
    ).to_csv(metrics_path, index=False, encoding="utf-8-sig")
    files.append(metrics_path)

    comparison_path = destination / "comparisons.csv"
    result.comparisons.to_csv(comparison_path, index=False, encoding="utf-8-sig")
    files.append(comparison_path)

    anomaly_path = destination / "anomalies.csv"
    result.anomalies.to_csv(anomaly_path, index=False, encoding="utf-8-sig")
    files.append(anomaly_path)

    for dimension, table in result.breakdowns.items():
        path = destination / f"breakdown_{dimension}.csv"
        table.to_csv(path, index=False, encoding="utf-8-sig")
        files.append(path)
    return files

