# IdleAgent 后端镜像（含 Playwright + Chromium）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HEADLESS=true \
    BROWSER_PROFILE=/app/state/profile

WORKDIR /app

# 先装依赖（利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install -r requirements.txt

# 安装 Chromium 及系统依赖
RUN playwright install --with-deps chromium

# 复制代码
COPY . .

# 运行时数据目录
RUN mkdir -p /app/state

EXPOSE 8000

# 绑定 0.0.0.0 + 云平台注入的 $PORT（本地默认 8000）
CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
