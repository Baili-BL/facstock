#!/bin/bash
# ============================================
# 更新代码脚本
# ============================================

APP_NAME="facstock"
APP_DIR="/opt/$APP_NAME"

echo "🔄 更新 $APP_NAME ..."

cd $APP_DIR

# 拉取最新代码
echo "[1/3] 拉取最新代码..."
sudo git pull origin main

# 更新依赖
echo "[2/3] 更新依赖..."
sudo $APP_DIR/venv/bin/pip install -r requirements.txt

# 重启应用
echo "[3/3] 重启应用..."
sudo supervisorctl restart $APP_NAME

echo ""
echo "✅ 更新完成！"
echo "📍 访问地址: http://服务器IP:5001"
