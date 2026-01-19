#!/bin/bash

# ============================================
# 腾讯云一键部署脚本 - 同时部署多个项目
# 项目1: facstock (布林带收缩策略) - 端口 5001
# 项目2: Ticai (热门题材推荐) - 端口 5002
# ============================================

set -e

echo "============================================"
echo "  腾讯云多项目一键部署脚本"
echo "============================================"

# 项目配置
PROJECTS=(
    "facstock|https://github.com/Baili-BL/facstock.git|5001|app.py"
    "Ticai|https://github.com/Baili-BL/Ticai.git|5002|main.py"
)

APP_DIR="/var/www"
CONDA_ENV_PREFIX="env_"

# ===== 1. 检测并初始化 Conda =====
echo ""
echo "[1/7] 🔍 检测 Anaconda/Miniconda..."

CONDA_PATH=""
for path in "/root/anaconda3" "/opt/anaconda3" "$HOME/anaconda3" "/root/miniconda3" "/opt/miniconda3"; do
    if [ -d "$path" ] && [ -f "$path/bin/conda" ]; then
        CONDA_PATH="$path"
        break
    fi
done

if [ -z "$CONDA_PATH" ]; then
    echo "❌ 未检测到 Anaconda/Miniconda，请先安装"
    echo "   安装命令: wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && bash Miniconda3-latest-Linux-x86_64.sh"
    exit 1
fi

echo "✅ 检测到 Conda: $CONDA_PATH"
export PATH="$CONDA_PATH/bin:$PATH"
source "$CONDA_PATH/etc/profile.d/conda.sh"

# ===== 2. 安装系统依赖 =====
echo ""
echo "[2/7] 📦 安装系统依赖..."
apt update -y
apt install -y nginx supervisor git

# ===== 3. 创建应用目录 =====
echo ""
echo "[3/7] 📁 创建应用目录..."
mkdir -p $APP_DIR

# ===== 4. 克隆/更新项目 =====
echo ""
echo "[4/7] 📥 克隆项目代码..."

for project_info in "${PROJECTS[@]}"; do
    IFS='|' read -r name repo port entry <<< "$project_info"
    project_dir="$APP_DIR/$name"
    
    echo "  → 处理项目: $name"
    
    if [ -d "$project_dir" ]; then
        echo "    更新已有代码..."
        cd "$project_dir"
        git pull origin main || git pull origin master || true
    else
        echo "    克隆新代码..."
        git clone "$repo" "$project_dir"
    fi
done

# ===== 5. 创建 Conda 环境并安装依赖 =====
echo ""
echo "[5/7] 🐍 配置 Python 环境..."

for project_info in "${PROJECTS[@]}"; do
    IFS='|' read -r name repo port entry <<< "$project_info"
    project_dir="$APP_DIR/$name"
    env_name="${CONDA_ENV_PREFIX}${name}"
    
    echo "  → 配置环境: $env_name"
    
    # 创建环境（如果不存在）
    if ! conda env list | grep -q "^$env_name "; then
        echo "    创建 conda 环境 (Python 3.10)..."
        conda create -y -n "$env_name" python=3.10
    else
        echo "    环境已存在，跳过创建"
    fi
    
    # 激活并安装依赖
    conda activate "$env_name"
    
    if [ -f "$project_dir/requirements.txt" ]; then
        echo "    安装依赖..."
        pip install -r "$project_dir/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple/
    fi
    
    # 安装 gunicorn
    pip install gunicorn -i https://pypi.tuna.tsinghua.edu.cn/simple/
    
    conda deactivate
done

# ===== 6. 配置 Supervisor =====
echo ""
echo "[6/7] ⚙️ 配置 Supervisor..."

# 清理旧配置
rm -f /etc/supervisor/conf.d/project_*.conf

for project_info in "${PROJECTS[@]}"; do
    IFS='|' read -r name repo port entry <<< "$project_info"
    project_dir="$APP_DIR/$name"
    env_name="${CONDA_ENV_PREFIX}${name}"
    env_path="$CONDA_PATH/envs/$env_name"
    
    echo "  → 配置 $name (端口 $port)"
    
    cat > "/etc/supervisor/conf.d/project_${name}.conf" << EOF
[program:$name]
directory=$project_dir
command=$env_path/bin/gunicorn -w 2 -b 127.0.0.1:$port ${entry%.py}:app
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/$name.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=3
environment=PATH="$env_path/bin:%(ENV_PATH)s"
EOF
done

# ===== 7. 配置 Nginx =====
echo ""
echo "[7/7] 🌐 配置 Nginx..."

# 获取服务器IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

cat > /etc/nginx/sites-available/multi_projects << EOF
# facstock - 布林带收缩策略
server {
    listen 80;
    server_name ${SERVER_IP};
    
    # 默认显示项目列表
    location = / {
        default_type text/html;
        return 200 '<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>项目列表</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
        .project { background: #f5f5f5; padding: 20px; margin: 15px 0; border-radius: 8px; }
        .project h2 { margin: 0 0 10px 0; }
        .project a { color: #007bff; text-decoration: none; font-size: 18px; }
        .project a:hover { text-decoration: underline; }
        .desc { color: #666; margin-top: 8px; }
    </style>
</head>
<body>
    <h1>🚀 项目列表</h1>
    <div class="project">
        <h2>📊 facstock</h2>
        <a href="/facstock/">布林带收缩策略 →</a>
        <p class="desc">扫描热点板块中布林带收缩的股票</p>
    </div>
    <div class="project">
        <h2>🔥 Ticai</h2>
        <a href="/ticai/">热门题材推荐 →</a>
        <p class="desc">A股热门题材追踪与推荐系统</p>
    </div>
</body>
</html>';
    }
    
    # facstock 项目
    location /facstock/ {
        rewrite ^/facstock/(.*)$ /\$1 break;
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }
    
    # Ticai 项目
    location /ticai/ {
        rewrite ^/ticai/(.*)$ /\$1 break;
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }
}

# 直接端口访问 - facstock
server {
    listen 5001;
    server_name ${SERVER_IP};
    
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 300s;
    }
}

# 直接端口访问 - Ticai  
server {
    listen 5002;
    server_name ${SERVER_IP};
    
    location / {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 300s;
    }
}
EOF

# 启用配置
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/multi_projects /etc/nginx/sites-enabled/

# 测试并重载
nginx -t && systemctl reload nginx

# ===== 启动服务 =====
echo ""
echo "🚀 启动所有服务..."
supervisorctl reread
supervisorctl update
supervisorctl restart all

# ===== 配置防火墙 =====
echo ""
echo "🔥 配置防火墙..."
ufw allow 80/tcp 2>/dev/null || true
ufw allow 5001/tcp 2>/dev/null || true
ufw allow 5002/tcp 2>/dev/null || true

# ===== 完成 =====
echo ""
echo "============================================"
echo "  ✅ 部署完成！"
echo "============================================"
echo ""
echo "📌 访问地址："
echo ""
echo "  项目列表页:  http://${SERVER_IP}/"
echo ""
echo "  facstock (布林带收缩):"
echo "    - http://${SERVER_IP}/facstock/"
echo "    - http://${SERVER_IP}:5001/"
echo ""
echo "  Ticai (热门题材):"
echo "    - http://${SERVER_IP}/ticai/"
echo "    - http://${SERVER_IP}:5002/"
echo ""
echo "📝 常用命令："
echo "  查看状态:    supervisorctl status"
echo "  查看日志:    tail -f /var/log/facstock.log"
echo "              tail -f /var/log/Ticai.log"
echo "  重启服务:    supervisorctl restart all"
echo "============================================"
