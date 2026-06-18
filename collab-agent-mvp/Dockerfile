# ── 构建阶段 ──
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装依赖到独立目录
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── 运行阶段 ──
FROM python:3.11-slim

WORKDIR /app

# 从构建阶段复制已安装的包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY . .

# 容器内默认使用 DuckDuckGo 搜索（无需 API Key）
ENV USE_DUCKDUCKGO=true
# DeepSeek 默认配置
ENV OPENAI_BASE_URL=https://api.deepseek.com
ENV OPENAI_MODEL_NAME=deepseek-v4-flash

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
