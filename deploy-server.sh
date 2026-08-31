#!/bin/bash
#=============================================================
# VoiceHub 一键部署脚本（华为云 Ubuntu 服务器）
# 用法：bash deploy-server.sh
# 前提：此脚本与 backend/ frontend/ 在同一目录下运行
#=============================================================
set -e

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "部署目录: $DEPLOY_DIR"

# MySQL root 密码（与 .env 中一致，含特殊字符已 URL 编码到 .env）
# 原始密码：<MySQL-root密码，见服务器backend/.env>
MYSQL_ROOT_PASS="<MySQL-root密码，见服务器backend/.env>"

# ===== 1. 检查并安装 MySQL =====
echo ""
echo "===== [1/7] 检查 MySQL ====="
if command -v mysql &>/dev/null; then
    echo "MySQL 已安装: $(mysql --version)"
    systemctl start mysql 2>/dev/null || true
else
    echo "MySQL 未安装，开始安装（Ubuntu apt）..."
    apt update -qq
    DEBIAN_FRONTEND=noninteractive apt install -y mysql-server
    systemctl start mysql
    systemctl enable mysql
    echo "MySQL 安装完成"
fi

# 设置 root 密码（Ubuntu 24.04 默认无密码，通过 auth_socket 登录）
# 先尝试无密码登录设置密码，如果已有密码则跳过
echo "配置 MySQL root 密码..."
mysql -u root <<SQLEOF 2>/dev/null && echo "root 密码已设置" || echo "root 密码可能已存在（跳过）"
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '${MYSQL_ROOT_PASS}';
FLUSH PRIVILEGES;
SQLEOF

# 验证密码可用
if mysql -u root -p"${MYSQL_ROOT_PASS}" -e "SELECT 1;" &>/dev/null; then
    echo "✅ MySQL root 密码验证通过"
else
    echo "⚠️  MySQL root 密码验证失败，尝试用 socket 方式设置..."
    mysql -u root <<SQLEOF2 2>/dev/null
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '${MYSQL_ROOT_PASS}';
FLUSH PRIVILEGES;
SQLEOF2
    if mysql -u root -p"${MYSQL_ROOT_PASS}" -e "SELECT 1;" &>/dev/null; then
        echo "✅ MySQL root 密码设置成功（第二次尝试）"
    else
        echo "❌ MySQL root 密码设置失败，请手动设置后重新运行"
        exit 1
    fi
fi

# ===== 2. 检查并安装 Redis =====
echo ""
echo "===== [2/7] 检查 Redis ====="
if command -v redis-server &>/dev/null; then
    echo "Redis 已安装: $(redis-server --version)"
    systemctl start redis-server 2>/dev/null || true
else
    echo "Redis 未安装，开始安装..."
    apt install -y redis-server
    systemctl start redis-server
    systemctl enable redis-server
    echo "Redis 安装完成"
fi

# ===== 3. 创建数据库 =====
echo ""
echo "===== [3/7] 创建数据库 ====="
mysql -u root -p"${MYSQL_ROOT_PASS}" -e "CREATE DATABASE IF NOT EXISTS voicehub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" && \
    echo "✅ 数据库 voicehub 已创建/已存在" || \
    { echo "❌ 数据库创建失败"; exit 1; }

# ===== 4. 安装 Python 依赖（Miniconda）=====
echo ""
echo "===== [4/7] 安装 Python 依赖 ====="
CONDA_HOME="/root/miniconda3"
CONDA_ENV="voicehub"
CONDA_BIN="$CONDA_HOME/bin/conda"
CONDA_PYTHON="$CONDA_HOME/envs/$CONDA_ENV/bin/python"
CONDA_PIP="$CONDA_HOME/envs/$CONDA_ENV/bin/pip"

# 检查 miniconda 是否已安装
if [ ! -f "$CONDA_BIN" ]; then
    echo "Miniconda 未安装，开始安装..."
    cd /tmp
    wget -q https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-latest-Linux-x86_64.sh
    bash Miniconda3-latest-Linux-x86_64.sh -b -p "$CONDA_HOME"
    "$CONDA_BIN" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main 2>/dev/null || true
    "$CONDA_BIN" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r 2>/dev/null || true
    "$CONDA_BIN" config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
    "$CONDA_BIN" config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free
    "$CONDA_BIN" config --set show_channel_urls yes
    echo "Miniconda 安装完成"
fi

# 配置 pip 清华源（如果尚未配置）
if [ ! -f /root/.config/pip/pip.conf ]; then
    mkdir -p /root/.config/pip
    cat > /root/.config/pip/pip.conf <<PIPEOF
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
timeout = 120
PIPEOF
    echo "pip 清华源已配置"
fi

# 创建 conda 环境（如果不存在）
if ! "$CONDA_BIN" env list | grep -q "^$CONDA_ENV "; then
    echo "创建 conda 环境: $CONDA_ENV (Python 3.11)"
    "$CONDA_BIN" create -y -n "$CONDA_ENV" python=3.11
fi

echo "conda 环境: $("$CONDA_BIN" env list | grep voicehub)"
cd "$DEPLOY_DIR/backend"
"$CONDA_PIP" install --upgrade pip -q
"$CONDA_PIP" install -r requirements.txt -q
"$CONDA_PIP" install gunicorn -q
echo "✅ Python 依赖安装完成（conda: $CONDA_ENV）"

# ===== 5. 构建前端 =====
echo ""
echo "===== [5/7] 构建前端 ====="
# 确保 node/npm 可用（conda 环境已安装则做符号链接）
if ! command -v node &>/dev/null; then
    if [ -f "/root/miniconda3/envs/voicehub/bin/node" ]; then
        ln -sf /root/miniconda3/envs/voicehub/bin/node /usr/local/bin/node
        ln -sf /root/miniconda3/envs/voicehub/bin/npm /usr/local/bin/npm
        ln -sf /root/miniconda3/envs/voicehub/bin/npx /usr/local/bin/npx
    else
        "$CONDA_BIN" install -y -n voicehub -c conda-forge nodejs=20
        ln -sf /root/miniconda3/envs/voicehub/bin/node /usr/local/bin/node
        ln -sf /root/miniconda3/envs/voicehub/bin/npm /usr/local/bin/npm
        ln -sf /root/miniconda3/envs/voicehub/bin/npx /usr/local/bin/npx
    fi
fi
# 配置 npm 清华源
npm config set registry https://registry.npmmirror.com 2>/dev/null
echo "Node: $(node --version) | npm: $(npm --version)"
cd "$DEPLOY_DIR/frontend"
npm install --silent 2>/dev/null
npm run build
echo "✅ 前端构建完成: $(ls dist/ | tr '\n' ' ')"

# ===== 6. 配置 systemd 服务 =====
echo ""
echo "===== [6/7] 配置 systemd 服务 ====="
# 使用 conda 环境中的 gunicorn
GUNICORN_PATH="/root/miniconda3/envs/voicehub/bin/gunicorn"
PYTHON_PATH="/root/miniconda3/envs/voicehub/bin"

# 重写 voicehub.service
cat > "$DEPLOY_DIR/voicehub.service" <<SVCEOF
[Unit]
Description=VoiceHub FastAPI Application (Gunicorn + Uvicorn)
After=network.target mysql.service redis-server.service

[Service]
Type=notify
User=root
WorkingDirectory=$DEPLOY_DIR/backend
Environment="PATH=$PYTHON_PATH:/usr/local/bin:/usr/bin"
ExecStart=$GUNICORN_PATH app.main:app \\
    -k uvicorn.workers.UvicornWorker \\
    -w 1 \\
    -b 0.0.0.0:8000 \\
    --timeout 120 \\
    --keep-alive 5 \\
    --preload \\
    --max-requests 5000 \\
    --max-requests-jitter 500
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
SVCEOF

cp "$DEPLOY_DIR/voicehub.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable voicehub
systemctl restart voicehub
echo "✅ systemd 服务已配置并启动"

# ===== 7. 验证 =====
echo ""
echo "===== [7/7] 验证服务 ====="
sleep 4
if systemctl is-active --quiet voicehub; then
    echo "✅ voicehub 服务运行中"
else
    echo "❌ voicehub 服务启动失败，日志："
    journalctl -u voicehub --no-pager -n 50
    exit 1
fi

if curl -s http://localhost:8000/api/health | grep -q 'healthy'; then
    echo "✅ API 健康检查通过"
else
    echo "⚠️  API 健康检查失败，请检查日志"
    journalctl -u voicehub --no-pager -n 20
fi

echo ""
echo "========== 部署完成 =========="
echo "后端地址: http://<服务器IP>:8000"
echo "域名访问: https://forum.example.com （需先配置 Nginx + SSL 证书）"
echo "查看日志: journalctl -u voicehub -f"
echo "重启服务: systemctl restart voicehub"
echo ""
echo "下一步：配置 Nginx（bash deploy-nginx.sh）"
