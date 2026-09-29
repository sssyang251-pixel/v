"""CSV/Excel ingestion and data-quality checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, TextIO

import pandas as pd

from .schema import NUMERIC_FIELDS, canonical_name


@dataclass
class DataBundle:
    frame: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    source_name: str = "uploaded_data"


def _read_csv(source: str | Path | BinaryIO | TextIO) -> pd.DataFrame:
    try:
        return pd.read_csv(source, encoding="utf-8-sig")
    except UnicodeDecodeError:
        if hasattr(source, "seek"):
            source.seek(0)
        return pd.read_csv(source, encoding="gb18030")


def load_data(
    source: str | Path | BinaryIO | TextIO,
    filename: str | None = None,
    sheet_name: str | int = 0,
) -> DataBundle:
    """Load and normalize CSV/XLS/XLSX data without inventing absent fields."""

    source_name = filename or getattr(source, "name", None) or str(source)
    suffix = Path(source_name).suffix.lower()
    if suffix == ".csv":
        raw = _read_csv(source)
    elif suffix in {".xlsx", ".xls"}:
        raw = pd.read_excel(source, sheet_name=sheet_name)
    else:
        raise ValueError("仅支持 .csv、.xlsx 或 .xls 文件。")

    if raw.empty:
        raise ValueError("文件中没有可分析的数据。")

    renamed = [canonical_name(column) for column in raw.columns]
    duplicates = sorted({name for name in renamed if renamed.count(name) > 1})
    if duplicates:
        raise ValueError(f"多个源字段映射到了同一标准字段：{', '.join(duplicates)}。请保留其中一列。")

    frame = raw.copy()
    frame.columns = renamed
    warnings: list[str] = []

    if "date" not in frame.columns:
        raise ValueError("缺少日期字段。请提供 date、日期、统计日期、下单日期或支付日期。")

    parsed_dates = pd.to_datetime(frame["date"], errors="coerce")
    invalid_dates = int(parsed_dates.isna().sum())
    if invalid_dates:
        warnings.append(f"已排除 {invalid_dates} 行无法识别的日期。")
    frame["date"] = parsed_dates.dt.normalize()
    frame = frame.loc[frame["date"].notna()].copy()
    if frame.empty:
        raise ValueError("日期字段均无法识别，没有可分析的数据。")

    for column in sorted(NUMERIC_FIELDS.intersection(frame.columns)):
        original_nonblank = frame[column].notna()
        converted = pd.to_numeric(frame[column], errors="coerce")
        invalid = int((original_nonblank & converted.isna()).sum())
        if invalid:
            warnings.append(f"字段 {column} 有 {invalid} 个非数值内容，计算时按缺失值处理。")
        negative = int((converted < 0).fillna(False).sum())
        if negative:
            warnings.append(f"字段 {column} 有 {negative} 个负值，请确认是否为冲销记录。")
        frame[column] = converted

    if "is_refunded" in frame.columns:
        truthy = {"1", "true", "yes", "y", "是", "已退款", "退款成功", "部分退款"}
        frame["is_refunded"] = frame["is_refunded"].map(
            lambda value: str(value).strip().lower() in truthy if pd.notna(value) else False
        )

    frame = frame.sort_values("date").reset_index(drop=True)
    return DataBundle(frame=frame, warnings=warnings, source_name=Path(source_name).name)

