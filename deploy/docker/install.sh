#!/bin/bash
# ============================================================
# 布林带收缩策略扫描器 - Docker 一键部署脚本
# 
# 功能：自动安装 Docker + Docker Compose，然后部署应用
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
# 配置
# ============================================================
APP_DIR="/opt/stock-scanner"
GITHUB_REPO="https://github.com/Baili-BL/facSstock.git"

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
# 安装 Docker
# ============================================================
install_docker() {
    log_info "检查 Docker..."
    
    if command -v docker &> /dev/null; then
        log_warn "Docker 已安装，跳过"
        docker --version
        return
    fi
    
    log_info "安装 Docker..."
    
    # 安装依赖
    apt-get update
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # 添加 Docker 官方 GPG 密钥
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # 设置稳定版仓库
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # 安装 Docker Engine
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # 启动 Docker
    systemctl enable docker
    systemctl start docker
    
    log_info "Docker 安装完成"
    docker --version
}

# ============================================================
# 安装 Docker Compose
# ============================================================
install_docker_compose() {
    log_info "检查 Docker Compose..."
    
    if command -v docker-compose &> /dev/null; then
        log_warn "Docker Compose 已安装，跳过"
        docker-compose --version
        return
    fi
    
    log_info "安装 Docker Compose..."
    
    # 下载最新版本
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    
    chmod +x /usr/local/bin/docker-compose
    
    log_info "Docker Compose 安装完成"
    docker-compose --version
}

# ============================================================
# 克隆代码
# ============================================================
clone_code() {
    log_info "克隆代码到 ${APP_DIR}..."
    
    # 安装 git
    apt-get install -y git
    
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
# 启动服务
# ============================================================
start_services() {
    log_info "启动 Docker 服务..."
    
    cd ${APP_DIR}/deploy/docker
    
    # 构建并启动
    docker-compose up -d --build
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10
    
    # 检查状态
    docker-compose ps
    
    log_info "服务启动完成"
}

# ============================================================
# 打印完成信息
# ============================================================
print_success() {
    PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "获取失败")
    
    echo ""
    echo "============================================================"
    echo -e "${GREEN}🎉 Docker 部署完成！${NC}"
    echo "============================================================"
    echo ""
    echo "访问地址："
    echo "  - http://${PUBLIC_IP}:5001"
    echo ""
    echo "常用命令："
    echo "  - 查看状态: cd ${APP_DIR}/deploy/docker && docker-compose ps"
    echo "  - 查看日志: cd ${APP_DIR}/deploy/docker && docker-compose logs -f app"
    echo "  - 重启服务: cd ${APP_DIR}/deploy/docker && docker-compose restart"
    echo "  - 停止服务: cd ${APP_DIR}/deploy/docker && docker-compose down"
    echo "  - 更新部署: cd ${APP_DIR} && git pull && cd deploy/docker && docker-compose up -d --build"
    echo ""
    echo "MySQL 信息："
    echo "  - 容器内访问: mysql -h mysql -u root -pStockPass2024"
    echo "  - 数据库: stock_scanner"
    echo ""
    echo "============================================================"
}

# ============================================================
# 主函数
# ============================================================
main() {
    echo ""
    echo "============================================================"
    echo "  布林带收缩策略扫描器 - Docker 一键部署"
    echo "============================================================"
    echo ""
    
    check_system
    install_docker
    install_docker_compose
    clone_code
    start_services
    print_success
}

main "$@"
