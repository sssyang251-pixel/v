"""Comparisons, dimensional analysis, anomaly detection, and report assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
import pandas as pd

from .metrics import METRIC_LABELS, MetricResult, calculate_metrics, metrics_as_row
from .schema import DIMENSIONS, DIMENSION_LABELS


@dataclass(frozen=True)
class Period:
    start: pd.Timestamp
    end: pd.Timestamp

    @property
    def days(self) -> int:
        return int((self.end - self.start).days) + 1

    @property
    def label(self) -> str:
        return f"{self.start:%Y-%m-%d} 至 {self.end:%Y-%m-%d}"


@dataclass
class AnalysisResult:
    period: Period
    current_data: pd.DataFrame
    metrics: dict[str, MetricResult]
    comparisons: pd.DataFrame
    breakdowns: dict[str, pd.DataFrame]
    contributions: dict[str, pd.DataFrame]
    anomalies: pd.DataFrame
    report_markdown: str
    notes: list[str] = field(default_factory=list)


def _slice(frame: pd.DataFrame, period: Period) -> pd.DataFrame:
    return frame.loc[frame["date"].between(period.start, period.end)].copy()


def _comparison_periods(period: Period) -> dict[str, Period]:
    previous_end = period.start - pd.Timedelta(1, unit="D")
    previous = Period(previous_end - pd.Timedelta(int(period.days - 1), unit="D"), previous_end)
    yoy = Period(period.start - pd.DateOffset(years=1), period.end - pd.DateOffset(years=1))
    return {"环比": previous, "同比": yoy}


def _metric_comparisons(frame: pd.DataFrame, current: pd.DataFrame, period: Period) -> pd.DataFrame:
    current_metrics = calculate_metrics(current)
    rows: list[dict[str, object]] = []
    for comparison_name, comparison_period in _comparison_periods(period).items():
        reference = _slice(frame, comparison_period)
        reference_metrics = calculate_metrics(reference) if not reference.empty else {}
        for key, current_metric in current_metrics.items():
            reference_metric = reference_metrics.get(key)
            comparable = (
                not reference.empty
                and current_metric.value is not None
                and reference_metric is not None
                and reference_metric.value is not None
            )
            reference_value = reference_metric.value if comparable else None
            change = (
                (current_metric.value - reference_value) / abs(reference_value)
                if comparable and reference_value != 0
                else None
            )
            rows.append(
                {
                    "comparison": comparison_name,
                    "metric": key,
                    "metric_label": current_metric.label,
                    "current": current_metric.value,
                    "reference": reference_value,
                    "change_rate": change,
                    "reference_period": comparison_period.label,
                    "available": comparable,
                    "reason": None if comparable else "对应历史区间无可比数据或指标缺失",
                }
            )
    return pd.DataFrame(rows)


def _breakdown(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    if dimension not in frame.columns:
        return pd.DataFrame()
    data = frame.copy()
    if dimension == "date":
        data[dimension] = data[dimension].dt.strftime("%Y-%m-%d")
    data[dimension] = data[dimension].fillna("未归类").astype(str)
    rows = []
    for value, group in data.groupby(dimension, dropna=False, sort=False):
        rows.append({dimension: value, **metrics_as_row(group)})
    result = pd.DataFrame(rows)
    sort_column = next((key for key in ("gmv", "orders", "units_sold") if key in result and result[key].notna().any()), None)
    if sort_column:
        result = result.sort_values(sort_column, ascending=False, na_position="last")
    return result.reset_index(drop=True)


def _contribution(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    dimension: str,
    metric: str = "gmv",
) -> pd.DataFrame:
    if dimension not in current.columns or previous.empty or dimension not in previous.columns:
        return pd.DataFrame()
    current_values = _breakdown(current, dimension)
    previous_values = _breakdown(previous, dimension)
    if metric not in current_values or metric not in previous_values:
        return pd.DataFrame()
    merged = current_values[[dimension, metric]].merge(
        previous_values[[dimension, metric]], on=dimension, how="outer", suffixes=("_current", "_previous")
    )
    merged[[f"{metric}_current", f"{metric}_previous"]] = merged[
        [f"{metric}_current", f"{metric}_previous"]
    ].fillna(0.0)
    merged["delta"] = merged[f"{metric}_current"] - merged[f"{metric}_previous"]
    total_delta = float(merged["delta"].sum())
    merged["contribution_rate"] = merged["delta"] / total_delta if total_delta != 0 else np.nan
    return merged.sort_values("delta", key=lambda values: values.abs(), ascending=False).reset_index(drop=True)


def _daily_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = []
    for date, group in frame.groupby("date", sort=True):
        rows.append({"date": date, **metrics_as_row(group)})
    return pd.DataFrame(rows).sort_values("date")


def _detect_anomalies(current: pd.DataFrame) -> pd.DataFrame:
    daily = _daily_metrics(current)
    if len(daily) < 7:
        return pd.DataFrame(columns=["date", "metric", "metric_label", "value", "change_rate", "severity", "reason"])
    rows: list[dict[str, object]] = []
    for metric in ("gmv", "orders", "uv", "ctr", "cvr", "refund_rate", "roi"):
        if metric not in daily or daily[metric].notna().sum() < 7:
            continue
        series = daily[metric].astype(float)
        median = float(series.median())
        mad = float(np.median(np.abs(series.dropna() - median)))
        robust_z = (series - median).abs() / (1.4826 * mad) if mad > 0 else pd.Series(0.0, index=series.index)
        pct_change = series.pct_change().replace([np.inf, -np.inf], np.nan)
        flagged = (robust_z >= 3.0) | (pct_change.abs() >= 0.30)
        for index in daily.index[flagged.fillna(False)]:
            change = pct_change.loc[index]
            severity = "高" if robust_z.loc[index] >= 4.5 or (pd.notna(change) and abs(change) >= 0.5) else "中"
            reasons = []
            if robust_z.loc[index] >= 3.0:
                reasons.append(f"偏离区间中位数 {robust_z.loc[index]:.1f} 个稳健标准差")
            if pd.notna(change) and abs(change) >= 0.30:
                reasons.append(f"较前一日变化 {change:+.1%}")
            rows.append(
                {
                    "date": daily.loc[index, "date"],
                    "metric": metric,
                    "metric_label": METRIC_LABELS[metric],
                    "value": daily.loc[index, metric],
                    "change_rate": change if pd.notna(change) else None,
                    "severity": severity,
                    "reason": "；".join(reasons),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["date", "metric", "metric_label", "value", "change_rate", "severity", "reason"])
    return pd.DataFrame(rows).sort_values(["date", "severity"], ascending=[False, True]).reset_index(drop=True)


def _format_value(value: float | None, unit: str) -> str:
    if value is None or pd.isna(value):
        return "不可计算"
    if unit == "currency":
        return f"¥{value:,.2f}"
    if unit == "rate":
        return f"{value:.2%}"
    if unit == "ratio":
        return f"{value:.2f}"
    return f"{value:,.0f}"


def _build_report(
    period: Period,
    metrics: dict[str, MetricResult],
    comparisons: pd.DataFrame,
    contributions: dict[str, pd.DataFrame],
    anomalies: pd.DataFrame,
    notes: list[str],
) -> str:
    lines = ["# 电商运营数据分析报告", "", f"分析区间：{period.label}", "", "## 一、数据现状", ""]
    for metric in metrics.values():
        if metric.available:
            lines.append(f"- {metric.label}：{_format_value(metric.value, metric.unit)}")
        else:
            lines.append(f"- {metric.label}：不可计算（{metric.reason}）")

    lines.extend(["", "## 二、问题与主要变化", ""])
    change_values = pd.to_numeric(comparisons["change_rate"], errors="coerce")
    available_changes = comparisons.assign(_change_numeric=change_values).loc[
        comparisons["available"] & (change_values.abs() >= 0.10)
    ].copy()
    if available_changes.empty and anomalies.empty:
        lines.append("- 未发现超过 10% 的显著对比变化，当前区间也没有触发异常规则。")
    else:
        for _, row in available_changes.sort_values("_change_numeric", ascending=False, key=lambda values: values.abs()).head(6).iterrows():
            direction = "上升" if row["change_rate"] > 0 else "下降"
            lines.append(f"- {row['metric_label']} {row['comparison']}{direction} {abs(row['change_rate']):.1%}。")
        if not anomalies.empty:
            for _, row in anomalies.head(5).iterrows():
                lines.append(f"- {row['date']:%Y-%m-%d} 的 {row['metric_label']} 出现{row['severity']}等级异常：{row['reason']}。")

    lines.extend(["", "## 三、可能原因", ""])
    cause_count = 0
    for dimension, table in contributions.items():
        if table.empty:
            continue
        for _, row in table.head(2).iterrows():
            if row["delta"] == 0:
                continue
            direction = "增加" if row["delta"] > 0 else "减少"
            lines.append(
                f"- {DIMENSION_LABELS[dimension]}“{row[dimension]}”的 GMV 较上一可比区间{direction} ¥{abs(row['delta']):,.2f}，"
                "是总体变化的主要来源之一；需结合该分组的流量、点击和转化进一步验证。"
            )
            cause_count += 1
    if cause_count == 0:
        lines.append("- 当前没有足够的历史数据与维度字段来定位变化来源，不能据此推断具体原因。")

    mom = comparisons.loc[(comparisons["comparison"] == "环比") & comparisons["available"]].set_index("metric")
    def change_of(metric: str) -> float | None:
        return float(mom.loc[metric, "change_rate"]) if metric in mom.index and pd.notna(mom.loc[metric, "change_rate"]) else None

    lines.extend(["", "## 四、运营建议", ""])
    suggestions: list[str] = []
    gmv_change = change_of("gmv")
    if gmv_change is not None and gmv_change < -0.05:
        uv_change, ctr_change, cvr_change = change_of("uv"), change_of("ctr"), change_of("cvr")
        drivers = [("UV", uv_change), ("CTR", ctr_change), ("CVR", cvr_change)]
        declining = [label for label, value in drivers if value is not None and value < -0.05]
        if declining:
            suggestions.append(f"GMV 下滑优先排查 {('、'.join(declining))}。先查看对应渠道、商品和达人分组，再做素材、承接页或货品调整。")
        else:
            suggestions.append("GMV 下滑但现有漏斗指标未同步显著下降，建议核查客单价、商品结构及数据口径变化。")
    refund_change = change_of("refund_rate")
    if refund_change is not None and refund_change > 0.10:
        suggestions.append("退款率明显上升。按商品定位退款集中项，并补充退款原因字段后验证质量、描述一致性和履约问题。")
    roi_change = change_of("roi")
    if roi_change is not None and roi_change < -0.10:
        suggestions.append("ROI 明显下降。按渠道和达人复核花费增量与 GMV 增量，暂停持续低效组合并保留小预算复测。")
    if not suggestions:
        suggestions.append("保持当前策略，每日监控 GMV、CTR、CVR、退款率和 ROI；对异常日期回看活动、库存、投放和内容变更记录。")
    suggestions.append("所有“可能原因”均为数据线索，不是因果结论。建议结合活动、库存、价格、素材和退款原因记录做二次验证。")
    lines.extend(f"- {item}" for item in suggestions)

    lines.extend(["", "## 数据与口径说明", ""])
    lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines) + "\n"


def analyze(
    frame: pd.DataFrame,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    dimensions: tuple[str, ...] = ("product", "channel", "creator"),
) -> AnalysisResult:
    """Run a complete analysis over the selected period."""

    if frame.empty:
        raise ValueError("没有可分析的数据。")
    end_ts = pd.Timestamp(end).normalize() if end is not None else frame["date"].max().normalize()
    start_ts = pd.Timestamp(start).normalize() if start is not None else max(frame["date"].min(), end_ts - pd.Timedelta(days=29))
    if start_ts > end_ts:
        raise ValueError("开始日期不能晚于结束日期。")
    period = Period(start_ts, end_ts)
    current = _slice(frame, period)
    if current.empty:
        raise ValueError("所选日期范围内没有数据。")

    valid_dimensions = tuple(dimension for dimension in dimensions if dimension in DIMENSIONS)
    metrics = calculate_metrics(current)
    comparisons = _metric_comparisons(frame, current, period)
    breakdowns = {dimension: _breakdown(current, dimension) for dimension in valid_dimensions if dimension in current.columns}
    previous_period = _comparison_periods(period)["环比"]
    previous = _slice(frame, previous_period)
    contributions = {
        dimension: _contribution(current, previous, dimension)
        for dimension in valid_dimensions
        if dimension in current.columns
    }
    anomalies = _detect_anomalies(current)
    missing = [metric.label for metric in metrics.values() if not metric.available]
    notes = [
        "环比使用所选区间之前、天数相同的连续区间；同比使用上年同期。仅在对应区间存在可比数据时计算。",
        "CVR 口径为订单量 / 点击量；ROI 口径为 GMV / 广告花费；退款率口径为退款订单量 / 订单量。",
        "若上传的是聚合数据，UV 等可加指标会按行求和；跨商品或渠道存在访客重叠时，应上传访客ID以获得去重结果。",
        "异常规则：至少需要 7 个有值日期；稳健 Z 分数不低于 3，或单日变化绝对值不低于 30%。",
    ]
    if missing:
        notes.append(f"本次缺少必要字段而不可计算的指标：{'、'.join(missing)}。系统未补值或伪造。")
    report = _build_report(period, metrics, comparisons, contributions, anomalies, notes)
    return AnalysisResult(
        period=period,
        current_data=current,
        metrics=metrics,
        comparisons=comparisons,
        breakdowns=breakdowns,
        contributions=contributions,
        anomalies=anomalies,
        report_markdown=report,
        notes=notes,
    )
