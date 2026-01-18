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

echo "=========================================="
echo "🚀 多应用部署脚本"
echo "=========================================="

# 1. 安装系统依赖
echo ""
echo "[Step 1] 📥 安装系统依赖..."
apt update
apt install -y git nginx supervisor ufw software-properties-common

# 2. 安装 Python 3.9（通过 deadsnakes PPA）
echo ""
echo "[Step 2] 🐍 安装 Python 3.9..."

CURRENT_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0")
echo "当前 Python 版本: $CURRENT_VERSION"

if [ "$(echo "$CURRENT_VERSION < 3.8" | bc -l 2>/dev/null || echo 1)" = "1" ]; then
    echo "Python 版本过低，安装 Python 3.9..."
    add-apt-repository -y ppa:deadsnakes/ppa
    apt update
    apt install -y python3.9 python3.9-venv python3.9-distutils
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.9
    PYTHON_CMD="python3.9"
else
    PYTHON_CMD="python3"
    apt install -y python3-venv python3-pip
fi

echo "✅ 使用 Python: $($PYTHON_CMD --version)"

# 部署每个应用
for app_config in "${APPS[@]}"; do
    IFS=':' read -r APP_NAME APP_PORT BRANCH <<< "$app_config"
    APP_DIR="$BASE_DIR/$APP_NAME"
    
    echo ""
    echo "=========================================="
    echo "📦 部署应用: $APP_NAME (端口: $APP_PORT, 分支: $BRANCH)"
    echo "=========================================="
    
    # 创建目录
    mkdir -p $APP_DIR/logs
    
    # 拉取代码
    if [ -d "$APP_DIR/.git" ]; then
        cd $APP_DIR
        git fetch origin
        git checkout $BRANCH
        git pull origin $BRANCH
    else
        rm -rf $APP_DIR/*
        git clone -b $BRANCH $GITHUB_REPO $APP_DIR
    fi
    
    # 创建虚拟环境
    cd $APP_DIR
    if [ -d "venv" ]; then
        rm -rf venv
    fi
    $PYTHON_CMD -m venv venv
    $APP_DIR/venv/bin/pip install --upgrade pip
    $APP_DIR/venv/bin/pip install -r requirements.txt
    
    # 配置 Supervisor
    cat > /etc/supervisor/conf.d/$APP_NAME.conf <<EOF
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
    ufw allow $APP_PORT/tcp
    
    echo "✅ $APP_NAME 配置完成"
done

# 重新加载 Supervisor
echo ""
echo "[Step 3] ⚙️ 重新加载 Supervisor..."
supervisorctl reread
supervisorctl update

# 启动所有应用
for app_config in "${APPS[@]}"; do
    IFS=':' read -r APP_NAME APP_PORT BRANCH <<< "$app_config"
    supervisorctl restart $APP_NAME 2>/dev/null || supervisorctl start $APP_NAME
done

# 配置 Nginx
echo ""
echo "[Step 4] 🌐 配置 Nginx..."
cat > /etc/nginx/sites-available/facstock_multi <<'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/facstock_multi /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t && systemctl reload nginx

# 配置防火墙
echo ""
echo "[Step 5] 🔥 配置防火墙..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

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
echo "   - 查看所有状态: supervisorctl status"
echo "   - 重启某个应用: supervisorctl restart 应用名"
echo "   - 查看日志: tail -f /opt/应用名/logs/supervisor_out.log"
echo ""
echo "⚠️ 记得在腾讯云安全组开放对应端口！"
echo ""
