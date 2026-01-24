# 布林带收缩策略 - 腾讯云部署指南

## 目录
1. [首次部署（从零开始）](#一首次部署从零开始)
2. [更新部署（代码更新后）](#二更新部署代码更新后)
3. [常见问题](#三常见问题)

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
# 方式1：使用密码登录
ssh root@你的服务器IP

# 方式2：使用密钥登录（推荐）
ssh -i ~/.ssh/your_key.pem root@你的服务器IP
```

### 3. 安装基础环境

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Python 3.11+ 和相关工具
apt install -y python3 python3-pip python3-venv git

# 验证安装
python3 --version  # 应该显示 3.10+
pip3 --version
```

### 4. 克隆项目代码

```bash
# 进入部署目录
cd /opt

# 克隆代码（替换为你的仓库地址）
git clone https://github.com/你的用户名/facSstock.git facstock

# 进入项目目录
cd facstock
```

**如果 git clone 失败**（网络问题），使用以下方法：

```bash
# 配置 git 使用 HTTP/1.1
git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000

# 重试
git clone https://github.com/你的用户名/facSstock.git facstock
```

### 5. 创建虚拟环境

```bash
# 在项目目录创建虚拟环境
cd /opt/facstock
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 确认激活成功（命令行前面会显示 (venv)）
which python  # 应该显示 /opt/facstock/venv/bin/python
```

### 6. 安装依赖

```bash
# 确保在虚拟环境中
source /opt/facstock/venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 验证安装
python -c "import flask; import akshare; print('依赖安装成功')"
```

### 7. 创建数据目录

```bash
# 创建数据目录（存储 SQLite 数据库）
mkdir -p /opt/facstock/data

# 设置权限
chmod 755 /opt/facstock/data
```

### 8. 测试运行

```bash
# 激活虚拟环境
source /opt/facstock/venv/bin/activate

# 测试运行（前台模式）
cd /opt/facstock
python app.py

# 应该看到：
# * Running on http://0.0.0.0:5001
# 按 Ctrl+C 停止
```

### 9. 配置 Systemd 服务（开机自启）

```bash
# 创建服务文件
cat > /etc/systemd/system/facstock.service << 'EOF'
[Unit]
Description=FacStock - Bollinger Squeeze Strategy
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/facstock
Environment=PATH=/opt/facstock/venv/bin:/usr/bin
ExecStart=/opt/facstock/venv/bin/gunicorn -w 2 -b 0.0.0.0:5001 --timeout 300 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd
systemctl daemon-reload

# 启动服务
systemctl start facstock

# 设置开机自启
systemctl enable facstock

# 查看状态
systemctl status facstock
```

### 10. 配置防火墙

```bash
# 腾讯云控制台操作：
# 1. 进入轻量应用服务器控制台
# 2. 点击服务器 -> 防火墙
# 3. 添加规则：
#    - 端口：5001
#    - 协议：TCP
#    - 策略：允许
#    - 来源：0.0.0.0/0

# 或者使用命令行（如果使用 ufw）
ufw allow 5001/tcp
```

### 11. 访问应用

打开浏览器访问：
```
http://你的服务器IP:5001
```

---

## 二、更新部署（代码更新后）

### 方式1：Git Pull 更新（推荐）

**本地操作：提交并推送代码**

```bash
# 在本地项目目录
cd /Users/kevin/Desktop/facSstock

# 添加所有更改
git add .

# 提交
git commit -m "更新说明"

# 推送到 GitHub
git push origin main
```

**服务器操作：拉取并重启**

```bash
# SSH 连接服务器
ssh root@你的服务器IP

# 进入项目目录
cd /opt/facstock

# 拉取最新代码
git pull origin main

# 如果 git pull 报错，尝试：
git config --global http.version HTTP/1.1
git pull origin main

# 重启服务
systemctl restart facstock

# 查看状态
systemctl status facstock
```

### 方式2：Rsync 直接同步（网络不稳定时）

**在本地执行一条命令即可：**

```bash
# 同步代码到服务器（排除数据目录和缓存）
rsync -avz --progress \
  --exclude='data/' \
  --exclude='__pycache__/' \
  --exclude='.git/' \
  --exclude='*.pyc' \
  --exclude='venv/' \
  /Users/kevin/Desktop/facSstock/ \
  root@你的服务器IP:/opt/facstock/

# 然后 SSH 到服务器重启
ssh root@你的服务器IP "systemctl restart facstock"
```

**一键更新脚本（保存为 deploy.sh）：**

```bash
#!/bin/bash
SERVER_IP="你的服务器IP"

echo "📦 同步代码到服务器..."
rsync -avz --progress \
  --exclude='data/' \
  --exclude='__pycache__/' \
  --exclude='.git/' \
  --exclude='*.pyc' \
  --exclude='venv/' \
  /Users/kevin/Desktop/facSstock/ \
  root@${SERVER_IP}:/opt/facstock/

echo "🔄 重启服务..."
ssh root@${SERVER_IP} "systemctl restart facstock && systemctl status facstock"

echo "✅ 部署完成！访问 http://${SERVER_IP}:5001"
```

使用方法：
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## 三、常见问题

### 1. Git Clone/Pull 失败

**错误信息：**
```
error: RPC failed; curl 16 Error in the HTTP2 framing layer
```

**解决方案：**
```bash
# 禁用 HTTP/2
git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000

# 重试
git pull origin main
```

### 2. 依赖安装失败

**错误信息：** pip 安装超时

**解决方案：使用国内镜像**
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 服务启动失败

**查看日志：**
```bash
# 查看服务日志
journalctl -u facstock -f

# 或查看最近100行
journalctl -u facstock -n 100
```

**常见原因：**
- 端口被占用：`lsof -i:5001`
- 依赖未安装：重新执行 `pip install -r requirements.txt`
- 权限问题：`chown -R root:root /opt/facstock`

### 4. 数据库被覆盖

**问题：** 每次部署后历史数据丢失

**解决方案：** 确保同步时排除 data 目录
```bash
rsync --exclude='data/' ...
```

### 5. 服务器内存不足

**查看内存：**
```bash
free -h
```

**解决方案：** 添加 Swap
```bash
# 创建 2G Swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# 永久生效
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### 6. 查看应用日志

```bash
# 实时查看日志
journalctl -u facstock -f

# 查看最近的错误
journalctl -u facstock -p err -n 50
```

### 7. 手动重启服务

```bash
# 重启
systemctl restart facstock

# 停止
systemctl stop facstock

# 启动
systemctl start facstock

# 查看状态
systemctl status facstock
```

---

## 四、快速参考

### 服务器信息
- **项目目录**：`/opt/facstock`
- **虚拟环境**：`/opt/facstock/venv`
- **数据目录**：`/opt/facstock/data`
- **服务名称**：`facstock`
- **端口**：`5001`

### 常用命令速查

```bash
# 连接服务器
ssh root@服务器IP

# 进入项目
cd /opt/facstock

# 激活虚拟环境
source venv/bin/activate

# 拉取代码
git pull origin main

# 重启服务
systemctl restart facstock

# 查看状态
systemctl status facstock

# 查看日志
journalctl -u facstock -f
```

### 本地一键部署

```bash
# 使用 rsync 同步并重启
rsync -avz --exclude='data/' --exclude='__pycache__/' --exclude='.git/' --exclude='venv/' \
  /Users/kevin/Desktop/facSstock/ root@服务器IP:/opt/facstock/ && \
  ssh root@服务器IP "systemctl restart facstock"
```
