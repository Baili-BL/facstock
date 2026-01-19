#!/bin/bash
# ============================================
# 本地代码部署脚本（跳过 GitHub 克隆）
# 适用于 GitHub 无法访问的情况
# 
# 使用方法：
# 1. 在本地先上传代码：
#    scp -r /path/to/facstock root@服务器IP:/opt/facstock
# 2. 在服务器执行此脚本
# ============================================

set -e

# ==================== 配置 ====================
APP_NAME="facstock"
APP_PORT=5001
APP_DIR="/opt/$APP_NAME"
CONDA_ENV_NAME="facstock_env"

echo "=========================================="
echo "🚀 本地代码部署 $APP_NAME"
echo "=========================================="

# 检查代码是否已上传
if [ ! -f "$APP_DIR/app.py" ]; then
    echo "❌ 未检测到代码文件！"
    echo ""
    echo "请先在本地执行以下命令上传代码："
    echo "  scp -r /path/to/facstock/* root@服务器IP:$APP_DIR/"
    echo ""
    exit 1
fi

echo "✅ 检测到代码文件: $APP_DIR"

# 1. 安装系统依赖
echo ""
echo "[1/5] 📦 安装系统依赖..."
apt update -y
apt install -y nginx supervisor

# 2. 配置 Conda
echo ""
echo "[2/5] 🐍 配置 Python 环境..."

CONDA_PATH=""
for path in "$HOME/miniconda" "/root/miniconda" "/root/miniconda3" "/root/anaconda3"; do
    if [ -d "$path" ] && [ -f "$path/bin/conda" ]; then
        CONDA_PATH="$path"
        break
    fi
done

if [ -z "$CONDA_PATH" ]; then
    echo "⚠️ 安装 Miniconda..."
    cd /tmp
    wget -q --show-progress https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-py310_23.1.0-1-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p $HOME/miniconda
    rm miniconda.sh
    CONDA_PATH="$HOME/miniconda"
    $CONDA_PATH/bin/conda init bash
fi

export PATH="$CONDA_PATH/bin:$PATH"
source "$CONDA_PATH/etc/profile.d/conda.sh"

# 配置镜像源
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --set show_channel_urls yes

# 创建环境
if ! conda env list | grep -q "^$CONDA_ENV_NAME "; then
    conda create -y -n $CONDA_ENV_NAME python=3.10
fi
conda activate $CONDA_ENV_NAME

# 3. 安装依赖
echo ""
echo "[3/5] 📦 安装 Python 依赖..."
cd $APP_DIR
mkdir -p logs
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
pip install gunicorn -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 4. 配置 Supervisor
echo ""
echo "[4/5] ⚙️ 配置服务..."

GUNICORN_CMD="$CONDA_PATH/envs/$CONDA_ENV_NAME/bin/gunicorn"

cat > /etc/supervisor/conf.d/$APP_NAME.conf <<EOF
[program:$APP_NAME]
command=$GUNICORN_CMD -w 2 -b 0.0.0.0:$APP_PORT app:app
directory=$APP_DIR
user=root
autostart=true
autorestart=true
startsecs=5
stdout_logfile=$APP_DIR/logs/supervisor_out.log
stderr_logfile=$APP_DIR/logs/supervisor_err.log
environment=PYTHONUNBUFFERED=1,PATH="$CONDA_PATH/envs/$CONDA_ENV_NAME/bin:%(ENV_PATH)s"
EOF

supervisorctl reread
supervisorctl update
supervisorctl restart $APP_NAME 2>/dev/null || supervisorctl start $APP_NAME

# 5. 配置 Nginx
echo ""
echo "[5/5] 🌐 配置 Nginx..."

cat > /etc/nginx/sites-available/$APP_NAME <<EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 120s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t && systemctl reload nginx

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo "访问: http://服务器IP 或 http://服务器IP:$APP_PORT"
echo ""
