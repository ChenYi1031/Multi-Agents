# CollabAgent MVP — 迭代开发文档

> 本文档服务于 **AI → AI 接力开发**，记录当前架构、已修复 Bug、关键决策和待办事项。
> 后续 AI 接手时，**必须先阅读此文档**，再开始修改代码。

---

## 1. 项目概述

多 Agent 协作研究报告生成系统。用户输入主题 → Researcher 搜索信息 → Writer 撰写报告 → 返回 Markdown。

**栈：** Python 3.11+ · FastAPI · LangGraph · LangChain · DuckDuckGo / Tavily · DeepSeek API

**总入口：** `api.py` → `POST /research`
**状态图：** `graph.py` → `research → write_report → END`

---

## 2. 架构总览

```
api.py  (FastAPI 入口)
  │
  ▼
graph.py  (LangGraph StateGraph)
  │
  ├─ researcher_node  (agents/researcher.py)
  │     └─ 调用 search_tool → tools/search.py
  │            ├─ DuckDuckGo (默认, 免费)
  │            └─ Tavily (备用, 需 API Key)
  │
  └─ writer_node  (agents/writer.py)
        └─ ChatOpenAI → 输出 Markdown 报告
```

- 状态定义 `ResearchState`：topic, search_results, draft_report, final_report, error
- 所有 LLM 调用通过 OpenAI 兼容接口 → 默认 DeepSeek
- 通过 `config.py` + `.env` 配置

---

## 3. 已完成的迭代与修复

### Iteration 1 — 基础设施搭建

| 改动 | 文件 |
|---|---|
| 创建 FastAPI 应用骨架 | `api.py` |
| 创建 LangGraph 状态图 | `graph.py` |
| 创建 Researcher Agent 框架 | `agents/researcher.py` |
| 创建 Writer Agent 框架 | `agents/writer.py` |
| 创建搜索工具模块 | `tools/search.py` |
| 配置管理与环境变量 | `config.py`, `.env.example` |
| 依赖声明 | `requirements.txt` |

### Iteration 2 — Bug 修复 (A→B 接力修复)

| # | 问题 | 根因 | 修复方式 |
|---|---|---|---|
| 1 | `ModuleNotFoundError: ToolMessage` | `langchain.schema` 导入路径已废弃 | `from langchain_core.messages import ToolMessage` |
| 2 | `Could not import ddgs` | duckduckgo_search v6 换了 SDK，langchain wrapper 不兼容 | 直接用 `DDGS` 类，不用 `DuckDuckGoSearchResults` |
| 3 | JSON 解析失败 — LLM 返回了 tool_call | Researcher 只写了普通聊天调用，没实现 tool calling 循环 | 实现 `_run_tool_loop()`：检测 tool_calls → 执行 → 注入结果 → 重新调用 |
| 4 | `{{"title"}}` 双大括号输出 | Prompt 中的 `{{` 在字符串中被当成模板语法 | 改为单大括号 `{"title"}` |
| 5 | DuckDuckGo 限速 202 | 短时间请求过多被 DD 拒绝 | 失败直接返回空，Writer 用 LLM 知识兜底，客户体验优先 |
| 6 | Tavily 无 API Key 时报错 | 没 Key 也尝试调用 Tavily SDK | 在 `_search_tavily()` 入口检查 `TAVILY_API_KEY` |
| 7 | 搜索全失败后 API 返回 500 | Researcher 返回 `{"error": ...}` 导致 Writer 跳过处理 | 返回空列表 `search_results: []`，Writer 用 LLM 知识兜底 |
| 8 | DuckDuckGo v6 `proxies` 参数弃用 | `DDGS(proxies=...)` → `DDGS(proxy=...)`（字符串） | `_get_proxies()` → `_get_proxy()` 返回 URL 字符串 |

### Iteration 3 — 容器化

| 改动 | 文件 |
|---|---|
| 创建多阶段 Dockerfile | `Dockerfile` |
| 创建 `.dockerignore` | `.dockerignore` |
| 验证容器构建与启动 | — |

### Iteration 4 — 韧性提升 + 单元测试

| # | 改动 | 文件 | 说明 |
|---|---|---|---|
| 1 | 搜索结果去重 | `tools/search.py` | 新增 `deduplicate_results()`，按 source→title 去重 |
| 2 | Tool calling loop 超限兜底 | `agents/researcher.py` | 5 轮超限后移除工具绑定，强制 LLM 输出 JSON |
| 3 | JSON 解析多级降级 | `agents/researcher.py` | `_extract_json_array` + `_clean_json_string` + 对象片段提取 |
| 4 | 搜索结果去重集成 | `agents/researcher.py` | 所有返回路径都经过 `deduplicate_results()` |
| 5 | 单元测试框架 | `tests/` | pytest，32 个测试覆盖去重 + JSON 解析 |
| 6 | `pytest` 加入依赖 | `requirements.txt` | `pytest>=8.0.0,<9` |

### Iteration 5 — Writer 质量校验 + 测试全覆盖

| # | 改动 | 文件 | 说明 |
|---|---|---|---|
| 1 | 报告质量校验 | `agents/writer.py` | 新增 `validate_report()` — 检查标题/章节/引用/错误标记 |
| 2 | 自动修复机制 | `agents/writer.py` | 校验失败时 LLM 重写一轮，带具体 issue 反馈 |
| 3 | 模块化 prompt 构建 | `agents/writer.py` | 抽离 `_build_prompt()` 分离生成与修复逻辑 |
| 4 | Writer 单元测试 | `tests/test_writer.py` | 11 个测试：空报告、错误标记、章节、引用校验 |
| 5 | Graph 单元测试 | `tests/test_graph.py` | 4 个测试：状态定义、图编译、节点注册、结构验证 |

### Iteration 6 — 截断续写 + 集成测试

| # | 改动 | 文件 | 说明 |
|---|---|---|---|
| 1 | 截断检测 | `agents/writer.py` | 新增 `_is_truncated()` — 检查结尾/结束章节/末尾完整性 |
| 2 | 自动续写 | `agents/writer.py` | 新增 `_continue_report()` — 从断点续写并拼接去重 |
| 3 | 续写集成 | `agents/writer.py` | writer_node 中校验后执行截断检测 |
| 4 | 集成测试 | `tests/test_integration.py` | 8 个测试：mock 全流程 + 截断检测 + 续写验证 |

### Iteration 7 — 代理自动兜底 + 启动探针

| # | 改动 | 文件 | 说明 |
|---|---|---|---|
| 1 | DD 搜索 proxy 自动降级 | `tools/search.py` | 配置 proxy 失败 → 自动尝试直连 |
| 2 | 启动连通性探针 | `api.py` | startup 时检测 DD + Tavily 是否可用 |
| 3 | /health 增强 | `api.py` | 返回 DD/Tavily/LLM Key 状态 |
| 4 | 代理配置文档化 | `.env.example` | 添加 HTTP_PROXY/HTTPS_PROXY 说明 |

---

## 4. 关键文件速查

### `tools/search.py` — 搜索核心

```
search(query) → List[dict]           # 对外唯一入口，从不抛异常
  ├─ _search_duckduckgo()            # 默认后端
  ├─ _search_tavily()                # 备用后端，无 API Key 时静默跳过
  └─ deduplicate_results(list)       # 按 source→title 去重，供 researcher 调用
```

**重要约定：**
- 所有函数/方法 **永不抛异常**，失败返回 `[]`
- DuckDuckGo 任何异常**直接返回**，不重试 → Writer 用 LLM 知识兜底
- 主引擎失败后自动切换另一个引擎兜底
- 搜索结果经过 `deduplicate_results()` 去重后进入报告

### `agents/researcher.py` — 研究员 Agent

```
researcher_node(state) → {"search_results": [...]}
  ├─ 首次：LLM + tool calling loop → JSON 解析
  ├─ 重试：加严格 prompt → LLM + tool calling loop → JSON 解析
  └─ 兜底：search(topic) 直接搜 → 返回原始结果
```

**tool calling loop 逻辑 (**_run_tool_loop_**)：**
1. 调用 `llm_with_tools.invoke(messages)`
2. 检测 `response.tool_calls`
3. 有 tool_call → 执行 search() → 注入 ToolMessage → 继续循环
4. 无 tool_call → 返回纯文本 response
5. 最多 5 轮，防止无限循环
6. ⚠ 5 轮超限 → **移除工具绑定**，用裸 `llm.invoke()` 强制输出 JSON

**JSON 解析 (_parse_json_from_response_**)——三级降级：**
1. ` ```json [...] ``` ` 代码块
2. `[...]` 外层包裹提取
3. 清洗（去尾部逗号、单引号→双引号、True/None→true/null）
4. 提取所有 `{...}` 对象片段拼装

**搜索结果去重：** 所有返回路径都经过 `deduplicate_results()`

### `agents/writer.py` — 撰写员 Agent

```
writer_node(state) → {"draft_report": str, "final_report": str}
```

- search_results 为空时会提示 "未找到相关搜索结果，请基于你的知识生成报告"
- 调用 LLM 生成 Markdown 报告，要求引用来源 `[标题](URL)` 格式
- **质量校验**：`validate_report()` 检查：
  1. 报告非空，不含错误标记
  2. 有标题（#/##）
  3. 有摘要/结论/展望等章节
  4. 有搜索结果时至少引用一个来源 URL
- **自动修复**：校验失败时，将 issue 列表反馈给 LLM 重写一轮
- prompt 构建抽离为 `_build_prompt()`，修复时附加 `fix_instruction`

### `graph.py` — LangGraph 状态图

```
START → research → write_report → END
```

简单线性流水线，无条件分支，无循环。

### `api.py` — FastAPI 服务

| 端点 | 方法 | 说明 |
|---|---|---|
| `/research` | POST | body: `{"topic": "..."}` 返回报告 |
| `/health` | GET | 健康检查 |

### `tests/` — 单元测试 + 集成测试

```
tests/
  __init__.py
  test_search.py       # deduplicate_results 去重逻辑 (11 tests)
  test_researcher.py   # JSON 解析三级降级 (21 tests)
  test_writer.py       # validate_report + _build_prompt (11 tests)
  test_graph.py        # 图编译、状态定义、节点注册 (4 tests)
  test_integration.py  # mock 全流程 + 截断检测 + 续写 (8 tests)
```

运行：`python -m pytest tests/ -v`（55 tests, 不依赖真实 API）

测试覆盖：
- 去重：空列表、无重复、按 source 去重、按 title 去重、混合、边界
- JSON 解析：代码块、纯数组、叙述包裹、尾部逗号、单引号、Python 字面量
- 降级兜底：对象片段提取
- Writer 校验：空报告、错误标记、章节完整性、来源引用
- 截断检测：结尾标题、缺失章节、完整报告判断
- 集成：全流程 mock（搜索→Researcher→Writer→报告）、空搜索兜底
- Graph：状态定义、编译、节点注册、结构

---

## 5. 已知问题 / 待办

### 高优先级

- **(已解决) 代理配置依赖本地工具**。DD 搜索已实现自动兜底：配置 proxy → 失败 → 自动降级直连。`.env.example` 有代理说明。`/health` 端点及启动探针包含连通性检查。

### 中优先级

- **(已解决) Writer 无质量校验**。已实现 `validate_report()` 检查标题/章节/引用/错误标记，失败自动修复一轮。

### 剩余（如需实施）

- **无异步支持**。当前 LangGraph 调用是同步的，高并发时会阻塞。
  - 涉及：api.py (async def → sync invoke)、LangGraph 异步编译接口
  - 复杂度：中，但改动范围大，需要重构 graph.py 和 api.py 调用链

---

## 6. 运行方式

```bash
# 1. 配置环境变量（API Key、代理等）
cp .env.example .env
# 编辑 .env 填入配置

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# 4. 测试
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "2026年AI发展趋势"}'

# Docker
docker build -t collab-agent-mvp .
docker run -p 8000:8000 --env-file .env collab-agent-mvp
```

---

## 7. 开发模式 / 注意事项

### 核心原则

1. **搜索永不抛异常** — 所有失败返回 `[]`。Writer 必须能处理空结果。
2. **LLM 调用失败是预期行为** — Researcher 有两层降级兜底，Writer 有异常处理。
3. **状态图中 `error` 字段只用于"致命错误"**（如 LLM 调用彻底失败导致无法生成报告）。搜索失败不是致命错误。

### 修改文件的顺序（给 AI 开发者）

```
1. 先读 ITERATION.md（本文件）→ 了解架构和历史
2. 再读 config.py → 了解环境配置
3. 再读 tools/search.py → 底层工具
4. 再读 agents/researcher.py 和 writer.py → 业务逻辑
5. 最后改
```

### 日志级别

- `INFO` — 正常流程（搜索返回、节点执行）
- `WARNING` — 预期内的失败（搜索失败、重试、兜底）
- `ERROR` — 非预期失败（LLM 调用失败、配置错误）

---

## 8. 环境变量清单

| 变量 | 必需 | 默认值 | 说明 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | 是 | — | DeepSeek API Key（优先） |
| `OPENAI_API_KEY` | 否 | — | 兼容 Key（当 DEEPSEEK 未设置时使用） |
| `OPENAI_BASE_URL` | 否 | `https://api.deepseek.com` | LLM 接口地址 |
| `OPENAI_MODEL_NAME` | 否 | `deepseek-v4-flash` | 模型名 |
| `TAVILY_API_KEY` | 否 | — | Tavily 搜索（有空时配置以防 DD 限速） |
| `USE_DUCKDUCKGO` | 否 | `true` | 是否优先使用 DuckDuckGo |
| `HTTP_PROXY` | 否 | — | HTTP 代理（中国大陆网络必需） |
| `HTTPS_PROXY` | 否 | — | HTTPS 代理 |
