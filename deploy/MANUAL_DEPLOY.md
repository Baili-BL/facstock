# 布林带收缩策略 - 腾讯云部署指南

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    腾讯云轻量服务器                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │   Nginx     │───▶│  Gunicorn   │───▶│  MySQL 8.0  │ │
│  │   (80)      │    │   (5001)    │    │   (3306)    │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                 │                             │
│         ▼                 ▼                             │
│  ┌─────────────┐    ┌─────────────┐                    │
│  │  Systemd    │    │   Python    │                    │
│  │  进程管理    │    │   venv      │                    │
│  └─────────────┘    └─────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

---

## 一、首次部署（从零开始）

### 1. 购买腾讯云服务器

1. 访问 [腾讯云轻量应用服务器](https://cloud.tencent.com/product/lighthouse)
2. 选择配置：
   - **镜像**：Ubuntu 22.04 LTS
   - **配置**：2核4G 及以上（推荐）
   - **带宽**：5Mbps 及以上
3. 完成购买，记住服务器 **公网IP**

### 2. 连接服务器

```bash
ssh root@<服务器IP>
```

### 3. 安装系统依赖

```bash
# 更新系统
apt update && apt upgrade -y

# 安装基础工具
apt install -y git curl wget vim htop

# 安装 Python 3 和开发工具
apt install -y python3 python3-pip python3-venv build-essential libffi-dev libssl-dev

# 安装 Nginx
apt install -y nginx

# 验证安装
python3 --version  # 应该显示 3.10+
```

### 4. 安装 MySQL 8.0

```bash
# 安装 MySQL 8.0
apt install -y mysql-server mysql-client libmysqlclient-dev

# 启动并设置开机自启
systemctl enable mysql
systemctl start mysql

# 设置 root 密码（替换 YourPassword123 为你的密码）
mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'YourPassword123';"

# 创建数据库
mysql -u root -p'YourPassword123' -e "CREATE DATABASE stock_scanner CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 验证
mysql -u root -p'YourPassword123' -e "SHOW DATABASES;"
```

### 5. 克隆项目代码

```bash
# 进入部署目录
cd /opt

# 克隆代码
git clone https://github.com/Baili-BL/facSstock.git stock-scanner

# 进入项目目录
cd stock-scanner
```

**如果 git clone 失败**（网络问题）：
```bash
git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000
git clone https://github.com/Baili-BL/facSstock.git stock-scanner
```

### 6. 配置 Python 环境

```bash
cd /opt/stock-scanner

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装依赖（使用国内镜像加速）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 gunicorn
pip install gunicorn

# 验证安装
python -c "import flask; import akshare; import pymysql; print('依赖安装成功')"
```

### 7. 配置环境变量

```bash
# 创建环境变量文件
cat > /opt/stock-scanner/.env << 'EOF'
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=YourPassword123
MYSQL_DATABASE=stock_scanner
EOF

# 设置权限
chmod 600 /opt/stock-scanner/.env
```

### 8. 测试运行

```bash
# 激活虚拟环境
source /opt/stock-scanner/venv/bin/activate

# 设置环境变量
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=YourPassword123
export MYSQL_DATABASE=stock_scanner

# 测试运行
cd /opt/stock-scanner
python app.py

# 应该看到：* Running on http://0.0.0.0:5001
# 按 Ctrl+C 停止
```

### 9. 配置 Systemd 服务

```bash
# 创建服务文件
cat > /etc/systemd/system/stock-scanner.service << 'EOF'
[Unit]
Description=Stock Scanner - Bollinger Squeeze Strategy
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/stock-scanner
Environment=PATH=/opt/stock-scanner/venv/bin:/usr/bin
Environment=MYSQL_HOST=localhost
Environment=MYSQL_PORT=3306
Environment=MYSQL_USER=root
Environment=MYSQL_PASSWORD=YourPassword123
Environment=MYSQL_DATABASE=stock_scanner
ExecStart=/opt/stock-scanner/venv/bin/gunicorn -w 2 -b 127.0.0.1:5001 --timeout 300 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd
systemctl daemon-reload

# 启动服务
systemctl start stock-scanner

# 设置开机自启
systemctl enable stock-scanner

# 查看状态
systemctl status stock-scanner
```

### 10. 配置 Nginx 反向代理

```bash
# 创建 Nginx 配置
cat > /etc/nginx/sites-available/stock-scanner << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
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

# 测试并重载
nginx -t
systemctl reload nginx
```

### 11. 配置防火墙

在腾讯云控制台操作：
1. 进入轻量应用服务器控制台
2. 点击服务器 → 防火墙
3. 添加规则：

| 端口 | 协议 | 策略 | 说明 |
|------|------|------|------|
| 22 | TCP | 允许 | SSH |
| 80 | TCP | 允许 | HTTP |
| 443 | TCP | 允许 | HTTPS（可选） |

### 12. 访问应用

```
http://<服务器IP>
```

---

## 二、更新部署

### 方式1：Git Pull 更新（推荐）

```bash
# SSH 连接服务器
ssh root@<服务器IP>

# 进入项目目录并拉取代码
cd /opt/stock-scanner
git pull origin main

# 更新依赖（如有变化）
source venv/bin/activate
pip install -r requirements.txt

# 重启服务
systemctl restart stock-scanner

# 查看状态
systemctl status stock-scanner
```

### 方式2：Rsync 直接同步

```bash
# 本地执行（排除不需要同步的目录）
rsync -avz --progress \
  --exclude='__pycache__/' \
  --exclude='.git/' \
  --exclude='*.pyc' \
  --exclude='venv/' \
  --exclude='.env' \
  /Users/kevin/Desktop/facSstock/ \
  root@<服务器IP>:/opt/stock-scanner/

# 重启服务
ssh root@<服务器IP> "systemctl restart stock-scanner"
```

### 一键部署脚本

保存为 `deploy.sh`：

```bash
#!/bin/bash
SERVER_IP="<你的服务器IP>"

echo "📦 同步代码到服务器..."
rsync -avz --progress \
  --exclude='__pycache__/' \
  --exclude='.git/' \
  --exclude='*.pyc' \
  --exclude='venv/' \
  --exclude='.env' \
  /Users/kevin/Desktop/facSstock/ \
  root@${SERVER_IP}:/opt/stock-scanner/

echo "🔄 重启服务..."
ssh root@${SERVER_IP} "systemctl restart stock-scanner && systemctl status stock-scanner"

echo "✅ 部署完成！访问 http://${SERVER_IP}"
```

---

## 三、日常运维

### 查看服务状态

```bash
systemctl status stock-scanner
```

### 重启服务

```bash
systemctl restart stock-scanner
```

### 查看日志

```bash
# 实时日志
journalctl -u stock-scanner -f

# 最近100行
journalctl -u stock-scanner -n 100

# 错误日志
journalctl -u stock-scanner -p err
```

### 数据库操作

```bash
# 连接数据库
mysql -u root -p stock_scanner

# 备份数据库
mysqldump -u root -p stock_scanner > backup_$(date +%Y%m%d).sql

# 恢复数据库
mysql -u root -p stock_scanner < backup_20240101.sql
```

### 查看磁盘空间

```bash
df -h
```

### 查看内存使用

```bash
free -h
htop
```

---

## 四、常见问题

### 1. Git Clone/Pull 失败

```bash
# 禁用 HTTP/2
git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000
git pull origin main
```

### 2. MySQL 连接失败

```bash
# 检查 MySQL 状态
systemctl status mysql

# 检查连接
mysql -u root -p -e "SELECT 1;"

# 查看错误日志
tail -f /var/log/mysql/error.log
```

### 3. 服务启动失败

```bash
# 查看详细日志
journalctl -u stock-scanner -n 50

# 手动测试运行
cd /opt/stock-scanner
source venv/bin/activate
export MYSQL_HOST=localhost MYSQL_PORT=3306 MYSQL_USER=root MYSQL_PASSWORD=YourPassword123 MYSQL_DATABASE=stock_scanner
python app.py
```

### 4. 内存不足

```bash
# 添加 2G Swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## 五、快速参考

### 服务器信息

| 项目 | 路径/值 |
|------|---------|
| 项目目录 | `/opt/stock-scanner` |
| 虚拟环境 | `/opt/stock-scanner/venv` |
| 服务名称 | `stock-scanner` |
| 应用端口 | `5001` |
| 数据库 | `stock_scanner` |

### 常用命令

```bash
# 连接服务器
ssh root@<服务器IP>

# 进入项目
cd /opt/stock-scanner

# 激活虚拟环境
source venv/bin/activate

# 拉取代码
git pull origin main

# 重启服务
systemctl restart stock-scanner

# 查看状态
systemctl status stock-scanner

# 查看日志
journalctl -u stock-scanner -f
```
