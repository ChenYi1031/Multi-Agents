"""
CollabAgent MVP - 离线测试脚本
不启动 FastAPI 服务，直接调用 LangGraph 图进行端到端测试
使用异步 ainvoke 调用
"""

from __future__ import annotations

import asyncio
import logging

from graph import compiled_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    """运行一次端到端测试"""
    topic = "量子计算最新进展"
    print(f"开始研究主题: {topic}")
    print("=" * 70)

    initial_state = {
        "topic": topic,
        "search_results": [],
        "draft_report": "",
        "final_report": "",
        "error": "",
    }

    result = await compiled_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test1"}},
    )

    print("\n搜索结果:")
    print("-" * 70)
    search_results = result.get("search_results", [])
    if search_results:
        for i, r in enumerate(search_results, 1):
            print(f"  {i}. {r.get('title', '无标题')}")
            print(f"     来源: {r.get('source', '无来源')}")
            print(f"     摘要: {r.get('summary', '无摘要')[:100]}...")
            print()
    else:
        print("  (无搜索结果)")

    print("=" * 70)
    print("\n最终报告:")
    print("-" * 70)
    print(result.get("final_report", "无报告生成"))

    if result.get("error"):
        print(f"\n!!! 错误: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())
