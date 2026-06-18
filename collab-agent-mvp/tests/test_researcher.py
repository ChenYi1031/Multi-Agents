"""
Researcher 解析函数单元测试
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from agents.researcher import (
    _extract_json_array,
    _clean_json_string,
    _parse_json_from_response,
)


# ──────────────────────────────────────────────
# _extract_json_array
# ──────────────────────────────────────────────
class TestExtractJsonArray:
    def test_json_code_block(self):
        text = '```json\n[{"title": "A"}]\n```'
        assert _extract_json_array(text) == '[{"title": "A"}]'

    def test_code_block_without_lang(self):
        text = '```\n[{"title": "A"}]\n```'
        assert _extract_json_array(text) == '[{"title": "A"}]'

    def test_bare_array(self):
        text = '[{"title": "A"}, {"title": "B"}]'
        result = _extract_json_array(text)
        assert result is not None
        assert "title" in result

    def test_array_inside_narrative(self):
        text = "以下是搜索结果：\n[{\"title\": \"A\"}]\n请查收。"
        result = _extract_json_array(text)
        assert result is not None

    def test_empty_text(self):
        assert _extract_json_array("") is None
        assert _extract_json_array("   ") is None
        assert _extract_json_array(None) is None

    def test_no_array(self):
        text = "这里没有 JSON 数组"
        result = _extract_json_array(text)
        # 全文被当作 JSON 尝试解析，会失败
        # 应该返回全文（让上层处理异常）
        assert result == text


# ──────────────────────────────────────────────
# _clean_json_string
# ──────────────────────────────────────────────
class TestCleanJsonString:
    def test_trailing_comma(self):
        raw = '{"title": "A",}'
        assert _clean_json_string(raw) == '{"title": "A"}'

    def test_trailing_comma_array(self):
        raw = '[{"title": "A"},]'
        cleaned = _clean_json_string(raw)
        assert cleaned == '[{"title": "A"}]'

    def test_single_quotes(self):
        raw = "{'title': 'A'}"
        assert _clean_json_string(raw) == '{"title": "A"}'

    def test_python_bool(self):
        raw = '{"active": True, "done": False}'
        cleaned = _clean_json_string(raw)
        assert json.loads(cleaned)["active"] is True
        assert json.loads(cleaned)["done"] is False

    def test_python_none(self):
        raw = '{"value": None}'
        assert json.loads(_clean_json_string(raw))["value"] is None

    def test_mixed_issues(self):
        raw = "{'title': 'A', 'count': None,}"
        cleaned = _clean_json_string(raw)
        parsed = json.loads(cleaned)
        assert parsed["title"] == "A"
        assert parsed["count"] is None


# ──────────────────────────────────────────────
# _parse_json_from_response (集成)
# ──────────────────────────────────────────────
class TestParseJsonFromResponse:
    def test_simple_array(self):
        content = '[{"title": "A", "summary": "sum", "source": "https://a.com"}]'
        result = _parse_json_from_response(content)
        assert len(result) == 1
        assert result[0]["title"] == "A"

    def test_json_code_block(self):
        content = '```json\n[{"title": "A", "summary": "sum", "source": "https://a.com"}]\n```'
        result = _parse_json_from_response(content)
        assert len(result) == 1

    def test_single_dict(self):
        content = '{"title": "A", "summary": "sum", "source": "https://a.com"}'
        result = _parse_json_from_response(content)
        assert len(result) == 1

    def test_empty_content(self):
        with pytest.raises(ValueError, match="为空"):
            _parse_json_from_response("")

    def test_trailing_comma(self):
        content = '[{"title": "A", "summary": "sum", "source": "https://a.com"},]'
        result = _parse_json_from_response(content)
        assert len(result) == 1

    def test_single_quotes(self):
        content = "[{'title': 'A', 'summary': 'sum', 'source': 'https://a.com'}]"
        result = _parse_json_from_response(content)
        assert len(result) == 1

    def test_narrative_wrapping(self):
        content = """以下是研究结果：
[
  {"title": "AI趋势", "summary": "2026年...", "source": "https://a.com"}
]
请查收。"""
        result = _parse_json_from_response(content)
        assert len(result) == 1

    def test_object_extraction_fallback(self):
        """当 JSON 数组解析失败时，尝试提取单个 {...} 对象"""
        content = '{"title": "A", "summary": "sum", "source": "https://a.com"},{"title": "B"}'
        result = _parse_json_from_response(content)
        assert len(result) >= 1

    def test_multiple_items(self):
        content = """[
  {"title": "A", "summary": "a", "source": "https://a.com"},
  {"title": "B", "summary": "b", "source": "https://b.com"}
]"""
        result = _parse_json_from_response(content)
        assert len(result) == 2
