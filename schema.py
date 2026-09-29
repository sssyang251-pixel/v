"""Canonical fields and aliases used by the analytics engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    canonical: str
    label: str
    aliases: tuple[str, ...]
    numeric: bool = False


FIELDS = (
    FieldSpec("date", "日期", ("date", "日期", "统计日期", "下单日期", "支付日期")),
    FieldSpec("order_id", "订单ID", ("order_id", "订单id", "订单号", "订单编号")),
    FieldSpec("order_count", "订单量", ("order_count", "orders", "订单量", "订单数", "支付订单数"), True),
    FieldSpec("units_sold", "销量", ("units_sold", "quantity", "qty", "销量", "销售件数", "商品件数"), True),
    FieldSpec("gmv", "GMV", ("gmv", "sales_amount", "revenue", "成交金额", "支付金额", "销售额"), True),
    FieldSpec("visitor_id", "访客ID", ("visitor_id", "user_id", "访客id", "用户id", "买家id")),
    FieldSpec("visitors", "UV", ("visitors", "uv", "访客数", "商品访客数", "独立访客数"), True),
    FieldSpec("impressions", "曝光量", ("impressions", "impression", "曝光量", "展现量"), True),
    FieldSpec("clicks", "点击量", ("clicks", "click", "点击量", "商品点击数"), True),
    FieldSpec(
        "refund_order_count",
        "退款订单量",
        ("refund_order_count", "refunded_orders", "退款订单量", "退款订单数"),
        True,
    ),
    FieldSpec("is_refunded", "是否退款", ("is_refunded", "refunded", "是否退款", "退款状态")),
    FieldSpec("refund_amount", "退款金额", ("refund_amount", "退款金额", "退款额"), True),
    FieldSpec("ad_spend", "广告花费", ("ad_spend", "spend", "cost", "广告花费", "投放消耗", "投放金额"), True),
    FieldSpec("product", "商品", ("product", "product_name", "sku", "商品", "商品名称", "商品id", "sku名称")),
    FieldSpec("channel", "渠道", ("channel", "source", "渠道", "流量来源", "平台")),
    FieldSpec("creator", "达人", ("creator", "influencer", "达人", "达人昵称", "达人名称")),
)

ALIAS_TO_CANONICAL = {
    alias.strip().lower(): field.canonical
    for field in FIELDS
    for alias in (field.canonical, *field.aliases)
}
NUMERIC_FIELDS = {field.canonical for field in FIELDS if field.numeric}
DIMENSIONS = ("date", "product", "channel", "creator")
DIMENSION_LABELS = {"date": "日期", "product": "商品", "channel": "渠道", "creator": "达人"}


def canonical_name(name: object) -> str:
    """Map a source column to a canonical field, preserving unknown columns."""

    cleaned = str(name).strip()
    return ALIAS_TO_CANONICAL.get(cleaned.lower(), cleaned)

