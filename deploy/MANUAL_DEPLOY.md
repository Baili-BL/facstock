# 腾讯云手动部署指南

> 服务器：Ubuntu 18.04/20.04/22.04  
> 项目：facstock (端口5001) + Ticai (端口5002)

---

## 一、安装 Miniconda

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

---

## 二、配置镜像源

```bash
# conda 镜像
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --set show_channel_urls yes

# pip 镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/
```

---

## 三、部署 facstock

### 3.1 创建环境

```bash
conda create -y -n facstock_env python=3.10
conda activate facstock_env
```

### 3.2 上传代码

**在本地 Mac 执行：**

```bash
ssh root@111.229.238.115 "mkdir -p /opt/facstock"
scp -r /Users/kevin/Desktop/facSstock/* root@111.229.238.115:/opt/facstock/
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
# 安装
apt update && apt install -y supervisor

# 创建日志目录
mkdir -p /opt/facstock/logs

# 配置文件
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

# 启动
systemctl start supervisor
systemctl enable supervisor
supervisorctl reread
supervisorctl update
supervisorctl start facstock
```

---

## 四、部署 Ticai

### 4.1 创建环境

```bash
conda create -y -n ticai_env python=3.10
conda activate ticai_env
```

### 4.2 上传代码

**在本地 Mac 执行：**

```bash
ssh root@111.229.238.115 "mkdir -p /opt/Ticai"
scp -r /Users/kevin/Desktop/Ticai/* root@111.229.238.115:/opt/Ticai/
```

### 4.3 安装依赖

```bash
cd /opt/Ticai
conda activate ticai_env
pip install -r requirements.txt
pip install gunicorn
```

### 4.4 修改端口（重要！）

```bash
# 把 port=80 改成 port=5002
sed -i 's/port=80/port=5002/g' /opt/Ticai/main.py

# 验证
grep "port=" /opt/Ticai/main.py
```

### 4.5 配置 Supervisor

```bash
# 创建日志目录
mkdir -p /opt/Ticai/logs

# 配置文件（注意 create_app() 工厂模式）
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

# 启动
supervisorctl reread
supervisorctl update
supervisorctl start ticai
```

---

## 五、配置 Nginx

```bash
apt install -y nginx

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

ln -sf /etc/nginx/sites-available/facstock /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
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

### 6.2 腾讯云安全组/防火墙（重要！）

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入 **轻量应用服务器** 或 **云服务器**
3. 点击 **防火墙** 或 **安全组**
4. 添加入站规则：

| 端口 | 协议 | 策略 |
|------|------|------|
| 22 | TCP | 允许 |
| 80 | TCP | 允许 |
| 5001 | TCP | 允许 |
| 5002 | TCP | 允许 |

---

## 七、访问地址

| 应用 | 地址 |
|------|------|
| facstock | http://111.229.238.115 或 http://111.229.238.115:5001 |
| Ticai | http://111.229.238.115:5002 |

---

## 八、常用命令

```bash
# 查看服务状态
supervisorctl status

# 重启服务
supervisorctl restart facstock
supervisorctl restart ticai

# 停止服务
supervisorctl stop facstock
supervisorctl stop ticai

# 查看日志
tail -f /opt/facstock/logs/supervisor_out.log
tail -f /opt/facstock/logs/supervisor_err.log
tail -f /opt/Ticai/logs/supervisor_out.log
tail -f /opt/Ticai/logs/supervisor_err.log

# 激活环境（调试用）
conda activate facstock_env
conda activate ticai_env

# 本地测试
curl http://127.0.0.1:5001
curl http://127.0.0.1:5002
```

---

## 九、更新代码

**在本地 Mac 执行：**

```bash
# 更新 facstock
scp -r /Users/kevin/Desktop/facSstock/* root@111.229.238.115:/opt/facstock/

# 更新 Ticai
scp -r /Users/kevin/Desktop/Ticai/* root@111.229.238.115:/opt/Ticai/
```

**在服务器执行：**

```bash
supervisorctl restart facstock
supervisorctl restart ticai
```

---

## 十、常见问题

### Q1: SSH 报错 "REMOTE HOST IDENTIFICATION HAS CHANGED"

```bash
# 在 Mac 执行
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
