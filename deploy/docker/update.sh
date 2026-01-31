#!/bin/bash
# ============================================================
# Docker 部署更新脚本
# ============================================================

set -e

APP_DIR="/opt/stock-scanner"

echo "📦 更新代码..."
cd ${APP_DIR}
git pull origin main || git pull origin master

echo "🔄 重新构建并启动..."
cd deploy/docker
docker-compose up -d --build

echo "⏳ 等待服务启动..."
sleep 5

echo "✅ 更新完成！"
docker-compose ps
