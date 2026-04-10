# 布林带收缩策略扫描器 - Docker 镜像（包含前端构建）
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=Asia/Shanghai

# ==================== 安装 Node.js + 系统依赖（合并为一步） ====================
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ==================== 复制项目文件 ====================
WORKDIR /app

# 复制 Python 依赖
COPY requirements.txt .

# 复制前端配置（用于 npm install + build）
COPY frontend/package.json frontend/vite.config.js frontend/index.html ./frontend/
COPY frontend/src ./frontend/src
COPY frontend/vite-plugins ./frontend/vite-plugins
COPY public ./public

# 复制后端所有文件（dist/ 不在此阶段复制，构建后再处理）
COPY app.py .
COPY strategy_routes.py .
COPY market_routes.py .
COPY market_data.py .
COPY tv_udf_routes.py .
COPY ai_service.py .
COPY agent_prompts.py .
COPY junge_trader.py .
COPY database.py .
COPY cache.py .
COPY a_share_session.py .
COPY bollinger_squeeze_strategy.py .
COPY ticai/ ./ticai/
COPY utils/ ./utils/
COPY charting_library/ ./charting_library/

# TradingView 核心 JS 文件实际在 charting_library/charting_library/ 子目录下，
# 但 mobile_white.html 的 library_path='charting_library/'，
# TV 会请求 charting_library/charting_library.standalone.js，
# 所以把核心文件复制到根目录，与 mobile_white.html 平级
RUN cp charting_library/charting_library/charting_library.standalone.js charting_library/ && \
    cp charting_library/charting_library/charting_library.js charting_library/ && \
    cp charting_library/charting_library/charting_library.esm.js charting_library/ && \
    cp charting_library/charting_library/charting_library.cjs.js charting_library/ || true

# ==================== 构建前端 ====================
WORKDIR /app/frontend
RUN npm install && npm run build

# ==================== 将构建产物移到 /app/dist ====================
WORKDIR /app
RUN mv frontend/dist ./dist || true

# ==================== 安装 Python 依赖 ====================
RUN pip install --no-cache-dir --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple/ -r requirements.txt gunicorn || \
    pip install --no-cache-dir --default-timeout=300 -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt gunicorn

# ==================== 清理 ====================
RUN apt-get purge -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.npm \
    && find . -name "node_modules" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find . -name "*.pyc" -delete 2>/dev/null || true

# 暴露端口
EXPOSE 5002

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "2", "--threads", "4", "--timeout", "300", "app:app"]
