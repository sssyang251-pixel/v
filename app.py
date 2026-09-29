"""Streamlit interface for the e-commerce analytics agent."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from ecom_agent import analyze, load_data
from ecom_agent.schema import DIMENSION_LABELS


PROJECT_ROOT = Path(__file__).parent
SAMPLE_FILE = PROJECT_ROOT / "data" / "sample_ecommerce_data.csv"


def format_metric(value: float | None, unit: str) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    if unit == "currency":
        return f"¥{value:,.0f}"
    if unit == "rate":
        return f"{value:.2%}"
    if unit == "ratio":
        return f"{value:.2f}"
    return f"{value:,.0f}"


def change_for(comparisons: pd.DataFrame, metric: str, comparison: str = "环比") -> float | None:
    rows = comparisons.loc[(comparisons["metric"] == metric) & (comparisons["comparison"] == comparison)]
    if rows.empty or not bool(rows.iloc[0]["available"]):
        return None
    value = rows.iloc[0]["change_rate"]
    return float(value) if pd.notna(value) else None


st.set_page_config(page_title="电商运营数据分析 Agent", page_icon="📊", layout="wide")
st.title("电商运营数据分析 Agent")

with st.sidebar:
    st.header("数据与筛选")
    uploaded = st.file_uploader("上传 CSV 或 Excel", type=["csv", "xlsx", "xls"])
    source = uploaded if uploaded is not None else SAMPLE_FILE
    source_name = uploaded.name if uploaded is not None else SAMPLE_FILE.name
    if uploaded is None:
        st.caption("当前使用内置模拟数据")

try:
    bundle = load_data(source, filename=source_name)
except Exception as exc:
    st.error(f"数据读取失败：{exc}")
    st.stop()

frame = bundle.frame
with st.sidebar:
    start_date, end_date = st.date_input(
        "分析日期范围",
        value=(max(frame["date"].min().date(), (frame["date"].max() - pd.Timedelta(days=29)).date()), frame["date"].max().date()),
        min_value=frame["date"].min().date(),
        max_value=frame["date"].max().date(),
    )
    filter_dimensions = [dimension for dimension in ("product", "channel", "creator") if dimension in frame.columns]
    filtered = frame.copy()
    for dimension in filter_dimensions:
        options = sorted(filtered[dimension].dropna().astype(str).unique().tolist())
        selected = st.multiselect(DIMENSION_LABELS[dimension], options, default=options)
        if selected:
            filtered = filtered.loc[filtered[dimension].astype(str).isin(selected)]

try:
    result = analyze(filtered, start=start_date, end=end_date, dimensions=tuple(filter_dimensions))
except Exception as exc:
    st.error(f"分析失败：{exc}")
    st.stop()

if bundle.warnings:
    with st.expander("数据质量提醒", expanded=True):
        for warning in bundle.warnings:
            st.warning(warning)

metric_keys = ["gmv", "orders", "units_sold", "aov", "uv", "ctr", "cvr", "refund_rate", "roi"]
for row_start in range(0, len(metric_keys), 5):
    columns = st.columns(5)
    for column, key in zip(columns, metric_keys[row_start : row_start + 5]):
        metric = result.metrics[key]
        delta = change_for(result.comparisons, key)
        delta_text = f"环比 {delta:+.1%}" if delta is not None else None
        column.metric(metric.label, format_metric(metric.value, metric.unit), delta=delta_text)
        if not metric.available:
            column.caption(metric.reason)

overview_tab, breakdown_tab, anomaly_tab, report_tab, quality_tab = st.tabs(
    ["趋势概览", "维度分析", "异常识别", "运营报告", "口径与质量"]
)

with overview_tab:
    daily = result.breakdowns.get("date")
    if daily is None:
        daily_rows = []
        for date, group in result.current_data.groupby("date"):
            from ecom_agent.metrics import metrics_as_row
            daily_rows.append({"date": date, **metrics_as_row(group)})
        daily = pd.DataFrame(daily_rows)
    if not daily.empty:
        daily = daily.copy()
        daily["date"] = pd.to_datetime(daily["date"])
        available_chart_metrics = [key for key in ("gmv", "orders", "ctr", "cvr", "refund_rate", "roi") if daily[key].notna().any()]
        chart_metric = st.selectbox("趋势指标", available_chart_metrics, format_func=lambda key: result.metrics[key].label)
        st.line_chart(daily.set_index("date")[[chart_metric]], height=340)
    comparable = result.comparisons.loc[result.comparisons["available"]].copy()
    st.subheader("环比 / 同比")
    if comparable.empty:
        st.info("没有对应历史数据，未计算环比或同比。")
    else:
        display = comparable[["comparison", "metric_label", "current", "reference", "change_rate", "reference_period"]].copy()
        st.dataframe(display, use_container_width=True, hide_index=True, column_config={"change_rate": st.column_config.NumberColumn("变化率", format="%.2f%%")})

with breakdown_tab:
    if not result.breakdowns:
        st.info("数据中没有商品、渠道或达人维度。")
    else:
        dimension = st.selectbox("分析维度", list(result.breakdowns), format_func=lambda item: DIMENSION_LABELS[item])
        table = result.breakdowns[dimension]
        st.dataframe(table, use_container_width=True, hide_index=True)
        if not table.empty and table["gmv"].notna().any():
            chart = table.head(12).set_index(dimension)[["gmv"]]
            st.bar_chart(chart, height=360)
        contribution = result.contributions.get(dimension)
        if contribution is not None and not contribution.empty:
            st.subheader("GMV 变化来源")
            st.dataframe(contribution.head(12), use_container_width=True, hide_index=True)

with anomaly_tab:
    if result.anomalies.empty:
        st.success("当前区间未触发异常规则，或有效日期不足 7 天。")
    else:
        st.dataframe(result.anomalies, use_container_width=True, hide_index=True)

with report_tab:
    st.markdown(result.report_markdown)
    st.download_button(
        "下载 Markdown 报告",
        data=result.report_markdown.encode("utf-8"),
        file_name="ecommerce_analysis_report.md",
        mime="text/markdown",
    )

with quality_tab:
    st.subheader("指标口径")
    definitions = pd.DataFrame(
        [{"指标": metric.label, "定义": metric.definition, "状态": "可计算" if metric.available else metric.reason} for metric in result.metrics.values()]
    )
    st.dataframe(definitions, use_container_width=True, hide_index=True)
    st.subheader("已识别字段")
    st.code(", ".join(frame.columns))
    for note in result.notes:
        st.caption(note)

