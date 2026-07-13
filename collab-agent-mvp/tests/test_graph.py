"""
Graph 结构和编译单元测试
不调用 LLM / 搜索，仅测试图结构正确性
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from graph import ResearchState, create_graph


class TestResearchState:
    """状态类型定义"""

    def test_state_keys(self):
        """ResearchState 应包含所有预期字段"""
        required = {"topic", "search_results", "draft_report", "final_report", "error"}
        annotations = ResearchState.__annotations__
        assert required.issubset(annotations.keys()), \
            f"缺少字段: {required - annotations.keys()}"


class TestCreateGraph:
    """图编译"""

    def test_graph_compiles(self):
        """create_graph 应成功返回编译后的图"""
        graph = create_graph()
        assert graph is not None

    def test_graph_node_count(self):
        """图应包含 research 和 write_report 两个节点"""
        graph = create_graph()
        nodes = list(graph.nodes.keys())
        assert "research" in nodes
        assert "write_report" in nodes

    def test_graph_has_edges(self):
        """图编译后应有边"""
        graph = create_graph()
        struct = graph.get_graph()
        assert struct is not None
        edges = struct.edges
        assert len(edges) >= 2  # START→research, research→write_report

    def test_graph_ainvoke_supported(self):
        """图应支持 ainvoke（异步调用）"""
        graph = create_graph()
        assert hasattr(graph, "ainvoke"), "图缺少 ainvoke 方法"
        assert callable(graph.ainvoke)
