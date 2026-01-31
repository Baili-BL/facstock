#!/bin/bash
# ============================================================
# 代码更新脚本
# 
# 使用方法：
#   ./update.sh
# ============================================================

set -e

APP_DIR="/opt/stock-scanner"
APP_NAME="stock-scanner"

echo "📦 更新代码..."
cd ${APP_DIR}
git pull origin main || git pull origin master

echo "📦 更新依赖..."
source venv/bin/activate
pip install -r requirements.txt

echo "🔄 重启服务..."
supervisorctl restart ${APP_NAME}

echo "✅ 更新完成！"
supervisorctl status ${APP_NAME}
