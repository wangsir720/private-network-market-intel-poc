# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from schema import coverage_report, is_unknown, validate_dataset, validate_vendor  # noqa: E402


def make_vendor(**overrides):
    vendor = {
        "id": "demo",
        "name": "示例厂商",
        "country": "中国",
        "standards": ["PDT", "DMR"],
        "narrowband": True,
        "broadband": False,
        "segments": ["公共安全"],
        "ai_features": ["unknown"],
        "channel": "渠道分销",
        "market_share": {"cn": "约 5%"},
        "facts": ["示例事实"],
        "unknown": ["宽带产品线"],
        "sources": ["S1"],
    }
    vendor.update(overrides)
    return vendor


class TestValidation(unittest.TestCase):
    def test_valid_vendor_passes(self):
        self.assertEqual(validate_vendor(make_vendor()), [])

    def test_missing_required_field(self):
        v = make_vendor()
        v.pop("channel")
        self.assertTrue(any("channel" in e for e in validate_vendor(v)))

    def test_missing_sources_is_error(self):
        # 没有来源编号 = 不可回溯，必须报错
        self.assertTrue(any("sources" in e for e in validate_vendor(make_vendor(sources=[]))))

    def test_standard_enum_enforced(self):
        self.assertTrue(any("枚举" in e for e in validate_vendor(make_vendor(standards=["WIFI7"]))))

    def test_empty_market_share_is_error(self):
        self.assertTrue(any("market_share" in e for e in validate_vendor(make_vendor(market_share={}))))

    def test_duplicate_id_detected(self):
        ds = {"vendors": [make_vendor(), make_vendor()]}
        self.assertTrue(any("重复" in e for e in validate_dataset(ds)))


class TestUnknownHandling(unittest.TestCase):
    def test_is_unknown_variants(self):
        self.assertTrue(is_unknown(None))
        self.assertTrue(is_unknown("unknown"))
        self.assertTrue(is_unknown(""))
        self.assertTrue(is_unknown([]))
        self.assertTrue(is_unknown(["unknown"]))
        self.assertFalse(is_unknown(["AI 专网战略"]))

    def test_coverage_report_counts_unknown_as_missing(self):
        vendors = [make_vendor(id="a"), make_vendor(id="b", ai_features=["AI 专网战略"])]
        report = coverage_report(vendors)
        # 两家都缺 ai 之外的 unknown 处理：只有一家有真实 ai_features
        self.assertAlmostEqual(report["coverage"]["ai_features"], 0.5)
        self.assertEqual(report["vendors"], 2)


if __name__ == "__main__":
    unittest.main()
