#!/bin/bash
# ============================================
# 一键安装脚本（在腾讯云服务器上运行）
# 
# 使用方法:
# curl -sSL https://raw.githubusercontent.com/Baili-BL/facstock/main/deploy/quick_install.sh | bash
# 
# 或者:
# wget -qO- https://raw.githubusercontent.com/Baili-BL/facstock/main/deploy/quick_install.sh | bash
# ============================================

set -e

echo "🚀 开始一键安装布林带收缩策略系统..."

# 下载部署脚本并执行
cd /tmp
git clone https://github.com/Baili-BL/facstock.git facstock_temp
cd facstock_temp/deploy
chmod +x deploy.sh
sudo ./deploy.sh

# 清理临时文件
cd /
rm -rf /tmp/facstock_temp

echo "✅ 安装完成！"
