#!/bin/bash
# ============================================================
# 代码更新脚本
# ============================================================

set -e

APP_DIR="/opt/stock-scanner"
APP_NAME="stock-scanner"

echo "📦 更新代码..."
cd ${APP_DIR}
git pull origin main || git pull origin master

echo "📦 更新依赖..."
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "🔄 重启服务..."
systemctl restart ${APP_NAME}

echo "✅ 更新完成！"
systemctl status ${APP_NAME}
