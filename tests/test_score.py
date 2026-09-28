# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from score import DEFAULT_SCENARIO, _ai_score, _standard_score, run, score_vendor  # noqa: E402


class TestDimensionScores(unittest.TestCase):
    def test_standard_score_exact_hits(self):
        v = {"standards": ["PDT", "LTE", "5G", "DMR"]}
        self.assertEqual(_standard_score(v, ["PDT", "LTE", "5G", "DMR"]), 1.0)

    def test_standard_score_broadband_partial_credit(self):
        # 只有 5G 时，LTE / 5G-R 视为部分替代
        v = {"standards": ["PDT", "5G", "DMR"]}
        score = _standard_score(v, ["PDT", "LTE", "5G", "DMR"])
        self.assertGreater(score, 0.75)
        self.assertLess(score, 1.0)

    def test_ai_unknown_scores_zero(self):
        self.assertEqual(_ai_score({"ai_features": ["unknown"]}), 0.0)
        self.assertEqual(_ai_score({}), 0.0)

    def test_ai_strategy_scores_full(self):
        self.assertEqual(_ai_score({"ai_features": ["AI 专网战略（2026-04 发布）"]}), 1.0)

    def test_missing_broadband_is_zero_not_average(self):
        # 关键设计：缺失按 0 计，不用均值填充（避免"看起来还行"的假数据）
        v = {"standards": ["PDT"], "segments": ["公共安全"], "ai_features": ["unknown"], "channel": "", "broadband": "unknown"}
        dims = score_vendor(v, DEFAULT_SCENARIO)["dims"]
        self.assertEqual(dims["broadband"], 0.0)
        self.assertEqual(dims["channel"], 0.0)


class TestRun(unittest.TestCase):
    def setUp(self):
        self.dataset = {
            "as_of": "2026-09-28",
            "vendors": [
                {
                    "id": "hytera", "name": "海能达", "country": "中国",
                    "standards": ["TETRA", "DMR", "PDT"], "segments": ["公共安全", "应急管理", "轨道交通"],
                    "ai_features": ["AI 专网战略"], "channel": "全球渠道伙伴计划，120+ 国家", "broadband": True,
                },
                {
                    "id": "tait", "name": "Tait", "country": "新西兰",
                    "standards": ["P25", "DMR"], "segments": ["公共安全"],
                    "ai_features": ["unknown"], "channel": "区域渠道", "broadband": False,
                },
            ],
        }

    def test_ranking_sorted_desc(self):
        result = run(self.dataset, DEFAULT_SCENARIO)
        totals = [s["total"] for s in result["ranking"]]
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_gap_uses_hytera_as_benchmark(self):
        result = run(self.dataset, DEFAULT_SCENARIO)
        self.assertEqual(len(result["gap_vs_hytera"]), 1)
        self.assertEqual(result["gap_vs_hytera"][0]["vs"], "Tait")
        self.assertGreater(result["gap_vs_hytera"][0]["gap"], 0)

    def test_score_bounds(self):
        for s in run(self.dataset, DEFAULT_SCENARIO)["ranking"]:
            self.assertGreaterEqual(s["total"], 0.0)
            self.assertLessEqual(s["total"], 1.0)


if __name__ == "__main__":
    unittest.main()
