#!/bin/bash
# ============================================
# 布林带收缩策略 - 腾讯云一键部署脚本
# GitHub: https://github.com/Baili-BL/facstock
# ============================================

set -e

# ==================== 配置变量 ====================
APP_NAME="facstock"
APP_PORT=5001
APP_DIR="/opt/$APP_NAME"
GITHUB_REPO="https://github.com/Baili-BL/facstock.git"

# 如需部署多个应用，修改以下变量
# APP_NAME="facstock_app2"
# APP_PORT=5002

echo "=========================================="
echo "🚀 开始部署 $APP_NAME"
echo "📦 仓库: $GITHUB_REPO"
echo "🔌 端口: $APP_PORT"
echo "=========================================="

# 1. 系统更新和依赖安装
echo ""
echo "[1/8] 📥 安装系统依赖..."
apt update
apt install -y git nginx supervisor ufw software-properties-common

# 2. 安装 Python 3.9（通过 deadsnakes PPA）
echo ""
echo "[2/8] 🐍 安装 Python 3.9..."

# 检查当前 Python 版本
CURRENT_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0")
echo "当前 Python 版本: $CURRENT_VERSION"

# 如果版本 < 3.8，安装 Python 3.9
if [ "$(echo "$CURRENT_VERSION < 3.8" | bc -l 2>/dev/null || echo 1)" = "1" ]; then
    echo "Python 版本过低，安装 Python 3.9..."
    add-apt-repository -y ppa:deadsnakes/ppa
    apt update
    apt install -y python3.9 python3.9-venv python3.9-distutils
    
    # 安装 pip for Python 3.9
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.9
    
    PYTHON_CMD="python3.9"
else
    PYTHON_CMD="python3"
    apt install -y python3-venv python3-pip
fi

echo "✅ 使用 Python: $($PYTHON_CMD --version)"

# 3. 创建应用目录
echo ""
echo "[3/8] 📁 创建应用目录..."
mkdir -p $APP_DIR
mkdir -p $APP_DIR/logs

# 4. 从 GitHub 拉取代码
echo ""
echo "[4/8] 📥 从 GitHub 拉取代码..."
if [ -d "$APP_DIR/.git" ]; then
    echo "代码已存在，执行 git pull 更新..."
    cd $APP_DIR
    git pull origin main
else
    echo "首次部署，执行 git clone..."
    rm -rf $APP_DIR/*
    git clone $GITHUB_REPO $APP_DIR
fi

# 5. 创建虚拟环境并安装依赖
echo ""
echo "[5/8] 🐍 创建 Python 虚拟环境..."
cd $APP_DIR
if [ -d "venv" ]; then
    rm -rf venv
fi
$PYTHON_CMD -m venv venv
$APP_DIR/venv/bin/pip install --upgrade pip
$APP_DIR/venv/bin/pip install -r requirements.txt

# 6. 配置 Supervisor
echo ""
echo "[6/8] ⚙️ 配置 Supervisor..."
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

supervisorctl reread
supervisorctl update
supervisorctl restart $APP_NAME 2>/dev/null || supervisorctl start $APP_NAME

# 7. 配置 Nginx
echo ""
echo "[7/8] 🌐 配置 Nginx..."
cat > /etc/nginx/sites-available/$APP_NAME <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t && systemctl reload nginx

# 8. 配置防火墙
echo ""
echo "[8/8] 🔥 配置防火墙..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow $APP_PORT/tcp
ufw --force enable

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "📍 访问地址:"
echo "   - 直接访问: http://服务器IP:$APP_PORT"
echo "   - Nginx代理: http://服务器IP"
echo ""
echo "🔧 常用命令:"
echo "   - 查看状态: supervisorctl status $APP_NAME"
echo "   - 重启应用: supervisorctl restart $APP_NAME"
echo "   - 查看日志: tail -f $APP_DIR/logs/supervisor_out.log"
echo "   - 更新代码: cd $APP_DIR && git pull && supervisorctl restart $APP_NAME"
echo ""
echo "⚠️ 记得在腾讯云安全组开放端口: 80, $APP_PORT"
echo "=========================================="
