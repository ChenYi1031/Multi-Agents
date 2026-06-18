# CollabAgent 最小可行产品（MVP）需求开发文档

**文档版本**：v1.0  
**目标交付**：可运行的端到端原型，验证多Agent协作生成报告的核心流程  
**开发人员**：AI 编程助手  
**预计工期**：5-7 天（按单人 AI 编码速度估算）

---

## 1. 项目概述与 MVP 目标

本项目最终目标是构建一个多AI Agent协作分析平台，但MVP仅实现**最简闭环**：

**用户输入一个研究主题 → 搜索研究员收集信息 → 报告撰写员生成结构化报告 → 返回Markdown报告**

MVP 只包含两个Agent，串行执行，不包含辩论、审核、人工卡点、向量记忆、Langfuse 等高级特性。这些将在后续迭代中逐步加入。

**MVP核心约束**：
- 2 个 Agent：`SearchResearcher`、`ReportWriter`
- 1 条线性工作流：研究 → 撰写
- 无人工干预，无长期记忆
- 使用简单的内存状态管理（LangGraph MemorySaver）
- 一个 FastAPI 接口即可触发任务并获取结果
- 工具仅需：Tavily 搜索（或 DuckDuckGo 免费替代）

---

## 2. 技术栈（MVP 限定）

| 组件           | 选型                                     | 备注                             |
| -------------- | ---------------------------------------- | -------------------------------- |
| 编排框架       | LangGraph (langgraph==0.2.0+)            | 构建状态图，管理节点流转         |
| Agent 框架     | LangChain (langchain>=0.3.0)             | 提供 Tool 抽象、Prompt Template |
| 后端 API       | FastAPI + Uvicorn                        | 仅需一个 `/research` 端点       |
| 模型           | OpenAI GPT-4o-mini (或用户提供的 key)     | 成本低、响应快，适合原型         |
| 搜索工具       | Tavily Search API (或 DuckDuckGo)        | 二选一，提供封装                 |
| 状态持久化     | LangGraph MemorySaver (内存)             | 单次会话，不跨进程               |
| 前端（可选）   | 无，仅 API + curl/Postman 测试           | 前端延后                         |
| 可观测性（暂缓）| 控制台日志 + print 语句                  | Langfuse 延后                    |

---

## 3. 系统架构（MVP 极简版）

```
用户 → FastAPI (/research) → LangGraph StateGraph (2节点)
                                  ├─ research_node (SearchResearcher)
                                  └─ writing_node (ReportWriter)
                                  → 返回 final_report
```

状态图结构：
- **StateGraph** 包含 3 个节点：`research`, `write_report`, `END`
- 边：`research → write_report → END`

无分支、无循环。

---

## 4. 详细功能需求

### 4.1 全局状态定义（ResearchState）

在 LangGraph 中定义以下 `TypedDict` 作为共享状态：

```python
from typing import TypedDict, List

class ResearchState(TypedDict):
    topic: str                    # 用户输入的研究主题
    search_results: List[dict]    # 研究员返回的结构化信息列表
    draft_report: str             # 撰写员生成的 Markdown 草稿
    final_report: str             # 最终报告（目前等于 draft_report）
    error: str                    # 若异常则填充错误信息
```

### 4.2 搜索研究员节点

**角色**：收集与主题相关的网页信息，输出结构化摘要列表。

**系统提示词模板**（用于 `ChatPromptTemplate`）：
```
你是一位专业的研究助理。你的任务是根据用户提供的主题，列出 3-5 个最重要的信息点或事实。
对于每个信息点，请使用搜索工具查找可靠的来源，并以 JSON 格式返回结果。

要求：
- 每个信息点必须包含: title (简短标题), summary (2-3 句话的摘要), source (URL)。
- 优先使用近期、权威的来源。
- 输出格式必须是严格的 JSON 数组，不要包含任何其他文字。

示例输出：
[
  {{"title": "气候变化对农业的影响", "summary": "...", "source": "https://..."}},
  ...
]
```

**工具**：
- `tavily_search` 或 `duckduckgo_search`：封装为一个 LangChain Tool。
  工具调用示例：
  ```python
  from langchain_community.tools import TavilySearchResults
  search_tool = TavilySearchResults(max_results=5)
  ```

**实现逻辑**（伪代码）：
```python
def research_node(state: ResearchState) -> dict:
    topic = state["topic"]
    # 构建提示词，要求 LLM 使用工具并返回 JSON
    llm_with_tools = llm.bind_tools([search_tool])
    # 使用 SystemMessage 指导输出格式
    messages = [
        SystemMessage(content=RESEARCHER_PROMPT),
        HumanMessage(content=f"研究主题：{topic}")
    ]
    response = llm_with_tools.invoke(messages)
    # 解析返回的 JSON 数组
    search_results = parse_json_from_response(response)
    return {"search_results": search_results}
```

**异常处理**：若解析失败，重试一次；仍失败则返回空列表并记录错误日志。

### 4.3 报告撰写员节点

**角色**：基于搜索结果，撰写一份结构清晰、可读性强的 Markdown 报告。

**系统提示词模板**：
```
你是一位资深报告撰写员。你会收到一份关于“{topic}”的搜索结果列表。
请基于这些信息，撰写一份专业的 Markdown 格式报告。

报告结构要求：
1. 标题（一级标题）
2. 摘要（一段话概括）
3. 主要发现（二级标题，每个发现一个小节，引用来源）
4. 结论与展望（一段话）

要求：
- 必须引用所有给定的来源，使用 [来源名称](URL) 格式。
- 语言专业、客观，避免夸张。
- 输出纯净的 Markdown，不要包含解释性文字。
```

**输入**：`state["topic"]` 和 `state["search_results"]`（将搜索结果序列化为文本填入提示词）。

**实现逻辑**：
```python
def writing_node(state: ResearchState) -> dict:
    topic = state["topic"]
    results = state["search_results"]
    # 将结果格式化为文本块
    research_text = json.dumps(results, indent=2, ensure_ascii=False)
    prompt = WRITER_PROMPT.format(topic=topic, research_text=research_text)
    response = llm.invoke(prompt)
    draft = response.content
    return {"draft_report": draft, "final_report": draft}
```

### 4.4 FastAPI 接口

**端点**：`POST /research`

**请求体**：
```json
{
  "topic": "2025年全球人工智能发展趋势"
}
```

**响应体**（200 OK）：
```json
{
  "status": "completed",
  "final_report": "# 2025年全球人工智能发展趋势\n\n## 摘要\n...",
  "search_results": [...]
}
```

**错误响应**（500）：
```json
{
  "status": "error",
  "detail": "搜索工具调用失败: ..."
}
```

**实现逻辑**：
```python
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END

app = FastAPI()
graph = create_graph()  # 编译好的图

class ResearchRequest(BaseModel):
    topic: str

@app.post("/research")
async def research(req: ResearchRequest):
    initial_state = {"topic": req.topic, "search_results": [], "draft_report": "", "final_report": "", "error": ""}
    final_state = graph.invoke(initial_state)
    if final_state.get("error"):
        return JSONResponse(status_code=500, content={"status": "error", "detail": final_state["error"]})
    return {
        "status": "completed",
        "final_report": final_state["final_report"],
        "search_results": final_state["search_results"]
    }
```

### 4.5 图构建与编译

```python
def create_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("research", research_node)
    builder.add_node("write_report", writing_node)
    builder.set_entry_point("research")
    builder.add_edge("research", "write_report")
    builder.add_edge("write_report", END)
    # 使用内存 saver，方便调试
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)
```

**注意**：尽管使用了 `checkpointer`，但 MVP 不要求跨请求恢复，仅用于 LangGraph 内部机制。`invoke` 时传入 `config={"configurable": {"thread_id": "1"}}` 即可。

---

## 5. 开发任务分解（AI 可执行步骤）

请按以下顺序实现，每步完成后验证。

### 步骤 1：项目初始化与环境配置
1. 创建项目目录 `collab-agent-mvp/`，初始化 `requirements.txt`：
   ```
   langgraph==0.2.*
   langchain==0.3.*
   langchain-openai==0.2.*
   langchain-community==0.3.*
   fastapi==0.115.*
   uvicorn==0.32.*
   tavily-python  # 若用 Tavily；若用 DuckDuckGo 则用 duckduckgo-search
   ```
2. 创建 `.env` 文件模板，包含 `OPENAI_API_KEY` 和 `TAVILY_API_KEY`（或 `DUCKDUCKGO` 无需 key）。
3. 编写 `config.py` 加载环境变量。

### 步骤 2：实现搜索工具封装
1. 选择搜索后端：Tavily（推荐，结果结构化）或 DuckDuckGo（免费）。
2. 创建 `tools/search.py`，定义一个 `search` 函数，返回列表 `[{"title":..., "summary":..., "source":...}]`。
   - 若使用 Tavily，直接封装 `TavilySearchResults`，并格式化输出。
   - 若使用 DuckDuckGo，使用 `DuckDuckGoSearchAPIWrapper`，但需要额外处理摘要提取。

### 步骤 3：实现 Agent 节点
1. 创建 `agents/researcher.py`，包含 `researcher_node` 函数。
   - 加载 LLM（`ChatOpenAI`）。
   - 绑定工具。
   - 构造提示词，强制输出 JSON。
   - 解析 JSON，处理失败重试。
2. 创建 `agents/writer.py`，包含 `writer_node` 函数。
   - 直接调用 LLM 生成 Markdown。

### 步骤 4：组装 LangGraph 图
1. 创建 `graph.py`，定义 `ResearchState`，按上述方式构造图，并导出 `compiled_graph`。
2. 编写简单的测试脚本 `test_graph.py`，用硬编码主题运行一次，打印最终报告。

### 步骤 5：构建 FastAPI 服务
1. 创建 `api.py`，挂载 `/research` 端点。
2. 添加 CORS 中间件（方便后续前端调试）。
3. 添加请求日志记录（简单的 `print` 或 `logger`）。

### 步骤 6：集成测试与错误处理
1. 使用 `curl` 或 `httpie` 发送请求，验证能否返回完整 Markdown 报告。
2. 测试异常场景：缺少 API key、搜索工具超时、JSON 解析失败等，确保返回友好的错误信息。

### 步骤 7：文档与交付
1. 编写 `README.md`：如何配置环境、启动服务、调用 API。
2. 提供示例请求和响应。
3. 标注后续迭代方向。

---

## 6. 验收标准（MVP）

- [ ] 发送一个主题（例如“量子计算最新进展”），能在 1-3 分钟内返回包含 2-5 个来源的结构化 Markdown 报告。
- [ ] 报告质量：标题、摘要、主要发现、结论四部分完整，每个发现都有来源链接。
- [ ] API 返回正确的 JSON 结构，状态码 200。
- [ ] 错误时返回 500 并包含错误详情，而非服务崩溃。
- [ ] 代码结构清晰，注释适量，方便后续迭代。

---

## 7. 后续迭代计划（不在 MVP 范围）

以下功能将在后续版本中逐步实现，可作为 backlog 参考。

| 迭代 | 功能                                                     | 依赖                |
| ---- | -------------------------------------------------------- | ------------------- |
| V0.2 | 引入**数据分析师 Agent**，增加 Python 代码执行工具       | MVP 完成            |
| V0.3 | 加入**辩论子图**，实现研究员-分析师多轮互辩              | V0.2                |
| V0.4 | **质量审核员 Agent** + 报告修订循环                      | V0.3                |
| V0.5 | **Human-in-the-loop** 人工审批节点                       | V0.3+Redis          |
| V0.6 | **Redis 会话管理** + 断点续传                            | LangGraph checkpointer |
| V0.7 | **向量数据库记忆**（Chroma）存储历史报告与事实            | V0.4                |
| V0.8 | **Langfuse 全链路追踪**与成本监控                        | V0.5                |
| V1.0 | 前端 Dashboard（Next.js），支持多任务并行，完善 UI        | V0.8                |

---

## 8. 给 AI 开发人员的特别指引

- **编码风格**：使用 Python 3.11+ 类型提示，遵循 PEP 8，尽量使用 `pydantic` 做数据校验。
- **错误处理**：每个外部调用（LLM、搜索 API）都要包裹 try-except，记录日志并设置 `state["error"]`。
- **安全性**：MVP 阶段无需过分关注沙箱，但请勿将 API key 硬编码在代码中，使用 `.env` + `python-dotenv`。
- **测试优先**：每完成一个 Agent 节点，立即写一个小测试验证其输出格式。
- **可扩展性**：Agent 节点的输入输出通过 `ResearchState` 字段传递，不依赖全局变量；工具封装为独立模块，方便替换。
- **回复格式**：在交付代码时，请同时提供详细的配置说明和运行示例。

