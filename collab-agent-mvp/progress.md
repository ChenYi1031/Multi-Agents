# 进度日志

## 会话 1 (2026-07-13)

### 全部完成 ✓

| # | 功能 | 后端 | 前端 | 状态 |
|---|------|------|------|------|
| **F1** | 导出 (HTML/Markdown) | `POST /research/export/html`、`POST /research/export/markdown` | ReportPanel 导出下拉菜单 | ✓ |
| **F2** | 设置面板 | SSE 接受 `model_name`/`search_source`；researcher/writer `_build_llm` 均支持动态模型 | SettingsPanel.vue 折叠卡片 | ✓ |
| **F3** | 追问 | `POST /research/followup` 端点，保留上下文 + conversation_history | ReportPanel 追问输入框 → 更新报告 | ✓ |
| **F4** | Fact-Checker | `agents/fact_checker.py` 节点，SSE 新增 `fact_check`/`fact_check_done` 阶段 | DAG 四阶段 + 事实核查评分/明细表格 | ✓ |
| **F5** | RAG 知识库 | `tools/rag.py` 内存知识库（TXT/PDF 解析、分块、检索）；researcher 自动注入知识上下文 | KnowledgePanel.vue 上传/搜索/清空 UI | ✓ |
| **F6** | DAG 可视化 | — | DagVisualizer.vue SVG 有向无环图，实时节点状态 | ✓ |

### 验证
- 后端测试：55 项全部通过
- 前端构建：成功
- 模块导入：api、graph、agents、tools 均正常

### 技术债务
- weasyprint Windows 不可用，PDF 导出通过 HTML → 浏览器打印 PDF 间接实现
- RAG 使用内存关键词检索（非向量嵌入），大规模知识库效果有限
- 前端 chunks 较大（Element Plus 全量引入），可按需优化
