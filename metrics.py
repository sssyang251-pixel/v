"""Traceable e-commerce metric calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class MetricResult:
    key: str
    label: str
    value: float | None
    unit: str
    definition: str
    available: bool
    reason: str | None = None


METRIC_LABELS = {
    "gmv": "GMV",
    "orders": "订单量",
    "units_sold": "销量",
    "aov": "客单价",
    "uv": "UV",
    "ctr": "CTR",
    "cvr": "CVR",
    "refund_rate": "退款率",
    "roi": "ROI",
}

METRIC_UNITS = {
    "gmv": "currency",
    "orders": "count",
    "units_sold": "count",
    "aov": "currency",
    "uv": "count",
    "ctr": "rate",
    "cvr": "rate",
    "refund_rate": "rate",
    "roi": "ratio",
}

METRIC_DEFINITIONS = {
    "gmv": "GMV = 成交金额求和",
    "orders": "订单量 = 订单ID去重数；没有订单ID时使用订单量字段求和",
    "units_sold": "销量 = 销售件数求和",
    "aov": "客单价 = GMV / 订单量",
    "uv": "UV = 访客ID去重数；没有访客ID时使用UV字段求和",
    "ctr": "CTR = 点击量 / 曝光量",
    "cvr": "CVR = 订单量 / 点击量",
    "refund_rate": "退款率 = 退款订单量 / 订单量",
    "roi": "ROI = GMV / 广告花费",
}


def _sum(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns or not frame[column].notna().any():
        return None
    return float(frame[column].sum(min_count=1))


def order_count(frame: pd.DataFrame) -> float | None:
    if "order_id" in frame.columns and frame["order_id"].notna().any():
        return float(frame["order_id"].dropna().nunique())
    return _sum(frame, "order_count")


def visitor_count(frame: pd.DataFrame) -> float | None:
    if "visitor_id" in frame.columns and frame["visitor_id"].notna().any():
        return float(frame["visitor_id"].dropna().nunique())
    return _sum(frame, "visitors")


def refunded_order_count(frame: pd.DataFrame) -> float | None:
    direct = _sum(frame, "refund_order_count")
    if direct is not None:
        return direct
    if "is_refunded" not in frame.columns:
        return None
    refunded = frame.loc[frame["is_refunded"].fillna(False)]
    if "order_id" in refunded.columns and refunded["order_id"].notna().any():
        return float(refunded["order_id"].dropna().nunique())
    return float(len(refunded))


def _ratio(numerator: float | None, denominator: float | None) -> tuple[float | None, str | None]:
    if numerator is None or denominator is None:
        return None, "缺少计算所需字段"
    if denominator == 0:
        return None, "分母为 0"
    return numerator / denominator, None


def calculate_metrics(frame: pd.DataFrame) -> dict[str, MetricResult]:
    gmv = _sum(frame, "gmv")
    orders = order_count(frame)
    units = _sum(frame, "units_sold")
    uv = visitor_count(frame)
    clicks = _sum(frame, "clicks")
    impressions = _sum(frame, "impressions")
    refunds = refunded_order_count(frame)
    spend = _sum(frame, "ad_spend")

    values: dict[str, tuple[float | None, str | None]] = {
        "gmv": (gmv, None if gmv is not None else "缺少 GMV/成交金额字段"),
        "orders": (orders, None if orders is not None else "缺少订单ID或订单量字段"),
        "units_sold": (units, None if units is not None else "缺少销量/销售件数字段"),
        "aov": _ratio(gmv, orders),
        "uv": (uv, None if uv is not None else "缺少访客ID或UV字段"),
        "ctr": _ratio(clicks, impressions),
        "cvr": _ratio(orders, clicks),
        "refund_rate": _ratio(refunds, orders),
        "roi": _ratio(gmv, spend),
    }

    return {
        key: MetricResult(
            key=key,
            label=METRIC_LABELS[key],
            value=value,
            unit=METRIC_UNITS[key],
            definition=METRIC_DEFINITIONS[key],
            available=value is not None,
            reason=reason if value is None else None,
        )
        for key, (value, reason) in values.items()
    }


def metrics_as_row(frame: pd.DataFrame) -> dict[str, float | None]:
    return {key: result.value for key, result in calculate_metrics(frame).items()}

