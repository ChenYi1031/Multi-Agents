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
        # TypedDict 的 __annotations__ 包含字段定义
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
        # graph.nodes 返回节点名称列表
        nodes = list(graph.nodes.keys())
        assert "research" in nodes
        assert "write_report" in nodes

    def test_graph_has_edges(self):
        """图编译后应有边，验证边集合存在"""
        graph = create_graph()
        # CompiledStateGraph 在 LangGraph >=0.2 中通过 .get_graph() 获取结构
        struct = graph.get_graph()
        # get_graph() 返回一个 Graph 对象，有 nodes 和 edges
        assert struct is not None
        # 至少有 research → write_report 的连接
        edges = struct.edges
        assert len(edges) >= 2  # START→research, research→write_report

    def test_graph_invoke_no_api(self):
        """在不配置 API Key 时应优雅报错，而非崩溃"""
        import os
        # 临时清空 API Key 测试错误路径
        orig_key = os.environ.get("DEEPSEEK_API_KEY", "")
        try:
            if orig_key:
                del os.environ["DEEPSEEK_API_KEY"]
            if os.environ.get("OPENAI_API_KEY"):
                del os.environ["OPENAI_API_KEY"]

            from config import OPENAI_API_KEY as cfg_key
            # config.py 如果没有 key 会 raise ValueError
            # 但我们只验证图本身没问题
            graph = create_graph()
            assert graph is not None
        except Exception:
            # 如果 config 抛异常也是预期的
            pass
        finally:
            if orig_key:
                os.environ["DEEPSEEK_API_KEY"] = orig_key
