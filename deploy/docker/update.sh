#!/bin/bash
# ============================================================
# Docker 部署更新脚本
# ============================================================

set -e

APP_DIR="/opt/stock-scanner"

# 兼容 docker compose v2 plugin 和 standalone docker-compose
COMPOSE_CMD="docker compose"
if ! docker compose version &>/dev/null; then
    COMPOSE_CMD="docker-compose"
fi

echo "📦 更新代码..."
cd ${APP_DIR}
git pull origin main || git pull origin master

echo "🔄 重新构建并启动..."
cd deploy/docker
${COMPOSE_CMD} down 2>/dev/null || true
${COMPOSE_CMD} up -d --build

echo "⏳ 等待服务启动..."
sleep 15

echo "✅ 更新完成！"
${COMPOSE_CMD} ps
