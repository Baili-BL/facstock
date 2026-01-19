#!/bin/bash
# ============================================
# 布林带收缩策略 - 腾讯云一键部署脚本
# 支持 Anaconda 环境
# GitHub: https://github.com/Baili-BL/facstock
# ============================================

set -e

# ==================== 配置变量 ====================
APP_NAME="facstock"
APP_PORT=5001
APP_DIR="/opt/$APP_NAME"
GITHUB_REPO="https://github.com/Baili-BL/facstock.git"
CONDA_ENV_NAME="facstock_env"

# 如需部署多个应用，修改以下变量
# APP_NAME="facstock_app2"
# APP_PORT=5002
# CONDA_ENV_NAME="facstock_env2"

echo "=========================================="
echo "🚀 开始部署 $APP_NAME"
echo "📦 仓库: $GITHUB_REPO"
echo "🔌 端口: $APP_PORT"
echo "=========================================="

# 1. 系统更新和依赖安装
echo ""
echo "[1/8] 📥 安装系统依赖..."
apt update
apt install -y git nginx supervisor ufw

# 2. 配置 Conda 环境
echo ""
echo "[2/8] 🐍 配置 Python 环境..."

# 检测 conda
CONDA_PATH=""
for path in "$HOME/miniconda" "/root/miniconda" "/root/miniconda3" "/root/anaconda3" "/opt/anaconda3" "$HOME/anaconda3"; do
    if [ -d "$path" ] && [ -f "$path/bin/conda" ]; then
        CONDA_PATH="$path"
        break
    fi
done

if [ -z "$CONDA_PATH" ]; then
    echo "⚠️ 未检测到 Conda，自动安装 Miniconda (Python 3.10)..."
    
    # 使用清华镜像下载 Miniconda
    cd /tmp
    wget -q --show-progress https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-py310_23.1.0-1-Linux-x86_64.sh -O miniconda.sh
    
    # 静默安装到用户目录
    bash miniconda.sh -b -p $HOME/miniconda
    rm miniconda.sh
    
    CONDA_PATH="$HOME/miniconda"
    
    # 初始化 conda
    $CONDA_PATH/bin/conda init bash
    
    echo "✅ Miniconda 3.10 安装完成: $CONDA_PATH"
fi

echo "✅ 使用 Conda: $CONDA_PATH"
export PATH="$CONDA_PATH/bin:$PATH"
source "$CONDA_PATH/etc/profile.d/conda.sh"

# 配置清华镜像源加速
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --set show_channel_urls yes

# 创建或更新 conda 环境
if conda env list | grep -q "^$CONDA_ENV_NAME "; then
    echo "环境 $CONDA_ENV_NAME 已存在，激活中..."
    conda activate $CONDA_ENV_NAME
else
    echo "创建 conda 环境 $CONDA_ENV_NAME (Python 3.10)..."
    conda create -y -n $CONDA_ENV_NAME python=3.10
    conda activate $CONDA_ENV_NAME
fi

PYTHON_CMD="$CONDA_PATH/envs/$CONDA_ENV_NAME/bin/python"
PIP_CMD="$CONDA_PATH/envs/$CONDA_ENV_NAME/bin/pip"
GUNICORN_CMD="$CONDA_PATH/envs/$CONDA_ENV_NAME/bin/gunicorn"

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

# 5. 安装 Python 依赖
echo ""
echo "[5/8] 📦 安装 Python 依赖..."
cd $APP_DIR

# 使用 conda 环境
source "$CONDA_PATH/etc/profile.d/conda.sh"
conda activate $CONDA_ENV_NAME
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
pip install gunicorn -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 6. 配置 Supervisor
echo ""
echo "[6/8] ⚙️ 配置 Supervisor..."

# gunicorn 路径
GUNICORN_CMD="$CONDA_PATH/envs/$CONDA_ENV_NAME/bin/gunicorn"

cat > /etc/supervisor/conf.d/$APP_NAME.conf <<EOF
[program:$APP_NAME]
command=$GUNICORN_CMD -w 2 -b 0.0.0.0:$APP_PORT app:app
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
environment=PYTHONUNBUFFERED=1,PATH="$CONDA_PATH/envs/$CONDA_ENV_NAME/bin:%(ENV_PATH)s"
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
echo "🐍 Conda 环境: $CONDA_ENV_NAME"
echo "   - 激活环境: conda activate $CONDA_ENV_NAME"
echo ""
echo "🔧 常用命令:"
echo "   - 查看状态: supervisorctl status $APP_NAME"
echo "   - 重启应用: supervisorctl restart $APP_NAME"
echo "   - 查看日志: tail -f $APP_DIR/logs/supervisor_out.log"
echo "   - 更新代码: cd $APP_DIR && git pull && supervisorctl restart $APP_NAME"
echo ""
echo "⚠️ 记得在腾讯云安全组开放端口: 80, $APP_PORT"
echo "=========================================="
