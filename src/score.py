# -*- coding: utf-8 -*-
"""定位评分：按统一口径给每家厂商打分，输出能力矩阵（CSV）与评分明细（JSON）。

评分不是"谁更好"，而是"针对某类招标场景，谁的匹配度更高"。
因此场景画像（必须支持的标准、必须覆盖的行业）是可配置的输入，不是写死的结论。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema import SCORE_WEIGHTS, UNKNOWN, is_unknown  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# 场景画像：一个典型的"省市级应急通信 + 公共安全"项目会对厂商提什么要求
DEFAULT_SCENARIO = {
    "name": "省市级应急通信与公共安全项目（示意画像）",
    "standards_required": ["PDT", "LTE", "5G", "DMR"],
    "segments_required": ["公共安全", "应急管理", "轨道交通", "能源", "工商业"],
    "broadband_required": True,
}


def _standard_score(vendor: dict, required: list[str]) -> float:
    have = {s for s in vendor.get("standards", []) if s != UNKNOWN}
    if not required:
        return 0.0
    # 宽带类标准允许 5G / LTE / 5G-R 互相部分替代，按 0.5 计（避免"只有 5G 没有 LTE 直接为零"）
    hit = 0.0
    for req in required:
        if req in have:
            hit += 1.0
        elif req in ("5G", "LTE", "5G-R") and have & {"5G", "LTE", "5G-R"}:
            hit += 0.5
    return round(min(hit / len(required), 1.0), 3)


def _segment_score(vendor: dict, required: list[str]) -> float:
    have = set(vendor.get("segments", []))
    if not required:
        return 0.0
    return round(len(have & set(required)) / len(required), 3)


def _ai_score(vendor: dict) -> float:
    feats = vendor.get("ai_features")
    if is_unknown(feats):
        return 0.0
    text = " ".join(feats) if isinstance(feats, list) else str(feats)
    if "unknown" in text.lower():
        return 0.0
    # 明确提到大模型/AI 专网战略视为强证据
    if any(k in text for k in ["大模型", "AI 专网", "战略"]):
        return 1.0
    return 0.6


def _broadband_score(vendor: dict) -> float:
    val = vendor.get("broadband")
    if val is True:
        return 1.0
    if isinstance(val, str) and val.lower() == UNKNOWN:
        return 0.0
    if val is False:
        return 0.0
    if is_unknown(val):
        return 0.0
    return 0.5


def _channel_score(vendor: dict) -> float:
    text = str(vendor.get("channel", ""))
    if not text or text.lower() == UNKNOWN:
        return 0.0
    score = 0.6
    if any(k in text for k in ["全球", "120", "伙伴计划"]):
        score += 0.2
    if any(k in text for k in ["渠道", "分销", "集成商"]):
        score += 0.2
    return round(min(score, 1.0), 3)


def score_vendor(vendor: dict, scenario: dict) -> dict:
    dims = {
        "standard_coverage": _standard_score(vendor, scenario["standards_required"]),
        "segment_coverage": _segment_score(vendor, scenario["segments_required"]),
        "ai_capability": _ai_score(vendor),
        "broadband": _broadband_score(vendor),
        "channel": _channel_score(vendor),
    }
    total = round(sum(dims[k] * w for k, w in SCORE_WEIGHTS.items()), 3)
    return {
        "id": vendor.get("id"),
        "name": vendor.get("name"),
        "country": vendor.get("country"),
        "standards": "/".join(vendor.get("standards", [])),
        "dims": dims,
        "total": total,
        "score_100": round(total * 100, 1),
    }


def run(dataset: dict, scenario: dict) -> dict:
    scores = [score_vendor(v, scenario) for v in dataset.get("vendors", [])]
    scores.sort(key=lambda s: -s["total"])

    benchmark = next((s for s in scores if s["id"] == "hytera"), None)
    gaps = []
    if benchmark:
        for s in scores:
            if s["id"] == "hytera":
                continue
            gaps.append(
                {
                    "vs": s["name"],
                    "gap": round(benchmark["total"] - s["total"], 3),
                    "note": "领先" if benchmark["total"] > s["total"] else "落后",
                }
            )

    return {
        "as_of": dataset.get("as_of"),
        "scenario": scenario,
        "weights": SCORE_WEIGHTS,
        "ranking": scores,
        "gap_vs_hytera": gaps,
    }


def write_csv(result: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["厂商", "国家/地区", "标准支持", "标准覆盖", "行业覆盖", "AI 能力", "宽带/公专融合", "渠道", "加权总分", "百分制"]
            + [f"权重_{k}" for k in SCORE_WEIGHTS]
        )
        for s in result["ranking"]:
            writer.writerow(
                [
                    s["name"], s["country"], s["standards"],
                    s["dims"]["standard_coverage"], s["dims"]["segment_coverage"],
                    s["dims"]["ai_capability"], s["dims"]["broadband"], s["dims"]["channel"],
                    s["total"], s["score_100"],
                ]
                + [SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="按场景画像计算厂商定位评分")
    parser.add_argument("--in", dest="infile", default=os.path.join(DATA, "collected.json"))
    parser.add_argument("--out", default=os.path.join(DATA, "capability_matrix.csv"))
    parser.add_argument("--json-out", default=os.path.join(DATA, "score.json"))
    args = parser.parse_args()

    with open(args.infile, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    result = run(dataset, DEFAULT_SCENARIO)
    write_csv(result, args.out)
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"场景：{DEFAULT_SCENARIO['name']}")
    print(f"{'厂商':<32}{'总分':>8}{'百分制':>8}")
    for s in result["ranking"]:
        print(f"{s['name'][:30]:<32}{s['total']:>8}{s['score_100']:>8}")
    print("\n已写入:", os.path.relpath(args.out, ROOT), "/", os.path.relpath(args.json_out, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
