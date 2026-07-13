"""
LangGraph 状态图定义与编译
包含 ResearchState 类型定义和图构建逻辑
"""

from __future__ import annotations

import logging
from typing import List, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.researcher import researcher_node
from agents.writer import writer_node, writer_node_sync
from agents.fact_checker import fact_checker_node

logger = logging.getLogger(__name__)


class ResearchState(TypedDict):
    """全局共享状态"""
    topic: str
    search_results: List[dict]
    draft_report: str
    final_report: str
    error: str
    token_usage: dict
    # 多轮对话
    followup_question: str
    conversation_history: List[dict]
    # 动态配置
    model_name: str
    search_source: str
    api_base_url: str
    api_key: str
    api_format: str
    # Fact-Check
    fact_check_report: str
    # RAG
    knowledge_docs: List[str]
    # LLM 参与开关
    use_llm: bool


def create_graph() -> StateGraph:
    """
    构建并编译 LangGraph 状态图

    节点：
        - research:      搜索研究员，收集信息
        - write_report:  报告撰写员，生成 Markdown 报告

    边：
        research → write_report → END
    """
    builder = StateGraph(ResearchState)

    builder.add_node("research", researcher_node)
    builder.add_node("write_report", writer_node)
    builder.add_node("fact_check", fact_checker_node)

    builder.add_edge(START, "research")
    builder.add_edge("research", "write_report")
    builder.add_edge("write_report", "fact_check")
    builder.add_edge("fact_check", END)

    # 使用内存 saver，方便调试
    memory = MemorySaver()

    return builder.compile(checkpointer=memory)


# 编译好的图实例，供 api.py 导入使用
# 注意: researcher_node 和 writer_node 均为 async 函数，
# 调用时须使用 compiled_graph.ainvoke() 而非 .invoke()
compiled_graph = create_graph()
