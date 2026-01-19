#!/bin/bash
# ============================================
# 多应用部署脚本 - 支持 Anaconda
# GitHub: https://github.com/Baili-BL/facstock
# ============================================

set -e

# ==================== 应用配置 ====================
# 格式: "应用名:端口:Git分支:conda环境名"
APPS=(
    "facstock:5001:main:facstock_env"
    # "facstock_test:5002:develop:facstock_env2"
)

GITHUB_REPO="https://github.com/Baili-BL/facstock.git"
BASE_DIR="/opt"

echo "=========================================="
echo "🚀 多应用部署脚本 (Anaconda)"
echo "=========================================="

# 1. 安装系统依赖
echo ""
echo "[Step 1] 📥 安装系统依赖..."
apt update
apt install -y git nginx supervisor ufw

# 2. 检测或安装 Miniconda
echo ""
echo "[Step 2] 🐍 检测 Conda 环境..."

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
    
    # 静默安装
    bash miniconda.sh -b -p $HOME/miniconda
    rm miniconda.sh
    
    CONDA_PATH="$HOME/miniconda"
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

# 部署每个应用
for app_config in "${APPS[@]}"; do
    IFS=':' read -r APP_NAME APP_PORT BRANCH CONDA_ENV_NAME <<< "$app_config"
    APP_DIR="$BASE_DIR/$APP_NAME"
    
    echo ""
    echo "=========================================="
    echo "📦 部署: $APP_NAME (端口: $APP_PORT, 环境: $CONDA_ENV_NAME)"
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
    
    # 创建 conda 环境
    if ! conda env list | grep -q "^$CONDA_ENV_NAME "; then
        echo "创建 conda 环境 $CONDA_ENV_NAME (Python 3.10)..."
        conda create -y -n $CONDA_ENV_NAME python=3.10
    fi
    
    # 安装依赖
    cd $APP_DIR
    conda activate $CONDA_ENV_NAME
    pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
    pip install gunicorn -i https://pypi.tuna.tsinghua.edu.cn/simple/
    conda deactivate
    
    # 配置 Supervisor
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

    ufw allow $APP_PORT/tcp
    echo "✅ $APP_NAME 配置完成"
done

# 重新加载 Supervisor
echo ""
echo "[Step 3] ⚙️ 启动应用..."
supervisorctl reread
supervisorctl update

for app_config in "${APPS[@]}"; do
    IFS=':' read -r APP_NAME APP_PORT BRANCH CONDA_ENV_NAME <<< "$app_config"
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
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "📍 访问地址:"
for app_config in "${APPS[@]}"; do
    IFS=':' read -r APP_NAME APP_PORT BRANCH CONDA_ENV_NAME <<< "$app_config"
    echo "   - $APP_NAME: http://服务器IP:$APP_PORT (环境: $CONDA_ENV_NAME)"
done
echo ""
echo "🔧 管理命令:"
echo "   - 查看状态: supervisorctl status"
echo "   - 重启应用: supervisorctl restart 应用名"
echo "   - 查看日志: tail -f /opt/应用名/logs/supervisor_out.log"
echo ""
