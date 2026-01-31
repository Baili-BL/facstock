#!/bin/bash
# ============================================================
# 布林带收缩策略扫描器 - 火山引擎 Ubuntu 一键部署脚本
# 
# 使用方法：
#   curl -sSL https://raw.githubusercontent.com/your-repo/main/deploy/volcengine/install.sh | bash
#   或
#   wget -qO- https://raw.githubusercontent.com/your-repo/main/deploy/volcengine/install.sh | bash
#
# 手动执行：
#   chmod +x install.sh && ./install.sh
# ============================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# 配置变量（可根据需要修改）
# ============================================================
APP_NAME="stock-scanner"
APP_DIR="/opt/stock-scanner"
GITHUB_REPO="https://github.com/Baili-BL/facSstock.git"  # 替换为你的仓库
MYSQL_ROOT_PASSWORD="StockPass@2024"  # 生产环境请修改
MYSQL_DATABASE="stock_scanner"
APP_PORT=5001

# ============================================================
# 检查系统
# ============================================================
check_system() {
    log_info "检查系统环境..."
    
    if [ "$(id -u)" != "0" ]; then
        log_error "请使用 root 用户运行此脚本"
        exit 1
    fi
    
    if ! grep -qi "ubuntu" /etc/os-release; then
        log_warn "此脚本针对 Ubuntu 优化，其他系统可能需要调整"
    fi
    
    log_info "系统检查通过"
}

# ============================================================
# 安装系统依赖
# ============================================================
install_dependencies() {
    log_info "更新系统并安装依赖..."
    
    apt-get update
    apt-get install -y \
        git \
        curl \
        wget \
        vim \
        htop \
        supervisor \
        nginx \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        libffi-dev \
        libssl-dev
    
    log_info "系统依赖安装完成"
}

# ============================================================
# 安装 MySQL 8.0
# ============================================================
install_mysql() {
    log_info "安装 MySQL 8.0..."
    
    # 检查是否已安装
    if command -v mysql &> /dev/null; then
        log_warn "MySQL 已安装，跳过"
        return
    fi
    
    # Ubuntu 22.04 默认源就是 MySQL 8.0
    apt-get install -y mysql-server mysql-client libmysqlclient-dev
    
    # 启动 MySQL
    systemctl enable mysql
    systemctl start mysql
    
    # 设置 root 密码和创建数据库
    log_info "配置 MySQL 8.0..."
    mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY '${MYSQL_ROOT_PASSWORD}';" || true
    mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "CREATE DATABASE IF NOT EXISTS ${MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "FLUSH PRIVILEGES;"
    
    log_info "MySQL 8.0 安装配置完成"
}

# ============================================================
# 克隆代码
# ============================================================
clone_code() {
    log_info "克隆代码到 ${APP_DIR}..."
    
    if [ -d "${APP_DIR}" ]; then
        log_warn "目录已存在，备份并更新..."
        cd ${APP_DIR}
        git pull origin main || git pull origin master
    else
        git clone ${GITHUB_REPO} ${APP_DIR}
    fi
    
    log_info "代码克隆完成"
}

# ============================================================
# 配置 Python 环境
# ============================================================
setup_python() {
    log_info "配置 Python 虚拟环境..."
    
    cd ${APP_DIR}
    
    # 创建虚拟环境
    python3 -m venv venv
    source venv/bin/activate
    
    # 升级 pip
    pip install --upgrade pip
    
    # 安装依赖
    pip install -r requirements.txt
    pip install gunicorn
    
    log_info "Python 环境配置完成"
}

# ============================================================
# 配置环境变量
# ============================================================
setup_env() {
    log_info "配置环境变量..."
    
    cat > ${APP_DIR}/.env << EOF
# MySQL 配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_DATABASE=${MYSQL_DATABASE}

# 应用配置
FLASK_ENV=production
EOF
    
    log_info "环境变量配置完成"
}

# ============================================================
# 配置 Supervisor
# ============================================================
setup_supervisor() {
    log_info "配置 Supervisor..."
    
    cat > /etc/supervisor/conf.d/${APP_NAME}.conf << EOF
[program:${APP_NAME}]
directory=${APP_DIR}
command=${APP_DIR}/venv/bin/gunicorn -w 2 -b 127.0.0.1:${APP_PORT} --timeout 120 app:app
user=root
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/${APP_NAME}/error.log
stdout_logfile=/var/log/${APP_NAME}/access.log
environment=MYSQL_HOST="localhost",MYSQL_PORT="3306",MYSQL_USER="root",MYSQL_PASSWORD="${MYSQL_ROOT_PASSWORD}",MYSQL_DATABASE="${MYSQL_DATABASE}"
EOF
    
    # 创建日志目录
    mkdir -p /var/log/${APP_NAME}
    
    # 重载 Supervisor
    supervisorctl reread
    supervisorctl update
    supervisorctl restart ${APP_NAME} || supervisorctl start ${APP_NAME}
    
    log_info "Supervisor 配置完成"
}

# ============================================================
# 配置 Nginx
# ============================================================
setup_nginx() {
    log_info "配置 Nginx..."
    
    cat > /etc/nginx/sites-available/${APP_NAME} << EOF
server {
    listen 80;
    server_name _;  # 替换为你的域名

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # 静态文件缓存
    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
    }
}
EOF
    
    # 启用站点
    ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # 测试并重载
    nginx -t
    systemctl enable nginx
    systemctl reload nginx
    
    log_info "Nginx 配置完成"
}

# ============================================================
# 配置防火墙
# ============================================================
setup_firewall() {
    log_info "配置防火墙..."
    
    # 检查 ufw 是否安装
    if command -v ufw &> /dev/null; then
        ufw allow 22/tcp    # SSH
        ufw allow 80/tcp    # HTTP
        ufw allow 443/tcp   # HTTPS
        ufw allow ${APP_PORT}/tcp  # 应用端口（可选，Nginx 代理后可不开）
        ufw --force enable
    fi
    
    log_info "防火墙配置完成"
}

# ============================================================
# 打印完成信息
# ============================================================
print_success() {
    PUBLIC_IP=$(curl -s ifconfig.me || echo "获取失败")
    
    echo ""
    echo "============================================================"
    echo -e "${GREEN}🎉 部署完成！${NC}"
    echo "============================================================"
    echo ""
    echo "访问地址："
    echo "  - http://${PUBLIC_IP}"
    echo "  - http://${PUBLIC_IP}:${APP_PORT} (直接访问)"
    echo ""
    echo "MySQL 信息："
    echo "  - 用户: root"
    echo "  - 密码: ${MYSQL_ROOT_PASSWORD}"
    echo "  - 数据库: ${MYSQL_DATABASE}"
    echo ""
    echo "常用命令："
    echo "  - 查看状态: supervisorctl status"
    echo "  - 重启应用: supervisorctl restart ${APP_NAME}"
    echo "  - 查看日志: tail -f /var/log/${APP_NAME}/access.log"
    echo "  - 更新代码: cd ${APP_DIR} && git pull && supervisorctl restart ${APP_NAME}"
    echo ""
    echo "============================================================"
}

# ============================================================
# 主函数
# ============================================================
main() {
    echo ""
    echo "============================================================"
    echo "  布林带收缩策略扫描器 - 一键部署脚本"
    echo "============================================================"
    echo ""
    
    check_system
    install_dependencies
    install_mysql
    clone_code
    setup_python
    setup_env
    setup_supervisor
    setup_nginx
    setup_firewall
    print_success
}

# 执行
main "$@"
