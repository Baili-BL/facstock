#!/bin/bash
# ============================================
# 停止应用脚本
# ============================================

APP_NAME="facSstock"

echo "停止 $APP_NAME ..."

# 方式1: 使用 Supervisor
sudo supervisorctl stop $APP_NAME

# 方式2: 直接杀进程
# kill $(cat /opt/$APP_NAME/logs/gunicorn.pid) 2>/dev/null

echo "$APP_NAME 已停止"
