#!/bin/bash
# ============================================================
# 布林带收缩策略扫描器 - 本地一键部署脚本
# 在 Mac 本地执行，自动构建前端并部署到腾讯云
#
# 使用方法：
#   1. 修改下面的 SERVER_IP 为你的服务器 IP
#   2. chmod +x deploy.sh
#   3. ./deploy.sh
# ============================================================

set -e

# ==================== 配置区（必须修改） ====================
SERVER_IP="111.229.238.115"           # 腾讯云服务器 IP
SERVER_USER="root"                    # 服务器用户名
SERVER_PORT="22"                      # SSH 端口
APP_DIR="/opt/stock-scanner"           # 服务器上的应用目录
MYSQL_PASSWORD="StockPass@2024"        # MySQL 密码（必须与 docker-compose.yml 一致）

# ==================== 颜色输出 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# ==================== 预检查 ====================
pre_check() {
    log_step "执行预检查..."
    
    # 检查配置
    if [ "$SERVER_IP" = "YOUR_SERVER_IP" ]; then
        log_error "请先修改脚本中的 SERVER_IP 为你的服务器 IP！"
        exit 1
    fi
    
    # 检查 SSH 连接
    log_info "检查 SSH 连接..."
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes ${SERVER_USER}@${SERVER_IP} "echo 'SSH OK'" > /dev/null 2>&1; then
        log_error "无法连接到服务器 ${SERVER_IP}，请检查："
        echo "  1. 服务器 IP 是否正确"
        echo "  2. SSH 密钥是否配置（建议使用 ssh-copy-id）"
        echo "  3. 服务器是否正常运行"
        exit 1
    fi
    log_info "SSH 连接正常"
    
    # 检查 rsync
    log_info "检查 rsync..."
    if ! command -v rsync &> /dev/null; then
        log_error "未找到 rsync，请安装: brew install rsync"
        exit 1
    fi
    log_info "rsync 已安装"
}

# ==================== 构建前端（跳过，由 Dockerfile 容器内自动构建） ====================
build_frontend() {
    log_step "前端将在 Docker 容器内自动构建，跳过本地构建"
}

# ==================== 同步代码到服务器 ====================
sync_to_server() {
    log_step "同步代码到服务器..."
    
    log_info "使用 rsync 同步（排除 node_modules, .git 等）..."
    
    rsync -avz --progress \
        -e "ssh -p ${SERVER_PORT}" \
        --exclude='__pycache__/' \
        --exclude='.git/' \
        --exclude='*.pyc' \
        --exclude='venv/' \
        --exclude='.env' \
        --exclude='node_modules/' \
        --exclude='.DS_Store' \
        --exclude='*.log' \
        --exclude='frontend/node_modules/' \
        --exclude='frontend/dist/' \
        --exclude='dist/' \
        "$(dirname "$0")/" \
        ${SERVER_USER}@${SERVER_IP}:${APP_DIR}/
    
    log_info "代码同步完成"
}

# ==================== 服务器端部署 ====================
deploy_server() {
    log_step "执行服务器端部署..."
    
    ssh -t -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
        set -e

        # 兼容 docker compose v2 plugin 和 standalone docker-compose
        if docker compose version &>/dev/null; then
            COMPOSE_CMD="docker compose"
        else
            COMPOSE_CMD="docker-compose"
        fi

        echo "[INFO] 进入部署目录..."
        cd /opt/stock-scanner

        echo "[INFO] 检查 Docker 服务..."
        if ! systemctl is-active --quiet docker; then
            echo "[WARN] Docker 未运行，启动中..."
            systemctl start docker
            systemctl enable docker
        fi

        echo "[INFO] 进入 Docker 目录..."
        cd deploy/docker

        echo "[INFO] 停止旧容器..."
        ${COMPOSE_CMD} down || true

        echo "[INFO] 构建并启动新容器..."
        docker pull ubuntu:22.04 2>/dev/null || true
        ${COMPOSE_CMD} up -d --build

        echo "[INFO] 等待服务启动..."
        sleep 15

        echo "[INFO] 检查容器状态..."
        ${COMPOSE_CMD} ps

        echo "[INFO] 检查应用日志..."
        ${COMPOSE_CMD} logs app --tail 10

        echo ""
        echo "=============================================="
        echo "  部署完成！"
        echo "=============================================="
ENDSSH
    
    log_info "服务器部署完成"
}

# ==================== 验证部署 ====================
verify_deploy() {
    log_step "验证部署..."
    
    # 等待服务启动
    log_info "等待服务启动（10秒）..."
    sleep 10
    
    # 检查 HTTP 响应
    log_info "检查服务响应..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "http://${SERVER_IP}:5002/" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        log_info "✓ 服务响应正常 (HTTP ${HTTP_CODE})"
    else
        log_warn "服务响应异常 (HTTP ${HTTP_CODE})，建议登录服务器检查："
        echo "  ssh ${SERVER_USER}@${SERVER_IP}"
        echo "  docker compose -f /opt/stock-scanner/deploy/docker/docker-compose.yml logs app"
    fi
}

# ==================== 打印完成信息 ====================
print_success() {
    echo ""
    echo "============================================================"
    echo -e "${GREEN}🎉 部署完成！${NC}"
    echo "============================================================"
    echo ""
    echo "访问地址："
    echo "  - http://${SERVER_IP}:5002"
    echo "  - http://${SERVER_IP}:5002/frontend"
    echo ""
    echo "常用命令："
    echo "  - 查看服务状态: ssh ${SERVER_USER}@${SERVER_IP} 'docker compose -f ${APP_DIR}/deploy/docker/docker-compose.yml ps'"
    echo "  - 查看日志: ssh ${SERVER_USER}@${SERVER_IP} 'docker compose -f ${APP_DIR}/deploy/docker/docker-compose.yml logs -f app'"
    echo "  - 重启服务: ssh ${SERVER_USER}@${SERVER_IP} 'docker compose -f ${APP_DIR}/deploy/docker/docker-compose.yml restart'"
    echo "  - SSH 连接: ssh ${SERVER_USER}@${SERVER_IP}"
    echo ""
    echo "============================================================"
}

# ==================== 主函数 ====================
main() {
    echo ""
    echo "============================================================"
    echo "  布林带收缩策略扫描器 - 腾讯云一键部署"
    echo "  服务器: ${SERVER_IP}"
    echo "============================================================"
    echo ""
    
    pre_check
    build_frontend
    sync_to_server
    deploy_server
    verify_deploy
    print_success
}

main "$@"
