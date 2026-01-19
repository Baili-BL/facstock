#!/bin/bash
# ============================================
# 启动应用脚本
# ============================================

APP_NAME="facSstock"
APP_DIR="/opt/$APP_NAME"
APP_PORT=5001
WORKERS=2

echo "启动 $APP_NAME ..."

# 方式1: 使用 Supervisor (推荐)
sudo supervisorctl start $APP_NAME

# 方式2: 直接使用 Gunicorn (手动启动时使用)
# cd $APP_DIR
# source venv/bin/activate
# gunicorn -w $WORKERS -b 0.0.0.0:$APP_PORT app:app \
#     --daemon \
#     --access-logfile logs/access.log \
#     --error-logfile logs/error.log \
#     --pid logs/gunicorn.pid

echo "$APP_NAME 已启动在端口 $APP_PORT"
