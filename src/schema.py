# -*- coding: utf-8 -*-
"""能力矩阵的字段定义与校验。

设计原则：
1. 字段缺失必须显式写 "unknown"，禁止用推测值填充（情报工作里，比"缺"更危险的是"看不出是猜的"）。
2. 市场份额允许一个厂商存在多个口径，不强行统一。
3. 任何事实性内容必须带 sources 编号，可回溯到 data/sources.md。
"""
from __future__ import annotations

STANDARD_ENUM = [
    "TETRA", "DMR", "PDT", "P25", "NXDN", "5G-R",
    "LTE", "5G", "卫星（天通/低轨/北斗）", "6G 无蜂窝（研发中）",
]

REQUIRED_FIELDS = [
    "id", "name", "country", "standards",
    "narrowband", "broadband", "segments",
    "ai_features", "channel", "market_share", "facts", "unknown", "sources",
]

# 定位评分使用的维度权重（经验值，需用客户反馈回测校准）
SCORE_WEIGHTS = {
    "standard_coverage": 0.30,   # 标准覆盖广度（能否满足多制式招标要求）
    "segment_coverage": 0.25,    # 行业覆盖广度（政企/能源/交通/工商业）
    "ai_capability": 0.20,       # AI 能力成熟度（差异化卖点）
    "broadband": 0.15,           # 宽带/公专融合能力
    "channel": 0.10,             # 渠道与交付网络
}

UNKNOWN = "unknown"


def is_unknown(value) -> bool:
    """判断字段是否被显式标记为未知（含字符串 unknown / 空列表 / 缺失）。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() == UNKNOWN or value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0 or all(is_unknown(v) for v in (value.values() if isinstance(value, dict) else value))
    return False


def validate_vendor(vendor: dict) -> list[str]:
    """校验单个厂商记录，返回错误信息列表（空列表 = 通过）。"""
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in vendor:
            errors.append(f"缺少必需字段: {field}")

    if not vendor.get("sources"):
        errors.append("sources 为空：任何事实都必须可回溯到来源编号")

    for std in vendor.get("standards", []):
        if std not in STANDARD_ENUM:
            errors.append(f"标准不在枚举内: {std}")

    # unknown 字段必须是非空列表（显式声明"哪些还没查到"）
    if "unknown" in vendor and not isinstance(vendor["unknown"], list):
        errors.append("unknown 字段必须是列表，用于显式声明未采集到的信息")

    # 市场份额多口径：值可以是字符串或字典，但不能整体为空
    if is_unknown(vendor.get("market_share")):
        errors.append("market_share 未采集：如确实无公开口径，请写 {'note': '暂无公开口径'}")

    return errors


def coverage_report(vendors: list[dict]) -> dict:
    """统计字段覆盖率——用来量化"这份情报到底有多完整"。"""
    total = len(vendors)
    if total == 0:
        return {"vendors": 0}

    def filled(field: str) -> int:
        return sum(1 for v in vendors if not is_unknown(v.get(field)))

    return {
        "vendors": total,
        "coverage": {
            field: round(filled(field) / total, 3)
            for field in ["standards", "segments", "ai_features", "channel", "market_share", "broadband", "narrowband"]
        },
        "with_unknown_declared": sum(1 for v in vendors if v.get("unknown")),
        "with_sources": sum(1 for v in vendors if v.get("sources")),
    }


def validate_dataset(dataset: dict) -> list[str]:
    """校验整份数据集，返回按厂商聚合的错误列表。"""
    problems: list[str] = []
    vendors = dataset.get("vendors", [])
    if not vendors:
        problems.append("数据集为空")
    seen_ids: set[str] = set()
    for v in vendors:
        vid = v.get("id", "<no-id>")
        if vid in seen_ids:
            problems.append(f"[{vid}] id 重复")
        seen_ids.add(vid)
        for err in validate_vendor(v):
            problems.append(f"[{vid}] {err}")
    return problems
