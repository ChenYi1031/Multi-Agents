"""
集成测试 — mock 全流程，不依赖真实 API
支持 async/await 调用
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from graph import create_graph


# ── Mock 数据 ────────────────────────────────

MOCK_SEARCH_RESULTS = [
    {"title": "AI Trend 2026", "summary": "AI发展趋势总结", "source": "https://example.com/ai"},
    {"title": "ML Advances", "summary": "机器学习新突破", "source": "https://example.com/ml"},
]

MOCK_REPORT = """# 2026年AI发展趋势报告

## 摘要
本文总结了2026年AI领域的主要趋势。

## 主要发现
- **大模型普及**: 更多企业采用LLM技术。[来源](https://example.com/ai)
- **多模态发展**: AI支持多种输入形式。[来源](https://example.com/ml)
- **AI Agent成熟**: 自主Agent进入生产阶段。[来源](https://example.com/ai)

## 结论与展望
AI技术将持续快速发展。
"""


# ── Helpers ──────────────────────────────────

def _make_async_mock(return_value):
    """创建一个同时支持 .invoke() 和 .ainvoke() 以及 .bind_tools() 的 mock"""
    mock_response = MagicMock()
    mock_response.content = return_value

    async def _ainvoke(*args, **kwargs):
        return mock_response

    mock_instance = MagicMock()
    mock_instance.invoke.return_value = mock_response
    mock_instance.ainvoke = _ainvoke

    # bind_tools() 返回的对象也必须支持 ainvoke
    mock_bound = MagicMock()
    mock_bound.invoke.return_value = mock_response
    mock_bound.ainvoke = _ainvoke
    mock_instance.bind_tools.return_value = mock_bound

    return mock_instance


# ── Fixtures ─────────────────────────────────

@pytest.fixture
def mock_search():
    """mock tools.search.search 返回固定结果"""
    with patch("tools.search.search", return_value=MOCK_SEARCH_RESULTS) as m:
        yield m


@pytest.fixture
def mock_llm():
    """mock ChatOpenAI 返回固定报告（支持 async）"""
    with patch("agents.writer.ChatOpenAI") as mock_cls:
        mock_cls.return_value = _make_async_mock(MOCK_REPORT)
        yield mock_cls


@pytest.fixture
def mock_researcher_llm():
    """mock researcher 中的 ChatOpenAI（支持 async）"""
    with patch("agents.researcher.ChatOpenAI") as mock_cls:
        json_content = json.dumps(MOCK_SEARCH_RESULTS, ensure_ascii=False, indent=2)
        mock_cls.return_value = _make_async_mock(json_content)
        yield mock_cls


# ── 测试 ─────────────────────────────────────


class TestFullGraph:
    """完整图流程（mock 搜索 + mock LLM）"""

    @pytest.mark.usefixtures("mock_researcher_llm")
    @pytest.mark.usefixtures("mock_llm")
    @pytest.mark.usefixtures("mock_search")
    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        """全流程正常返回报告"""
        graph = create_graph()
        result = await graph.ainvoke(
            {"topic": "2026年AI发展趋势", "search_results": [], "draft_report": "", "final_report": "", "error": ""},
            config={"configurable": {"thread_id": "test-1"}},
        )
        assert "final_report" in result
        assert "draft_report" in result
        assert result["final_report"] != ""
        assert "AI" in result["final_report"]

    @pytest.mark.usefixtures("mock_llm")
    @pytest.mark.asyncio
    async def test_empty_search_results(self, mock_search):
        """搜索返回空时，writer 应基于 LLM 知识生成"""
        mock_search.return_value = []
        graph = create_graph()

        with patch("agents.researcher.ChatOpenAI") as mock_r_cls:
            mock_r = _make_async_mock("[]")
            mock_r_cls.return_value = mock_r

            result = await graph.ainvoke(
                {"topic": "test", "search_results": [], "draft_report": "", "final_report": "", "error": ""},
                config={"configurable": {"thread_id": "test-2"}},
            )
            assert result["final_report"] != ""
            assert "error" not in result or not result.get("error")


class TestWriterTruncation:
    """Writer 截断检测"""

    def test_truncated_no_end_section(self):
        from agents.writer import _is_truncated
        report = "# 标题\n\n## 摘要\n内容。\n\n## 发现\n一些内容。"
        assert _is_truncated(report) is True, "缺少结论章节应判为截断"

    def test_truncated_ends_with_heading(self):
        from agents.writer import _is_truncated
        report = "# 标题\n\n## 摘要\n内容。\n\n## 结论\n"
        assert _is_truncated(report) is True, "末尾是标题应判为截断"

    def test_not_truncated_complete(self):
        from agents.writer import _is_truncated
        report = "# 标题\n\n## 摘要\n内容。\n\n## 发现\n细节。\n\n## 结论与展望\n总结内容。"
        assert _is_truncated(report) is False, "完整报告不应判为截断"

    def test_not_truncated_with_summary(self):
        from agents.writer import _is_truncated
        report = "# 标题\n\n## 摘要\n内容。\n\n## 总结\n结尾内容。"
        assert _is_truncated(report) is False, "包含【总结】不应判为截断"

    def test_empty_report(self):
        from agents.writer import _is_truncated
        assert _is_truncated("") is False
        assert _is_truncated(None) is False


class TestWriterContinuation:
    """Writer 续写"""

    @pytest.mark.usefixtures("mock_llm")
    @pytest.mark.asyncio
    async def test_continue_appends(self):
        from agents.writer import _continue_report_async, _build_llm
        llm = _build_llm()
        report = "# 标题\n\n## 摘要\n内容。\n\n## 发现\n"
        continued = await _continue_report_async(llm, report, "test", "[]")
        assert len(continued) > len(report)
        assert continued.startswith("#")
