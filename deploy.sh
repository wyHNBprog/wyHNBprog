#!/bin/bash
# VoiceHub FastAPI+Vue 部署脚本（Linux）
# 用法: bash deploy.sh
# 部署到远程服务器

set -e

# ===== 配置（按实际环境修改）=====
SERVER="root@106.63.7.122"
REMOTE_PATH="/opt/voicehub-fastapi-vue.tar.gz"
DEPLOY_PATH="/app/voice_hub"
# Python 环境路径（根据实际环境修改：conda / venv / 系统 Python）
PYTHON_BIN="/root/miniconda3/envs/voicehub/bin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "===== VoiceHub FastAPI+Vue 部署 ====="

# 1. 构建前端
echo "[1/5] 构建前端..."
cd "$SCRIPT_DIR/frontend"
npm install --silent
npm run build
echo "前端构建完成"

# 2. 打包
echo "[2/5] 打包项目..."
cd "$SCRIPT_DIR"
tar -czf voicehub-fastapi-vue.tar.gz \
    --exclude=".git" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude=".env" \
    --exclude="node_modules" \
    --exclude=".trae" \
    backend frontend/dist voicehub.service deploy.sh
echo "打包完成"

# 3. 上传
echo "[3/5] 上传到服务器..."
scp voicehub-fastapi-vue.tar.gz "${SERVER}:${REMOTE_PATH}"
echo "上传完成"

# 4. 远程部署
echo "[4/5] 远程部署..."
ssh "$SERVER" bash -s << REMOTE_SCRIPT
set -e
cd /opt

# 停止旧服务
systemctl stop voicehub 2>/dev/null || true

# 备份旧版本
if [ -d "${DEPLOY_PATH}" ]; then
    BACKUP_DIR="${DEPLOY_PATH}-backup-\$(date +%Y%m%d%H%M%S)"
    mv "${DEPLOY_PATH}" "\$BACKUP_DIR"
    echo "旧版本已备份到 \$BACKUP_DIR"
fi

# 创建部署目录
mkdir -p "${DEPLOY_PATH}"

# 解压新版
tar -xzf voicehub-fastapi-vue.tar.gz -C "${DEPLOY_PATH}"

# 从备份恢复 .env
if [ -f "\${BACKUP_DIR:-/tmp}/backend/.env" ]; then
    cp "\${BACKUP_DIR}/backend/.env" "${DEPLOY_PATH}/backend/.env"
    echo '.env 已恢复'
fi

# 安装 Python 依赖
cd "${DEPLOY_PATH}/backend"
${PYTHON_BIN}/pip install -r requirements.txt -q

# 安装 systemd 服务
cp "${DEPLOY_PATH}/voicehub.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable voicehub

# 启动服务
systemctl start voicehub

# 等待启动
sleep 3

# 验证
if systemctl is-active --quiet voicehub; then
    echo '✅ 服务启动成功'
else
    echo '❌ 服务启动失败'
    journalctl -u voicehub --no-pager -n 50
    exit 1
fi

# API 自测
curl -s http://localhost:8000/api/health | grep -q 'healthy' && echo '✅ API 健康检查通过' || echo '⚠️ API 健康检查失败'

# 清理
rm -f voicehub-fastapi-vue.tar.gz
echo '部署完成'
REMOTE_SCRIPT

echo "远程部署完成"

# 5. 清理本地临时文件
echo "[5/5] 清理临时文件..."
rm -f "$SCRIPT_DIR/voicehub-fastapi-vue.tar.gz"
echo "清理完成"

echo ""
echo "===== 部署成功 ====="
echo "服务地址: http://106.63.7.122:8000"
echo "查看日志: ssh $SERVER 'journalctl -u voicehub -f'"
echo "重启服务: ssh $SERVER 'systemctl restart voicehub'"
