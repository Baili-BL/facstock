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
echo "[1/9] 📥 安装系统依赖..."
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nginx supervisor ufw

# 2. 检测 Python 版本
echo ""
echo "[2/9] 🐍 检测 Python 版本..."
PYTHON_CMD=$(which python3)
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
echo "检测到 Python: $PYTHON_VERSION"

# 检查 Python 版本是否 >= 3.8
PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_MINOR" -lt 8 ]; then
    echo "⚠️ Python 版本过低，尝试安装更高版本..."
    sudo apt install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt update
    
    # 尝试安装 Python 3.10, 3.9, 3.8
    for ver in 3.10 3.9 3.8; do
        if sudo apt install -y python${ver} python${ver}-venv python${ver}-distutils 2>/dev/null; then
            PYTHON_CMD="/usr/bin/python${ver}"
            echo "✅ 已安装 Python ${ver}"
            break
        fi
    done
fi

echo "使用 Python: $($PYTHON_CMD --version)"

# 3. 创建应用目录
echo ""
echo "[3/9] 📁 创建应用目录..."
sudo mkdir -p $APP_DIR
sudo mkdir -p $APP_DIR/logs

# 4. 从 GitHub 拉取代码
echo ""
echo "[4/9] 📥 从 GitHub 拉取代码..."
if [ -d "$APP_DIR/.git" ]; then
    echo "代码已存在，执行 git pull 更新..."
    cd $APP_DIR
    sudo git pull origin main
else
    echo "首次部署，执行 git clone..."
    sudo rm -rf $APP_DIR/*
    sudo git clone $GITHUB_REPO $APP_DIR
fi

# 5. 创建虚拟环境并安装依赖
echo ""
echo "[5/9] 🐍 创建 Python 虚拟环境..."
cd $APP_DIR
if [ ! -d "venv" ]; then
    sudo $PYTHON_CMD -m venv venv
fi
sudo $APP_DIR/venv/bin/pip install --upgrade pip
sudo $APP_DIR/venv/bin/pip install -r requirements.txt

# 6. 创建日志目录
echo ""
echo "[6/9] 📝 创建日志目录..."
sudo mkdir -p $APP_DIR/logs
sudo chmod 755 $APP_DIR/logs

# 7. 配置 Supervisor
echo ""
echo "[7/9] ⚙️ 配置 Supervisor..."
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

sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart $APP_NAME 2>/dev/null || sudo supervisorctl start $APP_NAME

# 8. 配置 Nginx（可选，用于域名访问）
echo ""
echo "[8/9] 🌐 配置 Nginx..."
sudo tee /etc/nginx/sites-available/$APP_NAME > /dev/null <<EOF
server {
    listen 80;
    server_name _;  # 替换为你的域名，如 boll.example.com

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
sudo nginx -t && sudo systemctl reload nginx

# 9. 配置防火墙
echo ""
echo "[9/9] 🔥 配置防火墙..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow $APP_PORT/tcp
sudo ufw --force enable

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
echo "   - 查看状态: sudo supervisorctl status $APP_NAME"
echo "   - 重启应用: sudo supervisorctl restart $APP_NAME"
echo "   - 查看日志: tail -f $APP_DIR/logs/supervisor_out.log"
echo "   - 更新代码: cd $APP_DIR && sudo git pull && sudo supervisorctl restart $APP_NAME"
echo ""
echo "=========================================="
