# 腾讯云手动部署指南

## 服务器环境
- Ubuntu 18.04/20.04/22.04
- 需要 root 权限

---

## 第一步：安装 Miniconda (Python 3.10)

```bash
# 1. 下载 Miniconda（清华镜像）
cd /tmp
wget https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-py310_23.1.0-1-Linux-x86_64.sh

# 2. 安装（-b 静默安装，-p 指定目录）
bash Miniconda3-py310_23.1.0-1-Linux-x86_64.sh -b -p $HOME/miniconda

# 3. 添加到环境变量
export PATH="$HOME/miniconda/bin:$PATH"

# 4. 初始化 conda（让下次登录自动生效）
conda init bash

# 5. 刷新环境（或重新登录）
source ~/.bashrc

# 6. 验证安装
conda --version
python --version  # 应该显示 Python 3.10.x
```

---

## 第二步：配置镜像源（加速下载）

```bash
# 配置 conda 清华镜像
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --set show_channel_urls yes

# 配置 pip 清华镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/
```

---

## 第三步：创建项目环境

```bash
# 1. 创建独立的 conda 环境
conda create -y -n facstock_env python=3.10

# 2. 激活环境
conda activate facstock_env

# 3. 验证
which python  # 应该显示 ~/miniconda/envs/facstock_env/bin/python
```

---

## 第四步：上传代码

### 方式 A：从本地上传（推荐，避免 GitHub 网络问题）

在你的 **本地电脑（Mac）** 执行：

```bash
# 先在服务器创建目录
ssh root@你的服务器IP "mkdir -p /opt/facstock"

# 上传代码
scp -r /Users/kevin/Desktop/facSstock/* root@你的服务器IP:/opt/facstock/
```

### 方式 B：从 GitHub 克隆

```bash
# 在服务器执行
mkdir -p /opt/facstock
cd /opt

# 使用镜像加速
git clone https://ghproxy.com/https://github.com/Baili-BL/facstock.git

# 如果镜像也不行，直接克隆（可能慢）
git clone https://github.com/Baili-BL/facstock.git
```

---

## 第五步：安装 Python 依赖

```bash
# 1. 进入项目目录
cd /opt/facstock

# 2. 确保在 facstock_env 环境中
conda activate facstock_env

# 3. 升级 pip
pip install --upgrade pip

# 4. 安装依赖
pip install -r requirements.txt

# 5. 安装 gunicorn（生产服务器）
pip install gunicorn
```

---

## 第六步：测试运行

```bash
# 在项目目录下测试
cd /opt/facstock
conda activate facstock_env

# 直接运行测试
python app.py

# 或用 gunicorn 测试
gunicorn -w 2 -b 0.0.0.0:5001 app:app
```

浏览器访问：`http://你的服务器IP:5001`

测试成功后 `Ctrl+C` 停止。

---

## 第七步：安装 Supervisor（进程管理）

```bash
# 1. 安装 supervisor
apt update
apt install -y supervisor

# 2. 创建日志目录
mkdir -p /opt/facstock/logs

# 3. 创建配置文件
cat > /etc/supervisor/conf.d/facstock.conf <<'EOF'
[program:facstock]
command=/root/miniconda/envs/facstock_env/bin/gunicorn -w 2 -b 0.0.0.0:5001 app:app
directory=/opt/facstock
user=root
autostart=true
autorestart=true
startsecs=5
stdout_logfile=/opt/facstock/logs/supervisor_out.log
stderr_logfile=/opt/facstock/logs/supervisor_err.log
environment=PYTHONUNBUFFERED=1
EOF

# 4. 重新加载并启动
supervisorctl reread
supervisorctl update
supervisorctl start facstock

# 5. 查看状态
supervisorctl status
```

---

## 第八步：安装 Nginx（反向代理）

```bash
# 1. 安装 nginx
apt install -y nginx

# 2. 创建配置文件
cat > /etc/nginx/sites-available/facstock <<'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
}
EOF

# 3. 启用配置
ln -sf /etc/nginx/sites-available/facstock /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 4. 测试并重载
nginx -t
systemctl reload nginx
systemctl enable nginx
```

---

## 第九步：配置防火墙

```bash
# 开放端口
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS（可选）
ufw allow 5001/tcp  # 直接访问（可选）

# 启用防火墙
ufw --force enable

# 查看状态
ufw status
```

⚠️ **重要**：还需要在腾讯云控制台的**安全组**中开放 80 和 5001 端口！

---

## 第十步：验证部署

```bash
# 查看服务状态
supervisorctl status facstock

# 查看日志
tail -f /opt/facstock/logs/supervisor_out.log
```

访问地址：
- `http://你的服务器IP` （通过 Nginx）
- `http://你的服务器IP:5001` （直接访问）

---

## 常用管理命令

```bash
# 启动/停止/重启应用
supervisorctl start facstock
supervisorctl stop facstock
supervisorctl restart facstock

# 查看日志
tail -f /opt/facstock/logs/supervisor_out.log
tail -f /opt/facstock/logs/supervisor_err.log

# 更新代码后重启
cd /opt/facstock
git pull  # 或重新上传
supervisorctl restart facstock

# 激活 Python 环境（调试用）
conda activate facstock_env
```

---

## 部署第二个项目（Ticai）

重复上述步骤，修改以下参数：

| 参数 | facstock | Ticai |
|------|----------|-------|
| 项目目录 | `/opt/facstock` | `/opt/Ticai` |
| conda 环境 | `facstock_env` | `ticai_env` |
| 端口 | `5001` | `5002` |
| supervisor 配置 | `facstock.conf` | `ticai.conf` |
| 入口文件 | `app.py` | `main.py` |

Nginx 配置（多项目）：

```nginx
server {
    listen 80;
    server_name _;

    location /facstock/ {
        proxy_pass http://127.0.0.1:5001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ticai/ {
        proxy_pass http://127.0.0.1:5002/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        return 302 /facstock/;
    }
}
```
