# VoiceHub FastAPI+Vue 部署脚本
# 用法: .\deploy.ps1
# 部署到 106.63.7.122 服务器

$SERVER = "root@106.63.7.122"
$REMOTE_PATH = "/opt/voicehub-fastapi-vue.tar.gz"
$DEPLOY_PATH = "/app/voice_hub"

Write-Host "===== VoiceHub FastAPI+Vue 部署 =====" -ForegroundColor Cyan

# 1. 构建前端
Write-Host "[1/5] 构建前端..." -ForegroundColor Yellow
$frontendDir = "$PSScriptRoot\frontend"
Push-Location $frontendDir
npm install --silent
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "前端构建失败！" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "前端构建完成" -ForegroundColor Green

# 2. 打包
Write-Host "[2/5] 打包项目..." -ForegroundColor Yellow
$tarFile = "$PSScriptRoot\voicehub-fastapi-vue.tar.gz"
# 排除不需要的文件
$exclude = @("--exclude=`".git`"", "--exclude=`"__pycache__`"", "--exclude=`"*.pyc`"", "--exclude=`".env`"", "--exclude=`"node_modules`"", "--exclude=`".trae`"")
tar -czf $tarFile -C $PSScriptRoot backend frontend/dist voicehub.service *.ps1 *.sh $exclude
Write-Host "打包完成" -ForegroundColor Green

# 3. 上传
Write-Host "[3/5] 上传到服务器..." -ForegroundColor Yellow
scp $tarFile "${SERVER}:$REMOTE_PATH"
if ($LASTEXITCODE -ne 0) {
    Write-Host "上传失败！" -ForegroundColor Red
    exit 1
}
Write-Host "上传完成" -ForegroundColor Green

# 4. 远程部署
Write-Host "[4/5] 远程部署..." -ForegroundColor Yellow
$deployScript = @"
set -e
cd /opt

# 停止旧服务
systemctl stop voicehub 2>/dev/null || true

# 备份旧版本
if [ -d '$DEPLOY_PATH' ]; then
    BACKUP_DIR='${DEPLOY_PATH}-backup-'`$(date +%Y%m%d%H%M%S)
    mv '$DEPLOY_PATH' "`$BACKUP_DIR"
    echo "旧版本已备份到 `$BACKUP_DIR"
fi

# 创建部署目录
mkdir -p '$DEPLOY_PATH'

# 解压新版
tar -xzf voicehub-fastapi-vue.tar.gz -C '$DEPLOY_PATH'

# 从备份恢复 .env
if [ -f '`${BACKUP_DIR:-/tmp}/backend/.env' ]; then
    cp '`${BACKUP_DIR}/backend/.env' '$DEPLOY_PATH/backend/.env'
    echo '.env 已恢复'
fi

# 安装 Python 依赖
cd '$DEPLOY_PATH/backend'
/root/miniconda3/envs/voicehub/bin/pip install -r requirements.txt -q

# 安装 systemd 服务
cp '$DEPLOY_PATH/voicehub.service' /etc/systemd/system/
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
"@

ssh $SERVER $deployScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "远程部署失败！" -ForegroundColor Red
    exit 1
}
Write-Host "远程部署完成" -ForegroundColor Green

# 5. 清理本地临时文件
Write-Host "[5/5] 清理临时文件..." -ForegroundColor Yellow
Remove-Item $tarFile -Force -ErrorAction SilentlyContinue
Write-Host "清理完成" -ForegroundColor Green

Write-Host ""
Write-Host "===== 部署成功 =====" -ForegroundColor Cyan
Write-Host "服务地址: http://106.63.7.122:8000" -ForegroundColor White
Write-Host "查看日志: ssh $SERVER 'journalctl -u voicehub -f'" -ForegroundColor White
Write-Host "重启服务: ssh $SERVER 'systemctl restart voicehub'" -ForegroundColor White
