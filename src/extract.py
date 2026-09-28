# -*- coding: utf-8 -*-
"""抽取与归因层。

两种模式：
  rule —— 关键词/规则抽取，零依赖、结果可复现（默认，面试演示用这个）
  llm  —— 走 OpenAI 兼容接口做规格抽取与差异归因；未配置 key 时自动降级为 rule

输出：data/extracted.json（能力标签 + 差异化归因 + 抽取统计）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# 能力标签规则：命中关键词即打标。写死规则而不是靠模型，是为了"可解释、可复算"。
CAPABILITY_RULES = [
    ("中国自主标准", ["PDT"]),
    ("欧美主流标准", ["TETRA", "P25"]),
    ("数字对讲标准", ["DMR", "NXDN"]),
    ("宽带/专网演进", ["5G", "LTE", "5G-R", "宽带"]),
    ("空天地/多模融合", ["卫星", "低空", "6G"]),
    ("AI 化能力", ["AI", "大模型", "智能"]),
    ("极端环境适配", ["防爆", "ATEX", "IECEx"]),
    ("公共安全基本盘", ["公共安全", "公安", "应急"]),
    ("行业多元化", ["能源", "轨道交通", "工商业", "工业", "矿业"]),
    ("渠道/生态", ["渠道", "分销", "伙伴", "集成商"]),
]


def rule_extract(vendor: dict) -> dict:
    """规则抽取：把厂商记录压成能力标签 + 命中证据。"""
    haystack = " ".join(
        [
            " ".join(vendor.get("standards", [])),
            " ".join(vendor.get("segments", [])),
            " ".join(v if isinstance(v, str) else "" for v in vendor.get("ai_features", [])),
            " ".join(vendor.get("facts", [])),
            str(vendor.get("channel", "")),
        ]
    )

    tags: list[str] = []
    evidence: dict[str, str] = {}
    for tag, keywords in CAPABILITY_RULES:
        for kw in keywords:
            if kw in haystack:
                tags.append(tag)
                # 记录命中片段，供人工核对（防止"标签飘在空中"）
                m = re.search(rf"[^。；;]*{re.escape(kw)}[^。；;]*", haystack)
                evidence[tag] = (m.group(0).strip() if m else kw)[:120]
                break

    return {
        "id": vendor.get("id"),
        "name": vendor.get("name"),
        "tags": tags,
        "tag_count": len(tags),
        "evidence": evidence,
        "unknown_fields": vendor.get("unknown", []),
    }


def build_llm_prompt(vendor: dict, trends: dict) -> str:
    """构造抽取提示词。注意：只喂公开归档数据，不喂任何内部资料。"""
    payload = {
        "vendor": {
            "name": vendor.get("name"),
            "standards": vendor.get("standards"),
            "segments": vendor.get("segments"),
            "ai_features": vendor.get("ai_features"),
            "facts": vendor.get("facts"),
            "market_share": vendor.get("market_share"),
        },
        "trend_categories": list((trends or {}).keys()),
    }
    return (
        "你是专网通信行业的市场分析助手。下面是一家厂商的公开信息（JSON）。\n"
        "请只基于给定信息输出 JSON，格式：\n"
        '{"capability_tags": ["..."], "differentiation": "一句话差异化定位", '
        '"risk_note": "一句话风险或限制", "evidence_quotes": [{"tag": "...", "quote": "..."}]}\n'
        "要求：不确定的内容写 unknown，不要推测；不要引入输入中不存在的事实。\n\n"
        f"输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def llm_extract(vendor: dict, trends: dict, timeout: int = 30) -> dict | None:
    """调用 OpenAI 兼容接口。未配置 key 或调用失败时返回 None（由调用方降级）。"""
    api_key = os.environ.get("MARKET_INTEL_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    base = os.environ.get("MARKET_INTEL_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    model = os.environ.get("MARKET_INTEL_MODEL", "gpt-4o-mini")

    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": build_llm_prompt(vendor, trends)}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{base.rstrip('/')}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        parsed["id"] = vendor.get("id")
        parsed["name"] = vendor.get("name")
        parsed["mode"] = "llm"
        return parsed
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:  # 网络/格式异常一律降级
        print(f"  [warn] LLM 抽取失败，降级为 rule 模式: {exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="抽取能力标签与差异化归因")
    parser.add_argument("--mode", choices=["rule", "llm"], default="rule")
    parser.add_argument("--in", dest="infile", default=os.path.join(DATA, "collected.json"))
    parser.add_argument("--out", default=os.path.join(DATA, "extracted.json"))
    args = parser.parse_args()

    with open(args.infile, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    trends = dataset.get("trends", {})
    results = []
    used_mode = args.mode

    for vendor in dataset.get("vendors", []):
        item = None
        if args.mode == "llm":
            item = llm_extract(vendor, trends)
            if item is None:
                used_mode = "rule(降级)"
        if item is None:
            item = rule_extract(vendor)
            item["mode"] = "rule"
        results.append(item)

    out = {
        "as_of": dataset.get("as_of"),
        "mode": used_mode,
        "vendors": results,
        "stats": {
            "vendor_count": len(results),
            "avg_tags": round(sum(r["tag_count"] for r in results) / max(len(results), 1), 2),
            "top_tags": _top_tags(results),
        },
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"模式: {used_mode}  厂商: {len(results)}  平均标签数: {out['stats']['avg_tags']}")
    print("高频能力标签:", "、".join(f"{k}({v})" for k, v in out["stats"]["top_tags"][:6]))
    print("已写入:", os.path.relpath(args.out, ROOT))
    return 0


def _top_tags(results: list[dict]) -> list[tuple[str, int]]:
    counter: dict[str, int] = {}
    for r in results:
        for tag in r.get("tags", []):
            counter[tag] = counter.get(tag, 0) + 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


if __name__ == "__main__":
    raise SystemExit(main())
