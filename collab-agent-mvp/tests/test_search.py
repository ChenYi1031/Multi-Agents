"""
搜索工具单元测试
"""

import json
import sys
from pathlib import Path

# ── 把项目根目录加入 sys.path ──
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from tools.search import deduplicate_results


class TestDeduplicateResults:
    """deduplicate_results 去重逻辑"""

    def test_empty_list(self):
        assert deduplicate_results([]) == []

    def test_no_duplicates(self):
        items = [
            {"title": "A", "summary": "sumA", "source": "https://a.com"},
            {"title": "B", "summary": "sumB", "source": "https://b.com"},
        ]
        result = deduplicate_results(items)
        assert len(result) == 2

    def test_duplicate_source(self):
        items = [
            {"title": "A", "summary": "sumA", "source": "https://same.com"},
            {"title": "B", "summary": "sumB", "source": "https://same.com"},
        ]
        result = deduplicate_results(items)
        assert len(result) == 1
        assert result[0]["title"] == "A"  # 保留首次出现

    def test_duplicate_more_than_two(self):
        items = [
            {"title": "A", "summary": "a", "source": "https://x.com"},
            {"title": "B", "summary": "b", "source": "https://x.com"},
            {"title": "C", "summary": "c", "source": "https://x.com"},
        ]
        result = deduplicate_results(items)
        assert len(result) == 1

    def test_empty_source_dedup_by_title(self):
        items = [
            {"title": "相同标题", "summary": "a", "source": ""},
            {"title": "相同标题", "summary": "b", "source": ""},
        ]
        result = deduplicate_results(items)
        assert len(result) == 1

    def test_empty_source_different_title(self):
        items = [
            {"title": "A", "summary": "a", "source": ""},
            {"title": "B", "summary": "b", "source": ""},
        ]
        result = deduplicate_results(items)
        assert len(result) == 2

    def test_mixed_empty_and_nonempty_source(self):
        items = [
            {"title": "A", "summary": "a", "source": ""},
            {"title": "A", "summary": "a", "source": "https://a.com"},
        ]
        result = deduplicate_results(items)
        # 两个都保留：第一个无 source 按 title 去重，第二个有 source
        # 但第二个 title 相同，不过因为它有 source 且不同
        assert len(result) == 2

    def test_realistic_data(self):
        items = [
            {"title": "AI趋势", "summary": "2026年AI...", "source": "https://example.com/ai"},
            {"title": "AI趋势", "summary": "2026年AI...", "source": "https://example.com/ai"},
            {"title": "机器学习", "summary": "ML最新...", "source": "https://example.com/ml"},
            {"title": "AI趋势", "summary": "重复无source", "source": ""},
            {"title": "AI趋势", "summary": "重复无source2", "source": ""},
        ]
        result = deduplicate_results(items)
        # 去重后: AI趋势(src) + 机器学习(src) = 2
        assert len(result) == 2


class TestDeduplicateResultsEdgeCases:
    """边界情况"""

    def test_all_empty_fields(self):
        items = [
            {"title": "", "summary": "", "source": ""},
            {"title": "", "summary": "", "source": ""},
        ]
        result = deduplicate_results(items)
        assert len(result) == 2  # 两者皆空时都保留

    def test_trailing_slash_url(self):
        """source 去重不处理尾斜杠差异"""
        items = [
            {"title": "A", "summary": "a", "source": "https://example.com/page"},
            {"title": "A", "summary": "a", "source": "https://example.com/page/"},
        ]
        result = deduplicate_results(items)
        # 视为不同 URL，保留两个
        # 这是已知简化行为，不自动标准化 URL
        assert len(result) == 2

    def test_non_string_source(self):
        items = [
            {"title": "A", "summary": "a", "source": 12345},
            {"title": "B", "summary": "b", "source": 12345},
        ]
        result = deduplicate_results(items)
        # source 被 str() 后去重
        assert len(result) == 1
