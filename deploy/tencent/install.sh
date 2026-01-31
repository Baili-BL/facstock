#!/bin/bash
# ============================================================
# 布林带收缩策略扫描器 - 腾讯云 Ubuntu 一键部署脚本
# 
# 使用方法：
#   chmod +x install.sh && ./install.sh
# ============================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# 配置变量（根据需要修改）
# ============================================================
APP_NAME="stock-scanner"
APP_DIR="/opt/stock-scanner"
GITHUB_REPO="https://github.com/Baili-BL/facSstock.git"
MYSQL_ROOT_PASSWORD="StockPass@2024"  # 生产环境请修改！
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
    
    if command -v mysql &> /dev/null; then
        log_warn "MySQL 已安装，跳过"
        return
    fi
    
    apt-get install -y mysql-server mysql-client libmysqlclient-dev
    
    systemctl enable mysql
    systemctl start mysql
    
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
    
    # 配置 git（解决网络问题）
    git config --global http.version HTTP/1.1
    git config --global http.postBuffer 524288000
    
    if [ -d "${APP_DIR}" ]; then
        log_warn "目录已存在，更新代码..."
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
    
    python3 -m venv venv
    source venv/bin/activate
    
    pip install --upgrade pip
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install gunicorn
    
    log_info "Python 环境配置完成"
}

# ============================================================
# 配置 Systemd 服务
# ============================================================
setup_systemd() {
    log_info "配置 Systemd 服务..."
    
    cat > /etc/systemd/system/${APP_NAME}.service << EOF
[Unit]
Description=Stock Scanner - Bollinger Squeeze Strategy
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
Environment=PATH=${APP_DIR}/venv/bin:/usr/bin
Environment=MYSQL_HOST=localhost
Environment=MYSQL_PORT=3306
Environment=MYSQL_USER=root
Environment=MYSQL_PASSWORD=${MYSQL_ROOT_PASSWORD}
Environment=MYSQL_DATABASE=${MYSQL_DATABASE}
ExecStart=${APP_DIR}/venv/bin/gunicorn -w 2 -b 127.0.0.1:${APP_PORT} --timeout 300 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable ${APP_NAME}
    systemctl start ${APP_NAME}
    
    log_info "Systemd 服务配置完成"
}

# ============================================================
# 配置 Nginx
# ============================================================
setup_nginx() {
    log_info "配置 Nginx..."
    
    cat > /etc/nginx/sites-available/${APP_NAME} << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
    }
}
EOF
    
    ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    nginx -t
    systemctl enable nginx
    systemctl reload nginx
    
    log_info "Nginx 配置完成"
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
    echo ""
    echo "MySQL 信息："
    echo "  - 用户: root"
    echo "  - 密码: ${MYSQL_ROOT_PASSWORD}"
    echo "  - 数据库: ${MYSQL_DATABASE}"
    echo ""
    echo "常用命令："
    echo "  - 查看状态: systemctl status ${APP_NAME}"
    echo "  - 重启应用: systemctl restart ${APP_NAME}"
    echo "  - 查看日志: journalctl -u ${APP_NAME} -f"
    echo "  - 更新代码: cd ${APP_DIR} && git pull && systemctl restart ${APP_NAME}"
    echo ""
    echo "============================================================"
}

# ============================================================
# 主函数
# ============================================================
main() {
    echo ""
    echo "============================================================"
    echo "  布林带收缩策略扫描器 - 腾讯云一键部署"
    echo "============================================================"
    echo ""
    
    check_system
    install_dependencies
    install_mysql
    clone_code
    setup_python
    setup_systemd
    setup_nginx
    print_success
}

main "$@"
