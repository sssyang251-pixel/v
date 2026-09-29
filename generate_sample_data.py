"""Generate deterministic aggregate e-commerce demo data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def generate() -> pd.DataFrame:
    rng = np.random.default_rng(20260928)
    periods = [
        pd.date_range("2024-05-01", "2024-07-31", freq="D"),
        pd.date_range("2025-04-01", "2025-07-31", freq="D"),
    ]
    products = [
        ("便携榨汁杯", 79.0, 1.18),
        ("防晒冰袖", 29.9, 0.86),
        ("桌面风扇", 109.0, 1.05),
        ("旅行收纳包", 49.9, 0.72),
    ]
    channels = [
        ("抖音", "达人-晴晴", 1.30, 0.19),
        ("小红书", "达人-小林", 0.82, 0.12),
        ("自然流量", "无达人", 0.65, 0.00),
    ]
    rows = []
    for dates in periods:
        for date in dates:
            weekend = 1.12 if date.dayofweek >= 5 else 1.0
            seasonality = 1 + 0.16 * np.sin((date.dayofyear % 30) / 30 * 2 * np.pi)
            year_growth = 1.16 if date.year == 2025 else 1.0
            for product, price, product_factor in products:
                for channel, creator, channel_factor, spend_rate in channels:
                    base_impressions = 2400 * weekend * seasonality * year_growth * product_factor * channel_factor
                    if date >= pd.Timestamp("2025-07-22") and channel == "抖音":
                        base_impressions *= 0.78
                    if date >= pd.Timestamp("2025-07-15") and channel == "小红书":
                        base_impressions *= 1.22
                    impressions = max(50, int(rng.normal(base_impressions, base_impressions * 0.08)))
                    ctr = 0.075 + (0.012 if product == "便携榨汁杯" else 0) + rng.normal(0, 0.006)
                    clicks = max(1, int(impressions * max(0.025, ctr)))
                    cvr = 0.057 + (0.008 if channel == "自然流量" else 0) + rng.normal(0, 0.004)
                    if date >= pd.Timestamp("2025-07-22") and channel == "抖音":
                        cvr *= 0.70
                    orders = max(0, int(clicks * max(0.012, cvr)))
                    units = orders + int(rng.binomial(orders, 0.12)) if orders else 0
                    gmv = round(units * price * rng.uniform(0.92, 1.0), 2)
                    refund_rate = 0.055 + (0.07 if product == "桌面风扇" and date >= pd.Timestamp("2025-07-18") else 0)
                    refunded_orders = int(rng.binomial(orders, min(refund_rate, 0.35))) if orders else 0
                    ad_spend = round(impressions / 1000 * 18 * spend_rate + clicks * spend_rate * 0.42, 2)
                    rows.append(
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "product": product,
                            "channel": channel,
                            "creator": creator,
                            "impressions": impressions,
                            "clicks": clicks,
                            "visitors": int(clicks * rng.uniform(0.78, 0.92)),
                            "order_count": orders,
                            "units_sold": units,
                            "gmv": gmv,
                            "refund_order_count": refunded_orders,
                            "refund_amount": round(refunded_orders * price * 0.95, 2),
                            "ad_spend": ad_spend,
                        }
                    )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "data" / "sample_ecommerce_data.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = generate()
    data.to_csv(destination, index=False, encoding="utf-8-sig")
    print(f"Generated {len(data):,} rows: {destination}")
