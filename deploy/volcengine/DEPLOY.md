# 火山引擎部署指南

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    火山引擎 ECS                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Nginx     │───▶│  Gunicorn   │───▶│   MySQL     │ │
│  │   (80)      │    │   (5001)    │    │   (3306)    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                 │                             │
│         ▼                 ▼                             │
│  ┌─────────────┐    ┌─────────────┐                    │
│  │ Supervisor  │    │   Python    │                    │
│  │  进程管理    │    │   venv      │                    │
│  └─────────────┘    └─────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

---

## 方案一：一键部署（推荐）

### 1. 创建火山引擎 ECS

1. 登录火山引擎控制台 → 云服务器 ECS
2. 创建实例：
   - **镜像**：Ubuntu 22.04 LTS
   - **规格**：2核4G（推荐）或 1核2G（入门）
   - **存储**：40GB 系统盘
   - **网络**：分配公网 IP
   - **安全组**：开放 22、80、5001 端口

### 2. SSH 登录并执行一键脚本

```bash
# SSH 登录
ssh root@<服务器公网IP>

# 方式一：直接执行（需要先上传代码到 GitHub）
curl -sSL https://raw.githubusercontent.com/your-repo/main/deploy/volcengine/install.sh | bash

# 方式二：手动执行
git clone https://github.com/your-repo/stock-scanner.git /opt/stock-scanner
cd /opt/stock-scanner/deploy/volcengine
chmod +x install.sh
./install.sh
```

### 3. 完成！

脚本会自动安装：
- MySQL 数据库
- Python 3 + 虚拟环境
- Nginx 反向代理
- Supervisor 进程管理

访问：`http://<服务器IP>`

---

## 方案二：手动部署（详细步骤）

### 1. 创建 ECS 实例

同上，选择 Ubuntu 22.04

### 2. 安装系统依赖

```bash
# 更新系统
apt update && apt upgrade -y

# 安装基础工具
apt install -y git curl wget vim htop

# 安装 Python
apt install -y python3 python3-pip python3-venv

# 安装编译依赖
apt install -y build-essential libffi-dev libssl-dev
```

### 3. 安装 MySQL 8.0

```bash
# 安装 MySQL 8.0
apt install -y mysql-server mysql-client libmysqlclient-dev

# 启动并设置开机自启
systemctl enable mysql
systemctl start mysql

# 设置 root 密码（MySQL 8.0 使用 caching_sha2_password）
mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'YourPassword123';"

# 创建数据库
mysql -u root -p'YourPassword123' -e "CREATE DATABASE stock_scanner CHARACTER SET utf8mb4;"
```

### 4. 克隆代码

```bash
# 克隆到 /opt 目录
git clone https://github.com/your-repo/stock-scanner.git /opt/stock-scanner
cd /opt/stock-scanner
```

### 5. 配置 Python 环境

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 6. 测试运行

```bash
# 设置环境变量
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=YourPassword123
export MYSQL_DATABASE=stock_scanner

# 测试启动
python app.py

# 访问 http://<IP>:5001 测试
# Ctrl+C 停止
```

### 7. 配置 Supervisor

```bash
# 安装 Supervisor
apt install -y supervisor

# 创建配置文件
cat > /etc/supervisor/conf.d/stock-scanner.conf << 'EOF'
[program:stock-scanner]
directory=/opt/stock-scanner
command=/opt/stock-scanner/venv/bin/gunicorn -w 2 -b 127.0.0.1:5001 --timeout 120 app:app
user=root
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/stock-scanner/error.log
stdout_logfile=/var/log/stock-scanner/access.log
environment=MYSQL_HOST="localhost",MYSQL_PORT="3306",MYSQL_USER="root",MYSQL_PASSWORD="YourPassword123",MYSQL_DATABASE="stock_scanner"
EOF

# 创建日志目录
mkdir -p /var/log/stock-scanner

# 启动
supervisorctl reread
supervisorctl update
supervisorctl start stock-scanner

# 查看状态
supervisorctl status
```

### 8. 配置 Nginx

```bash
# 安装 Nginx
apt install -y nginx

# 创建配置
cat > /etc/nginx/sites-available/stock-scanner << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    location /static/ {
        alias /opt/stock-scanner/static/;
        expires 7d;
    }
}
EOF

# 启用站点
ln -sf /etc/nginx/sites-available/stock-scanner /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 重载
nginx -t && systemctl reload nginx
```

### 9. 配置防火墙

```bash
# 火山引擎安全组配置（控制台操作）
# 入站规则：
# - TCP 22   SSH
# - TCP 80   HTTP
# - TCP 443  HTTPS（如需）
# - TCP 5001 应用（可选）
```

---

## 日常运维

### 查看状态

```bash
supervisorctl status stock-scanner
```

### 重启应用

```bash
supervisorctl restart stock-scanner
```

### 查看日志

```bash
# 应用日志
tail -f /var/log/stock-scanner/access.log

# 错误日志
tail -f /var/log/stock-scanner/error.log

# Nginx 日志
tail -f /var/log/nginx/access.log
```

### 更新代码

```bash
cd /opt/stock-scanner
git pull
source venv/bin/activate
pip install -r requirements.txt
supervisorctl restart stock-scanner
```

或使用更新脚本：

```bash
cd /opt/stock-scanner/deploy/volcengine
./update.sh
```

### 数据库备份

```bash
# 备份
mysqldump -u root -p stock_scanner > backup_$(date +%Y%m%d).sql

# 恢复
mysql -u root -p stock_scanner < backup_20240101.sql
```

---

## 费用估算

| 资源 | 规格 | 月费用（约） |
|------|------|-------------|
| ECS | 2核4G | ¥100-150 |
| 系统盘 | 40GB SSD | ¥20 |
| 公网带宽 | 1Mbps | ¥20 |
| **总计** | | **¥140-190** |

> 新用户通常有优惠，实际费用可能更低

---

## 常见问题

### Q: 扫描时报错 "无法获取数据"？

A: 检查网络是否正常，同花顺接口是否可访问：
```bash
curl -I https://q.10jqka.com.cn/thshy/
```

### Q: MySQL 连接失败？

A: 检查环境变量和 MySQL 服务：
```bash
systemctl status mysql
mysql -u root -p -e "SHOW DATABASES;"
```

### Q: 内存不足？

A: 减少 Gunicorn worker 数量：
```bash
# 修改 /etc/supervisor/conf.d/stock-scanner.conf
# 将 -w 2 改为 -w 1
supervisorctl restart stock-scanner
```

### Q: 如何配置域名？

A: 
1. 购买域名并解析到服务器 IP
2. 修改 Nginx 配置中的 `server_name`
3. 可选：使用 Let's Encrypt 配置 HTTPS
