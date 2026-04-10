# 布林带收缩策略 - 腾讯云一键部署指南

## 快速部署（推荐）

### 方式一：从本地一键部署（推荐）

**前提条件**：
1. 腾讯云服务器已安装 Docker
2. Mac 本地配置了 SSH 免密登录服务器

**步骤**：

1. **配置部署脚本**

编辑 `deploy/deploy.sh`，修改以下配置：

```bash
SERVER_IP="你的服务器IP"           # 例如：123.45.67.89
SERVER_USER="root"                # 服务器用户名
MYSQL_PASSWORD="你想要的密码"       # MySQL 密码
```

2. **配置 SSH 免密登录**

```bash
# 在 Mac 终端执行
ssh-copy-id root@你的服务器IP
```

3. **执行部署**

```bash
cd ~/Desktop/facSstock
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

---

### 方式二：服务器上手动部署

**步骤**：

1. SSH 连接服务器

```bash
ssh root@你的服务器IP
```

2. 在服务器上执行一键安装

```bash
cd /opt
git clone https://ghproxy.com/https://github.com/Baili-BL/facSstock.git stock-scanner
cd stock-scanner/deploy/docker
chmod +x install.sh
./install.sh
```

3. 启动服务

```bash
docker compose up -d --build
```

---

## 架构说明

```
┌─────────────────────────────────────────────────────────┐
│                    腾讯云轻量服务器                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   MySQL 8   │    │   Nginx     │    │  防火墙     │ │
│  │   (3306)    │    │   (可选)    │    │  (5002)    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                                                │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │  Docker     │                                        │
│  │  (5002)     │                                        │
│  └─────────────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌─────────────┐                                        │
│  │  Flask +    │                                        │
│  │  Gunicorn   │                                        │
│  │  + Vue 前端  │                                        │
│  └─────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 服务管理命令

```bash
# 进入项目目录
cd /opt/stock-scanner/deploy/docker

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f app

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新部署
cd /opt/stock-scanner
git pull
cd deploy/docker
docker compose up -d --build
```

---

## 配置说明

### 环境变量

在 `docker-compose.yml` 中或通过 `.env` 文件配置：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| MYSQL_PASSWORD | StockPass2024 | MySQL root 密码 |
| HTTP_PROXY | 空 | HTTP 代理（服务器IP被封时使用） |
| HTTPS_PROXY | 空 | HTTPS 代理 |

### 端口说明

| 端口 | 协议 | 说明 |
|------|------|------|
| 5001 | TCP | 应用主端口 |

---

## 防火墙配置

在腾讯云控制台开放端口：

1. 进入 [轻量应用服务器控制台](https://console.cloud.tencent.com/lighthouse)
2. 选择你的服务器 → 防火墙
3. 添加规则：

| 端口 | 协议 | 策略 | 说明 |
|------|------|------|------|
| 22 | TCP | 允许 | SSH |
| 5002 | TCP | 允许 | 应用 |

---

## 访问应用

部署完成后，访问：

```
http://你的服务器IP:5002
http://你的服务器IP:5002/frontend
```

---

## 常见问题

### 1. 端口 5001 被占用

```bash
# 查看占用进程
lsof -i :5001

# 杀掉进程
fkill 5001
```

### 2. Docker 容器不断重启

```bash
# 查看日志
docker compose logs app --tail 50

# 完全重建
docker compose down -v
docker compose up -d --build
```

### 3. MySQL 连接失败

检查容器网络：

```bash
docker compose exec app ping mysql
docker compose logs mysql
```

### 4. 前端页面 404

确保 Docker 镜像构建时执行了 `npm run build`，dist 目录存在：

```bash
docker compose exec app ls -la /app/dist/
```

### 5. 金融网站数据获取失败

服务器 IP 可能被封禁，配置 HTTP 代理：

```bash
# 编辑 .env 文件
echo "HTTP_PROXY=http://你的代理IP:端口" >> /opt/stock-scanner/deploy/docker/.env
echo "HTTPS_PROXY=http://你的代理IP:端口" >> /opt/stock-scanner/deploy/docker/.env

# 重启服务
docker compose restart
```

---

## 数据备份

### 备份 MySQL 数据

```bash
docker compose exec mysql mysqldump -u root -pStockPass2024 stock_scanner > backup_$(date +%Y%m%d).sql
```

### 恢复数据

```bash
docker compose exec -i mysql mysql -u root -pStockPass2024 stock_scanner < backup_20240101.sql
```

---

## 更新部署

### 方式一：服务器上 git pull

```bash
cd /opt/stock-scanner
git pull
cd deploy/docker
docker compose up -d --build
```

### 方式二：本地 rsync 同步

```bash
# 在 Mac 本地执行
rsync -avz --progress \
  --exclude='__pycache__/' \
  --exclude='.git/' \
  --exclude='venv/' \
  ~/Desktop/facSstock/ \
  root@你的服务器IP:/opt/stock-scanner/

# 服务器上重建
ssh root@你的服务器IP "cd /opt/stock-scanner/deploy/docker && docker compose up -d --build"
```

---

## 卸载

```bash
# 停止服务
docker compose down

# 删除容器和镜像
docker compose down --rmi all

# 删除数据卷（会丢失数据！）
docker volume rm stock-scanner_mysql_data

# 删除项目目录
rm -rf /opt/stock-scanner
```
