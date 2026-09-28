# -*- coding: utf-8 -*-
"""报告层：把矩阵、趋势、质量分合成一份可演示的 HTML（自包含、无外部依赖）。"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

CSS = """
:root{--ink:#16202c;--muted:#5b6b7c;--line:#dfe6ee;--bg:#f6f8fb;--card:#fff;--brand:#0f5bd7;--ok:#1a7f4b;--warn:#b06a00;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.7 "Microsoft YaHei","Segoe UI",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:32px 22px 60px}
h1{font-size:24px;margin:0 0 6px}
h2{font-size:17px;margin:34px 0 12px;padding-left:10px;border-left:4px solid var(--brand)}
.sub{color:var(--muted);font-size:13px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
th{background:#eef3f9;font-weight:600;color:#2b3a4a;white-space:nowrap}
td.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.bar{height:8px;border-radius:4px;background:#e6edf6;position:relative;min-width:110px}
.bar>i{position:absolute;inset:0 auto 0 0;border-radius:4px;background:var(--brand)}
.tag{display:inline-block;padding:1px 7px;border-radius:10px;background:#eaf1fd;color:#1a4fa8;font-size:12px;margin:2px 4px 2px 0}
.muted{color:var(--muted);font-size:12.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi b{display:block;font-size:22px;color:var(--brand)}
ul{margin:8px 0 0 18px;padding:0}
li{margin:4px 0}
.warn{border-left:4px solid var(--warn);background:#fff8ec;padding:12px 16px;border-radius:8px}
footer{margin-top:34px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);padding-top:14px}
"""


def _bar(value: float, maximum: float = 1.0) -> str:
    pct = 0 if maximum <= 0 else max(0.0, min(value / maximum, 1.0)) * 100
    return f'<div class="bar"><i style="width:{pct:.1f}%"></i></div>'


def _kpi(label: str, value: str) -> str:
    return f'<div class="kpi"><b>{html.escape(value)}</b><span class="muted">{html.escape(label)}</span></div>'


def build_html(collected: dict, score: dict, extracted: dict | None) -> str:
    quality = collected.get("quality", {})
    scenario = score.get("scenario", {})

    rows = []
    for s in score.get("ranking", []):
        rows.append(
            "<tr>"
            f"<td>{html.escape(s['name'])}</td>"
            f"<td>{html.escape(str(s['country']))}</td>"
            f"<td>{html.escape(s['standards'])}</td>"
            f"<td>{_bar(s['dims']['standard_coverage'])}</td>"
            f"<td>{_bar(s['dims']['segment_coverage'])}</td>"
            f"<td>{_bar(s['dims']['ai_capability'])}</td>"
            f"<td>{_bar(s['dims']['broadband'])}</td>"
            f'<td class="num">{s["score_100"]}</td>'
            "</tr>"
        )

    trends_html = []
    labels = {"policy": "政策与标准", "technology": "技术路线", "demand": "需求结构"}
    for key, items in collected.get("trends", {}).items():
        lis = "".join(
            f"<li><b>{html.escape(i['title'])}</b> —— {html.escape(i['detail'])}"
            f'<div class="muted">影响：{html.escape(i.get("impact", ""))}（来源 {", ".join(i.get("sources", []))}）</div></li>'
            for i in items
        )
        trends_html.append(f"<h3>{labels.get(key, key)}</h3><ul>{lis}</ul>")

    gaps_html = "".join(
        f"<li>{html.escape(g['vs'])}：{'领先' if g['gap'] > 0 else '落后'} {abs(g['gap']):.3f}"
        f'<span class="muted">（相对基准厂商）</span></li>'
        for g in score.get("gap_vs_hytera", [])
    )

    tags_html = ""
    if extracted:
        tags_html = "".join(f'<span class="tag">{html.escape(t)}×{c}</span>' for t, c in extracted.get("stats", {}).get("top_tags", [])[:10])

    coverage = quality.get("coverage", {})
    cov_html = "".join(f"<li>{html.escape(k)}：{v:.0%}</li>" for k, v in coverage.items())

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>专网通信市场情报与竞品分析报告</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>专网通信市场情报与竞品分析报告</h1>
<div class="sub">数据截至 {html.escape(str(collected.get('as_of')))} · 报告生成 {datetime.now().strftime('%Y-%m-%d %H:%M')} · 全部数据来自公开信息（见 data/sources.md）</div>

<div class="grid">
  {_kpi("覆盖厂商", str(quality.get("vendors", 0)))}
  {_kpi("趋势/政策条目", str(collected.get("trend_count", 0)))}
  {_kpi("场景画像", scenario.get("name", "-")[:14])}
  {_kpi("抽取模式", (extracted or {}).get("mode", "-"))}
</div>

<h2>1. 场景画像与评分口径</h2>
<div class="card">
<p>{html.escape(scenario.get("name", ""))}</p>
<p class="muted">必须支持的标准：{html.escape("、".join(scenario.get("standards_required", [])))}　|　
必须覆盖行业：{html.escape("、".join(scenario.get("segments_required", [])))}　|　
是否要求宽带/公专融合：{"是" if scenario.get("broadband_required") else "否"}</p>
<p class="muted">权重：{html.escape("；".join(f"{k} {v:.0%}" for k, v in score.get("weights", {}).items()))}
　（权重为经验值，需用真实客户反馈回测校准）</p>
</div>

<h2>2. 能力矩阵与匹配度排名</h2>
<div class="card">
<table>
<thead><tr><th>厂商</th><th>国家/地区</th><th>标准支持</th><th>标准覆盖</th><th>行业覆盖</th><th>AI 能力</th><th>宽带/公专融合</th><th>百分制</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p class="muted">说明：条形为各维度归一化得分（0–100%），百分制为加权总分。缺失字段按 0 计，而非按行业均值填充——宁可低估，不做假。</p>
</div>

<h2>3. 相对基准厂商的差距</h2>
<div class="card"><ul>{gaps_html}</ul></div>

<h2>4. 行业趋势与政策（结构化摘录）</h2>
<div class="card">{''.join(trends_html)}</div>

<h2>5. 数据质量</h2>
<div class="card">
<ul>{cov_html}</ul>
<p class="muted">显式声明 unknown 的厂商：{quality.get("with_unknown_declared", 0)}/{quality.get("vendors", 0)}　|　
带来源编号：{quality.get("with_sources", 0)}/{quality.get("vendors", 0)}</p>
</div>

<h2>6. 能力标签分布</h2>
<div class="card">{tags_html or '<span class="muted">未运行 extract.py</span>'}</div>

<h2>7. 结论与局限</h2>
<div class="warn">
<b>结论</b>
<ul>
<li>行业赛道结构性分化：窄带为存量基本盘，宽带智能专网为增量与高毛利来源，售前交付能力是核心壁垒。</li>
<li>标准覆盖是政企准入的硬门槛：同时具备窄带（PDT/DMR/TETRA）与宽带（LTE/5G）能力的厂商才谈得上"综合解决方案"。</li>
<li>AI 能力当前仍处"叙事领先于落地"阶段，谁能把算法指标翻译成指挥调度的业务价值，谁在标书里占优。</li>
</ul>
<b>局限</b>
<ul>
<li>份额数据存在多来源多口径，未做统一，仅并列呈现。</li>
<li>产品级规格缺官方链接的内容已标 unknown，未用推测值填充。</li>
<li>评分权重为经验值；场景画像为示意，真实项目需替换为客户招标文件的具体要求。</li>
</ul>
</div>

<footer>本报告为个人学习与研究用途的 POC 产出，不代表任何厂商官方口径。数据来源见 data/sources.md。</footer>
</div></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 HTML 报告")
    parser.add_argument("--collected", default=os.path.join(DATA, "collected.json"))
    parser.add_argument("--score", default=os.path.join(DATA, "score.json"))
    parser.add_argument("--extracted", default=os.path.join(DATA, "extracted.json"))
    parser.add_argument("--out", default=os.path.join(ROOT, "report.html"))
    args = parser.parse_args()

    with open(args.collected, "r", encoding="utf-8") as f:
        collected = json.load(f)
    with open(args.score, "r", encoding="utf-8") as f:
        score = json.load(f)
    extracted = None
    if os.path.exists(args.extracted):
        with open(args.extracted, "r", encoding="utf-8") as f:
            extracted = json.load(f)

    html_text = build_html(collected, score, extracted)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_text)
    print("报告已生成:", os.path.relpath(args.out, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
