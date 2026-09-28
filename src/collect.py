# -*- coding: utf-8 -*-
"""采集与归档层。

离线优先：默认读取 data/vendors.json 与 data/trends.json（已人工归档的公开信息），
合并成一份带校验结果的 collected.json。在线采集为可选增强（默认关闭），
避免引入反爬、频率控制与版权风险。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema import coverage_report, validate_dataset  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect(vendors_path: str, trends_path: str) -> dict:
    vendors = load_json(vendors_path)
    trends = load_json(trends_path)

    dataset = {
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": vendors.get("as_of"),
        "schema_version": vendors.get("schema_version"),
        "rules": vendors.get("rules", []),
        "vendor_count": len(vendors.get("vendors", [])),
        "vendors": vendors.get("vendors", []),
        "trends": trends.get("categories", {}),
        "trend_count": sum(len(v) for v in trends.get("categories", {}).values()),
    }
    dataset["quality"] = coverage_report(dataset["vendors"])
    dataset["validation_errors"] = validate_dataset(dataset)
    return dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="采集并归档公开信息")
    parser.add_argument("--vendors", default=os.path.join(DATA, "vendors.json"))
    parser.add_argument("--trends", default=os.path.join(DATA, "trends.json"))
    parser.add_argument("--out", default=os.path.join(DATA, "collected.json"))
    args = parser.parse_args()

    dataset = collect(args.vendors, args.trends)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    q = dataset["quality"]
    print(f"厂商: {q['vendors']}  趋势条目: {dataset['trend_count']}")
    print("字段覆盖率:")
    for field, ratio in q["coverage"].items():
        print(f"  {field:<14} {ratio:.0%}")
    print(f"显式声明 unknown 的厂商: {q['with_unknown_declared']}/{q['vendors']}")
    print(f"带来源编号的厂商: {q['with_sources']}/{q['vendors']}")

    if dataset["validation_errors"]:
        print("\n校验告警:")
        for err in dataset["validation_errors"]:
            print("  !", err)
        return 1
    print("\n校验通过，已写入:", os.path.relpath(args.out, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
