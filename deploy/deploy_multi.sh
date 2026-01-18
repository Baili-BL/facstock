#!/bin/bash
# ============================================
# 多应用部署脚本 - 同一台服务器部署多个应用
# GitHub: https://github.com/Baili-BL/facstock
# ============================================

set -e

# ==================== 应用配置 ====================
# 在这里添加你要部署的应用，格式: "应用名:端口:Git分支"
APPS=(
    "facstock:5001:main"
    # "facstock_test:5002:develop"
    # "facstock_v2:5003:v2"
)

GITHUB_REPO="https://github.com/Baili-BL/facstock.git"
BASE_DIR="/opt"
PYTHON_VERSION="3.10"

echo "=========================================="
echo "🚀 多应用部署脚本"
echo "=========================================="

# 安装系统依赖
echo ""
echo "[Step 1] 📥 安装系统依赖..."
sudo apt update
sudo apt install -y git python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python3-pip nginx supervisor ufw

# 部署每个应用
for app_config in "${APPS[@]}"; do
    IFS=':' read -r APP_NAME APP_PORT BRANCH <<< "$app_config"
    APP_DIR="$BASE_DIR/$APP_NAME"
    
    echo ""
    echo "=========================================="
    echo "📦 部署应用: $APP_NAME (端口: $APP_PORT, 分支: $BRANCH)"
    echo "=========================================="
    
    # 创建目录
    sudo mkdir -p $APP_DIR/logs
    
    # 拉取代码
    if [ -d "$APP_DIR/.git" ]; then
        cd $APP_DIR
        sudo git fetch origin
        sudo git checkout $BRANCH
        sudo git pull origin $BRANCH
    else
        sudo rm -rf $APP_DIR/*
        sudo git clone -b $BRANCH $GITHUB_REPO $APP_DIR
    fi
    
    # 创建虚拟环境
    cd $APP_DIR
    if [ ! -d "venv" ]; then
        sudo python${PYTHON_VERSION} -m venv venv
    fi
    sudo $APP_DIR/venv/bin/pip install --upgrade pip
    sudo $APP_DIR/venv/bin/pip install -r requirements.txt
    
    # 配置 Supervisor
    sudo tee /etc/supervisor/conf.d/$APP_NAME.conf > /dev/null <<EOF
[program:$APP_NAME]
command=$APP_DIR/venv/bin/gunicorn -w 2 -b 0.0.0.0:$APP_PORT app:app
directory=$APP_DIR
user=root
autostart=true
autorestart=true
startsecs=5
startretries=3
stdout_logfile=$APP_DIR/logs/supervisor_out.log
stderr_logfile=$APP_DIR/logs/supervisor_err.log
stdout_logfile_maxbytes=50MB
stderr_logfile_maxbytes=50MB
environment=PYTHONUNBUFFERED=1
EOF

    # 开放端口
    sudo ufw allow $APP_PORT/tcp
    
    echo "✅ $APP_NAME 配置完成"
done

# 重新加载 Supervisor
echo ""
echo "[Step 2] ⚙️ 重新加载 Supervisor..."
sudo supervisorctl reread
sudo supervisorctl update

# 启动所有应用
for app_config in "${APPS[@]}"; do
    IFS=':' read -r APP_NAME APP_PORT BRANCH <<< "$app_config"
    sudo supervisorctl restart $APP_NAME 2>/dev/null || sudo supervisorctl start $APP_NAME
done

# 配置 Nginx
echo ""
echo "[Step 3] 🌐 配置 Nginx..."
sudo tee /etc/nginx/sites-available/facstock_multi > /dev/null <<'EOF'
# 多应用 Nginx 配置

server {
    listen 80;
    server_name _;

    # 应用1 - 主应用
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 应用2 - 通过路径访问 (如需要，取消注释)
    # location /app2/ {
    #     proxy_pass http://127.0.0.1:5002/;
    #     proxy_set_header Host $host;
    #     proxy_set_header X-Real-IP $remote_addr;
    # }
}

# 如果有域名，可以配置子域名访问
# server {
#     listen 80;
#     server_name boll.yourdomain.com;
#     location / {
#         proxy_pass http://127.0.0.1:5001;
#     }
# }
EOF

sudo ln -sf /etc/nginx/sites-available/facstock_multi /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
sudo nginx -t && sudo systemctl reload nginx

# 配置防火墙
echo ""
echo "[Step 4] 🔥 配置防火墙..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo ""
echo "=========================================="
echo "✅ 所有应用部署完成！"
echo "=========================================="
echo ""
echo "📍 应用访问地址:"
for app_config in "${APPS[@]}"; do
    IFS=':' read -r APP_NAME APP_PORT BRANCH <<< "$app_config"
    echo "   - $APP_NAME: http://服务器IP:$APP_PORT"
done
echo ""
echo "🔧 管理命令:"
echo "   - 查看所有状态: sudo supervisorctl status"
echo "   - 重启某个应用: sudo supervisorctl restart 应用名"
echo "   - 查看日志: tail -f /opt/应用名/logs/supervisor_out.log"
echo ""
