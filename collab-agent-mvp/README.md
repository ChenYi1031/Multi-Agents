# CollabAgent MVP

**多 AI Agent 协作研究报告生成系统 - 最小可行产品**

用户输入研究主题 → 搜索研究员收集信息 → 报告撰写员生成结构化 Markdown 报告。

## 系统架构

```
用户 → FastAPI (/research) → LangGraph StateGraph (2 节点)
                                ├─ research_node (SearchResearcher)
                                └─ writing_node (ReportWriter)
                                → 返回 final_report
```

- **2 个 Agent**：SearchResearcher（搜索研究员）、ReportWriter（报告撰写员）
- **1 条线性工作流**：研究 → 撰写
- **FastAPI 接口**：`POST /research` 触发任务并获取结果

## 技术栈

| 组件         | 选型                                   |
| ------------ | -------------------------------------- |
| 编排框架     | LangGraph 0.2+                         |
| Agent 框架   | LangChain 0.3+                         |
| 后端 API     | FastAPI + Uvicorn                      |
| 模型         | OpenAI GPT-4o-mini                     |
| 搜索工具     | Tavily Search API / DuckDuckGo 免费搜索 |
| 状态持久化   | LangGraph MemorySaver（内存级）         |

## 快速开始

### 1. 环境配置

```bash
cd collab-agent-mvp

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key：

```env
OPENAI_API_KEY=sk-your-openai-api-key-here
TAVILY_API_KEY=tvly-your-tavily-api-key-here

# 如需使用 DuckDuckGo 免费搜索（无需 API Key）：
USE_DUCKDUCKGO=true
```

### 2. 启动服务

#### 方式一：API 服务

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

#### 方式二：离线测试（不启动 FastAPI）

```bash
python test_graph.py
```

### 3. 调用 API

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "2025年全球人工智能发展趋势"}'
```

**成功响应**（200 OK）：

```json
{
  "status": "completed",
  "final_report": "# ... Markdown 报告 ...",
  "search_results": [
    {
      "title": "...",
      "summary": "...",
      "source": "https://..."
    }
  ]
}
```

**错误响应**（500）：

```json
{
  "status": "error",
  "detail": "搜索工具调用失败: ..."
}
```

### 4. 健康检查

```bash
curl http://localhost:8000/health
```

## 项目结构

```
collab-agent-mvp/
├── requirements.txt      # 依赖清单
├── .env.example          # 环境变量模板
├── .gitignore
├── config.py             # 配置加载
├── tools/
│   └── search.py         # 搜索工具封装（Tavily / DuckDuckGo）
├── agents/
│   ├── researcher.py     # 搜索研究员 Agent
│   └── writer.py         # 报告撰写员 Agent
├── graph.py              # LangGraph 状态图定义与编译
├── api.py                # FastAPI 服务入口
├── test_graph.py         # 离线测试脚本
└── README.md
```

## 验收标准（MVP）

- [x] 发送主题 → 返回包含 2-5 个来源的结构化 Markdown 报告
- [x] 报告包含：标题、摘要、主要发现、结论，每个发现有来源链接
- [x] API 返回正确 JSON 结构，状态码 200
- [x] 错误时返回 500 并包含错误详情
- [x] 代码结构清晰，注释适量，便于后续迭代

## 后续迭代计划

| 迭代 | 功能                                      |
| ---- | ----------------------------------------- |
| V0.2 | 引入数据分析师 Agent + Python 代码执行工具 |
| V0.3 | 辩论子图：研究员-分析师多轮互辩           |
| V0.4 | 质量审核员 Agent + 报告修订循环           |
| V0.5 | Human-in-the-loop 人工审批节点             |
| V0.6 | Redis 会话管理 + 断点续传                 |
| V0.7 | 向量数据库记忆（Chroma）                   |
| V0.8 | Langfuse 全链路追踪与成本监控              |
| V1.0 | 前端 Dashboard（Next.js）                  |
