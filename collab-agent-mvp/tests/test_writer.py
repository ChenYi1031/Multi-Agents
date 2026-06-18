"""
Writer 质量校验单元测试
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from agents.writer import validate_report, _build_prompt


# ──────────────────────────────────────────────
# validate_report
# ──────────────────────────────────────────────

class TestValidateReport:
    """报告质量校验"""

    def test_valid_report(self):
        report = """# AI发展趋势报告

## 摘要
本文总结了2026年AI领域的主要趋势。

## 主要发现
- **大模型普及**: 越来越多的企业采用LLM技术。[来源](https://example.com/ai)
- **多模态发展**: AI模型支持图像、视频等多种输入。[来源](https://example.com/multi)

## 结论与展望
AI将持续影响各行各业。
"""
        issues = validate_report(report, "AI趋势", [
            {"title": "AI", "summary": "AI", "source": "https://example.com/ai"},
        ])
        assert issues == [], f"应有空列表，得到: {issues}"

    def test_empty_report(self):
        issues = validate_report("", "topic", [])
        assert "报告内容为空" in issues

    def test_error_marker(self):
        report = "# 报告生成出错\n\nsomething went wrong"
        issues = validate_report(report, "topic", [])
        assert "报告包含错误标记" in issues

    def test_no_heading(self):
        report = "这是一段没有标题的文字。\n\n只有正文。"
        issues = validate_report(report, "topic", [])
        assert "缺少一级或二级标题" in issues

    def test_missing_sections(self):
        report = "# 标题\n\n只有一段话。"
        issues = validate_report(report, "topic", [])
        assert any("缺少" in i for i in issues)

    def test_no_source_citation(self):
        report = "# 标题\n\n## 摘要\n摘要内容。\n\n## 结论\n结论。"
        issues = validate_report(report, "topic", [
            {"title": "X", "summary": "x", "source": "https://example.com/x"},
        ])
        source_issues = [i for i in issues if "引用" in i]
        assert len(source_issues) >= 1

    def test_with_source_citation(self):
        report = """# 标题

## 摘要
内容。

## 发现
详情 [Example](https://example.com/x)

## 结论
总结。
"""
        issues = validate_report(report, "topic", [
            {"title": "X", "summary": "x", "source": "https://example.com/x"},
        ])
        assert issues == [] or all("引用" not in i for i in issues)


# ──────────────────────────────────────────────
# _build_prompt
# ──────────────────────────────────────────────

class TestBuildPrompt:
    def test_basic(self):
        prompt = _build_prompt("AI", '[{"title": "A"}]')
        assert "AI" in prompt
        assert "A" in prompt
        assert "修复" not in prompt

    def test_with_fix(self):
        prompt = _build_prompt("AI", "[]", fix_instruction="缺少标题")
        assert "缺少标题" in prompt

    def test_empty_results_prompt(self):
        prompt = _build_prompt("AI", "未找到相关搜索结果，请基于你的知识生成报告。")
        assert "未找到相关搜索结果" in prompt
