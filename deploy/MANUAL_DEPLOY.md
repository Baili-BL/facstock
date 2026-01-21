# 腾讯云服务器部署指南

> **服务器**：Ubuntu 18.04/20.04/22.04  
> **项目**：facstock (端口5001) + Ticai (端口5002)  
> **服务器IP**：111.229.238.115

---

# 第一部分：首次部署

> 首次部署需要完成环境安装、代码部署、服务配置等全部步骤

---

## 一、环境准备

### 1.1 安装 Miniconda

```bash
# 下载（清华镜像）
cd /tmp
wget https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-py310_23.1.0-1-Linux-x86_64.sh

# 安装
bash Miniconda3-py310_23.1.0-1-Linux-x86_64.sh -b -p $HOME/miniconda

# 环境变量
export PATH="$HOME/miniconda/bin:$PATH"
conda init bash
source ~/.bashrc

# 验证
conda --version
python --version
```

### 1.2 配置镜像源

```bash
# conda 镜像（清华源）
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --set show_channel_urls yes

# pip 镜像（清华源）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/
```

### 1.3 安装基础软件

```bash
apt update
apt install -y supervisor nginx git
```

---

## 二、获取代码

> 选择 GitHub 或 Gitee 其中一个源即可

### 方式 A：从 GitHub 克隆

```bash
# facstock
git clone https://github.com/Baili-BL/facSstock.git ~/facSstock

# Ticai
git clone https://github.com/Baili-BL/Ticai.git ~/Ticai
```

### 方式 B：从 Gitee 克隆（国内更快）

```bash
# facstock
git clone https://gitee.com/Baili-BL/facSstock.git ~/facSstock

# Ticai
git clone https://gitee.com/Baili-BL/Ticai.git ~/Ticai
```

### 方式 C：本地上传（无需 Git）

**在本地 Mac 终端执行：**

```bash
# 创建远程目录
ssh root@111.229.238.115 "mkdir -p /opt/facstock /opt/Ticai"

# 上传 facstock
scp -r /Users/kevin/Desktop/facSstock/* root@111.229.238.115:/opt/facstock/

# 上传 Ticai
scp -r /Users/kevin/Desktop/Ticai/* root@111.229.238.115:/opt/Ticai/
```

> 如果使用方式 C，可跳过后续的"复制代码到运行目录"步骤

---

## 三、部署 facstock

### 3.1 创建 Python 环境

```bash
conda create -y -n facstock_env python=3.10
conda activate facstock_env
```

### 3.2 复制代码到运行目录

```bash
mkdir -p /opt/facstock
cp -r ~/facSstock/* /opt/facstock/
```

### 3.3 安装依赖

```bash
cd /opt/facstock
conda activate facstock_env
pip install -r requirements.txt
pip install gunicorn
```

### 3.4 配置 Supervisor

```bash
# 创建日志目录
mkdir -p /opt/facstock/logs

# 创建配置文件
cat > /etc/supervisor/conf.d/facstock.conf <<'EOF'
[program:facstock]
command=/root/miniconda/envs/facstock_env/bin/gunicorn -w 2 -b 0.0.0.0:5001 app:app
directory=/opt/facstock
user=root
autostart=true
autorestart=true
stdout_logfile=/opt/facstock/logs/supervisor_out.log
stderr_logfile=/opt/facstock/logs/supervisor_err.log
EOF

# 启动服务
systemctl start supervisor
systemctl enable supervisor
supervisorctl reread
supervisorctl update
supervisorctl start facstock
```

---

## 四、部署 Ticai

### 4.1 创建 Python 环境

```bash
conda create -y -n ticai_env python=3.10
conda activate ticai_env
```

### 4.2 复制代码到运行目录

```bash
mkdir -p /opt/Ticai
cp -r ~/Ticai/* /opt/Ticai/
```

### 4.3 安装依赖

```bash
cd /opt/Ticai
conda activate ticai_env
pip install -r requirements.txt
pip install gunicorn
```

### 4.4 修改端口配置

```bash
# 把 port=80 改成 port=5002
sed -i 's/port=80/port=5002/g' /opt/Ticai/main.py

# 验证修改
grep "port=" /opt/Ticai/main.py
```

### 4.5 配置 Supervisor

```bash
# 创建日志目录
mkdir -p /opt/Ticai/logs

# 创建配置文件（注意：使用 create_app() 工厂模式）
cat > /etc/supervisor/conf.d/ticai.conf <<'EOF'
[program:ticai]
command=/root/miniconda/envs/ticai_env/bin/gunicorn -w 2 -b 0.0.0.0:5002 "main:create_app()"
directory=/opt/Ticai
user=root
autostart=true
autorestart=true
stdout_logfile=/opt/Ticai/logs/supervisor_out.log
stderr_logfile=/opt/Ticai/logs/supervisor_err.log
EOF

# 启动服务
supervisorctl reread
supervisorctl update
supervisorctl start ticai
```

---

## 五、配置 Nginx

```bash
# 创建配置文件
cat > /etc/nginx/sites-available/facstock <<'EOF'
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
EOF

# 启用配置
ln -sf /etc/nginx/sites-available/facstock /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 测试并重载
nginx -t && systemctl reload nginx
systemctl enable nginx
```

---

## 六、配置防火墙

### 6.1 服务器防火墙 (ufw)

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 5001/tcp
ufw allow 5002/tcp
ufw --force enable
ufw status
```

### 6.2 腾讯云安全组（必须配置！）

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入 **轻量应用服务器** 或 **云服务器**
3. 点击 **防火墙** 或 **安全组**
4. 添加入站规则：

| 端口 | 协议 | 策略 | 说明 |
|------|------|------|------|
| 22 | TCP | 允许 | SSH |
| 80 | TCP | 允许 | HTTP |
| 5001 | TCP | 允许 | facstock |
| 5002 | TCP | 允许 | Ticai |

---

## 七、验证部署

```bash
# 查看服务状态
supervisorctl status

# 本地测试
curl http://127.0.0.1:5001
curl http://127.0.0.1:5002
```

**访问地址：**

| 应用 | 地址 |
|------|------|
| facstock | http://111.229.238.115 或 http://111.229.238.115:5001 |
| Ticai | http://111.229.238.115:5002 |

---

# 第二部分：更新部署

> 代码更新只需要 **上传代码 + 重启服务**，无需重复环境配置

---

## 方式一：本地上传更新（推荐）

### Step 1：上传代码（本地 Mac 执行）

```bash
# 更新 facstock
scp -r /Users/kevin/Desktop/facSstock/* root@111.229.238.115:/opt/facstock/

# 更新 Ticai
scp -r /Users/kevin/Desktop/Ticai/* root@111.229.238.115:/opt/Ticai/
```

### Step 2：重启服务（服务器执行）

```bash
ssh root@111.229.238.115

# 重启服务
supervisorctl restart facstock
supervisorctl restart ticai

# 确认状态
supervisorctl status
```

---

## 方式二：Git 拉取更新

> 从 GitHub 或 Gitee 拉取最新代码

### 从 GitHub 更新

```bash
# === facstock ===
cd ~/facSstock
git pull origin main
cp -r ~/facSstock/* /opt/facstock/
supervisorctl restart facstock

# === Ticai ===
cd ~/Ticai
git pull origin main
cp -r ~/Ticai/* /opt/Ticai/
supervisorctl restart ticai
```

### 从 Gitee 更新

```bash
# === facstock ===
cd ~/facSstock
git pull gitee main
cp -r ~/facSstock/* /opt/facstock/
supervisorctl restart facstock

# === Ticai ===
cd ~/Ticai
git pull gitee main
cp -r ~/Ticai/* /opt/Ticai/
supervisorctl restart ticai
```

---

## 方式三：一键更新脚本

### 创建更新脚本（首次执行）

```bash
cat > /root/update_all.sh << 'EOF'
#!/bin/bash
echo "=========================================="
echo "       一键更新脚本"
echo "=========================================="

echo ""
echo "=== [1/4] 更新 facstock 代码 ==="
cd ~/facSstock && git pull origin main

echo ""
echo "=== [2/4] 部署 facstock ==="
cp -r ~/facSstock/* /opt/facstock/
supervisorctl restart facstock

echo ""
echo "=== [3/4] 更新 Ticai 代码 ==="
cd ~/Ticai && git pull origin main

echo ""
echo "=== [4/4] 部署 Ticai ==="
cp -r ~/Ticai/* /opt/Ticai/
supervisorctl restart ticai

echo ""
echo "=========================================="
echo "       更新完成！服务状态："
echo "=========================================="
supervisorctl status
EOF

chmod +x /root/update_all.sh
```

### 执行更新

```bash
/root/update_all.sh
```

---

# 第三部分：运维管理

---

## 常用命令速查

| 操作 | 命令 |
|------|------|
| 查看状态 | `supervisorctl status` |
| 重启 facstock | `supervisorctl restart facstock` |
| 重启 Ticai | `supervisorctl restart ticai` |
| 重启全部 | `supervisorctl restart all` |
| 停止服务 | `supervisorctl stop facstock` |
| 启动服务 | `supervisorctl start facstock` |

---

## 日志查看

```bash
# facstock 日志
tail -50 /opt/facstock/logs/supervisor_out.log   # 输出日志
tail -50 /opt/facstock/logs/supervisor_err.log   # 错误日志

# Ticai 日志
tail -50 /opt/Ticai/logs/supervisor_out.log
tail -50 /opt/Ticai/logs/supervisor_err.log

# 实时查看（Ctrl+C 退出）
tail -f /opt/facstock/logs/supervisor_out.log
tail -f /opt/Ticai/logs/supervisor_err.log
```

---

## 常见问题

### Q1: SSH 报错 "REMOTE HOST IDENTIFICATION HAS CHANGED"

```bash
# 在本地 Mac 执行
ssh-keygen -R 111.229.238.115
```

### Q2: Port 80 is in use

不要直接运行 `python main.py`，用 supervisor 管理：

```bash
supervisorctl restart ticai
```

### Q3: supervisor 报错 "no such file"

```bash
mkdir -p /opt/facstock/logs
mkdir -p /opt/Ticai/logs
supervisorctl reread
supervisorctl update
```

### Q4: 外网无法访问

1. 检查服务是否运行：`supervisorctl status`
2. 本地测试：`curl http://127.0.0.1:5001`
3. 检查 ufw：`ufw status`
4. **检查腾讯云安全组/防火墙是否开放端口**

### Q5: gunicorn 报错 "Failed to find attribute 'app'"

Ticai 使用工厂模式，gunicorn 命令要用：

```bash
gunicorn -w 2 -b 0.0.0.0:5002 "main:create_app()"
```

### Q6: Git pull 后代码没更新

Git 仓库在 `~/项目名`，但服务运行在 `/opt/项目名`，需要复制：

```bash
# facstock
cp -r ~/facSstock/* /opt/facstock/
supervisorctl restart facstock

# Ticai
cp -r ~/Ticai/* /opt/Ticai/
supervisorctl restart ticai
```

### Q7: RemoteDisconnected 网络错误

外部 API 连接问题，尝试重启：

```bash
supervisorctl restart ticai
```

如果持续报错，检查是哪个 API：

```bash
grep -B 5 "RemoteDisconnected" /opt/Ticai/logs/supervisor_err.log
```

### Q8: 如何切换 Git 源（GitHub/Gitee）

```bash
cd ~/facSstock

# 查看当前远程仓库
git remote -v

# 添加 Gitee 源
git remote add gitee https://gitee.com/Baili-BL/facSstock.git

# 从 Gitee 拉取
git pull gitee main

# 从 GitHub 拉取
git pull origin main
```

---

## 快速参考卡片

### 目录结构

| 位置 | 说明 |
|------|------|
| `~/facSstock` | Git 仓库目录 |
| `/opt/facstock` | 服务运行目录 |
| `/opt/facstock/logs` | 日志目录 |
| `/etc/supervisor/conf.d/` | Supervisor 配置 |

### 访问地址

| 应用 | 地址 |
|------|------|
| facstock | http://111.229.238.115 (或 :5001) |
| Ticai | http://111.229.238.115:5002 |

### 更新流程

```
本地修改 → 上传/Git推送 → 服务器拉取 → 复制到/opt → 重启服务
```

### 一句话更新

```bash
# 方式一：本地上传（Mac执行）
scp -r /Users/kevin/Desktop/facSstock/* root@111.229.238.115:/opt/facstock/ && ssh root@111.229.238.115 "supervisorctl restart facstock"

# 方式二：服务器Git拉取
cd ~/facSstock && git pull && cp -r ~/facSstock/* /opt/facstock/ && supervisorctl restart facstock
```
