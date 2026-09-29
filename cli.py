"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ecom_agent import analyze, load_data
from ecom_agent.export import export_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="电商运营数据分析 Agent")
    parser.add_argument("--input", default="data/sample_ecommerce_data.csv", help="CSV/XLS/XLSX 文件路径")
    parser.add_argument("--sheet", default=0, help="Excel 工作表名称或序号，默认第一张表")
    parser.add_argument("--start", help="分析开始日期 YYYY-MM-DD，默认最近30天")
    parser.add_argument("--end", help="分析结束日期 YYYY-MM-DD，默认数据最新日期")
    parser.add_argument("--output", default="demo_output", help="报告输出目录")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args()
    sheet = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
    bundle = load_data(args.input, sheet_name=sheet)
    result = analyze(bundle.frame, start=args.start, end=args.end)
    files = export_result(result, args.output)
    print(result.report_markdown)
    if bundle.warnings:
        print("数据质量提醒：")
        for warning in bundle.warnings:
            print(f"- {warning}")
    print(f"已输出 {len(files)} 个文件到 {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
