# CollabAgent MVP

**多 AI Agent 协作研究报告生成系统 — 最小可行产品**

用户输入研究主题 → Researcher 搜索信息 → Writer 撰写报告 → 返回结构化 Markdown。
配备 Vue 3 + Element Plus 前端，提供实时 SSE 流式进度展示。

---

## 系统架构

```
用户 → 前端 (Vue 3 + Element Plus)
         │  SSE /research/stream?topic=...
         ▼
  FastAPI (api.py)
         │
         ▼
  LangGraph StateGraph (graph.py)
         │
         ├─ researcher_node  搜索研究员 (agents/researcher.py)
         │     └─ search() → DuckDuckGo / Tavily (tools/search.py)
         │
         └─ writer_node      报告撰写员 (agents/writer.py)
               ├─ 质量校验 validate_report()
               ├─ 自动修复 (校验失败 → LLM 重写)
               └─ 截断检测续写 _is_truncated() + _continue_report()
               │
               ▼
         返回 Markdown 报告 → 前端渲染展示
```

- **2 个 Agent**：Researcher（搜索研究员）、Writer（报告撰写员）
- **1 条线性工作流**：研究 → 撰写
- **前端**：Vue 3 + Element Plus，支持 SSE 实时流式进度展示
- **API 接口**：`POST /research` + `GET /research/stream`(SSE) + `GET /health`

---

## 技术栈

| 组件 | 选型 |
|---|---|
| 编排框架 | LangGraph 0.2+ |
| Agent 框架 | LangChain 0.3+ |
| 后端 API | FastAPI + Uvicorn |
| LLM | DeepSeek (OpenAI 兼容接口) |
| 默认搜索 | DuckDuckGo 免费搜索 |
| 备用搜索 | Tavily Search API（可选） |
| 状态持久化 | LangGraph MemorySaver（内存级） |
| 测试 | pytest（55 个测试，不依赖真实 API） |
| 前端框架 | Vue 3 + Vite |
| UI 组件库 | Element Plus |
| 容器 | Docker (python:3.11-slim) |

---

## 功能特性

| 特性 | 说明 |
|---|---|
| 🔍 **双引擎搜索** | DuckDuckGo 默认 + Tavily 备用，自动降级 |
| 🌐 **代理自动兜底** | 配置 proxy → 失败 → 自动尝试直连 |
| 📋 **质量校验** | 报告自动检查标题/章节/来源引用完整性 |
| 🔧 **自动修复** | 校验不通过 → LLM 接收 issue 列表重写一轮 |
| ✂️ **截断检测续写** | 检测到报告被截断 → 自动续写拼接 |
| 🔄 **去重** | 多轮搜索结果按 source 去重 |
| 🧪 **测试覆盖** | 55 个单元测试 + mock 集成测试 |
| 🐳 **容器化** | 多阶段 Dockerfile 构建 |
| 🖥️ **Web 前端** | Vue 3 + Element Plus，SSE 实时流式进度展示 |
| 🔌 **SSE 流式接口** | `GET /research/stream` 实时推送 Agent 工作进度 |
| 🩺 **配置探针** | 启动时快速检查搜索/LLM 配置状态（不阻塞） |

---

## 快速开始

### 1. 环境配置

```bash
cd collab-agent-mvp

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
```

编辑 `.env` 文件：

```env
# DeepSeek (优先) 或 OpenAI 兼容接口
DEEPSEEK_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL_NAME=deepseek-v4-flash

# Tavily 搜索（可选，DD 限速时兜底）
TAVILY_API_KEY=tvly-your-key-here

# 中国大陆用户需配置代理
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

### 2. 启动后端服务

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### 3. 启动前端（开发模式）

新开一个终端：

```bash
cd web
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，会自动代理 API 请求到后端。

**生产部署：** 前端构建后由 FastAPI 自动托管：

```bash
cd web
npm run build   # 产出 dist/，api.py 自动挂载
```

### 4. 调用 API

```bash
# 非流式接口
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "2026年全球人工智能发展趋势"}'

# 流式 SSE 接口（推荐，前端使用）
curl http://localhost:8000/research/stream?topic=2026年全球人工智能发展趋势
```

### 5. 健康检查

```bash
curl http://localhost:8000/health
```

返回搜索和 LLM 配置状态：

```json
{
  "status": "ok",
  "service": "CollabAgent MVP",
  "checks": {
    "duckduckgo": "unavailable",
    "tavily": "not_configured",
    "llm_key": "configured"
  }
}
```

### 6. 运行测试

```bash
python -m pytest tests/ -v
```

### 7. Docker

```bash
docker build -t collab-agent-mvp .
docker run -p 8000:8000 --env-file .env collab-agent-mvp
```

---

## 项目结构

```
collab-agent-mvp/
├── api.py                 # FastAPI 服务入口（含启动探针）
├── config.py              # 配置加载（DeepSeek/搜索/代理）
├── graph.py               # LangGraph 状态图定义与编译
├── requirements.txt       # 依赖清单
├── Dockerfile             # 多阶段容器构建
├── .env.example           # 环境变量模板
├── ITERATION.md           # 迭代开发文档（AI 接力用）
│
├── tools/
│   └── search.py          # 搜索工具（DD/Tavily/去重/代理降级）
│
├── agents/
│   ├── researcher.py      # 搜索研究员（tool calling loop + JSON 三级降级）
│   └── writer.py          # 报告撰写员（校验/修复/截断检测/续写）
│
├── web/                   # Vue 3 + Element Plus 前端
│   ├── src/
│   │   ├── App.vue           # 主界面
│   │   ├── main.js           # 入口
│   │   └── components/
│   │       ├── ResearchInput.vue   # 研究主题输入
│   │       ├── ProgressPanel.vue   # SSE 实时进度展示
│   │       └── ReportPanel.vue     # 报告展示+下载
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
└── tests/
    ├── test_search.py      # 去重逻辑 (11)
    ├── test_researcher.py  # JSON 解析降级 (21)
    ├── test_writer.py      # 质量校验 (11)
    ├── test_graph.py       # 图结构 (4)
    └── test_integration.py # mock 全流程 (8)
```

---

## 开发迭代记录

参见 `ITERATION.md`，包含完整的架构说明、已修复问题、已知限制。

| 迭代 | 内容 |
|---|---|---|
| Iteration 1 | 基础设施搭建（FastAPI + LangGraph + Agent 骨架） |
| Iteration 2 | Bug 修复 8 项（JSON 解析、tool loop、SDK 兼容等） |
| Iteration 3 | 容器化（Dockerfile + .dockerignore） |
| Iteration 4 | 搜索去重 + JSON 三级降级 + 单元测试 |
| Iteration 5 | Writer 质量校验 + 自动修复 + Graph 测试 |
| Iteration 6 | 截断检测续写 + mock 集成测试 |
| Iteration 7 | 代理自动兜底 + 启动连通性探针 |
| Iteration 8 | Vue 3 + Element Plus 前端 + SSE 流式展示 + 搜索/探针优化 |

---

## 设计原则

1. **搜索永不抛异常** — 所有失败返回 `[]`，Writer 用 LLM 知识兜底
2. **LLM 调用失败是预期行为** — Researcher 有两层降级，Writer 有异常处理
3. **客户体验优先** — 失败快速降级，不重试不阻塞
4. **所有改动需有测试** — 新增功能必须配套测试用例
