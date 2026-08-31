# VoiceHub 服务器部署说明

## 上传方式
用 WinSCP 将整个 `voicehub-deploy` 文件夹上传到服务器 `/app/voice_hub/` 目录。

## 部署前修改（上传前或上传后在服务器上改）

### 1. 修改 backend/.env
- `YOUR_MYSQL_PASSWORD` → 你服务器的 MySQL root 密码
- `CHANGE_ME_TO_RANDOM_32_CHARS_AT_LEAST` → 随机密钥（SSH 上去执行 `openssl rand -hex 32` 生成）

### 2. voicehub.service
- 脚本会自动根据服务器实际路径修改，无需手动改

## 部署步骤（SSH 登录服务器后执行）

```bash
cd /app/voice_hub
bash deploy-server.sh
```

脚本会自动完成：
1. 检查/安装 MySQL、Redis
2. 创建 voicehub 数据库
3. 安装 Python 依赖
4. 构建前端
5. 配置并启动 systemd 服务
6. 健康检查验证

## 部署后手动配置 Nginx + HTTPS

```bash
# 安装 Nginx
yum install -y nginx   # CentOS
# apt install -y nginx  # Ubuntu

# 复制配置
cp /app/voice_hub/nginx/voicehub.conf /etc/nginx/conf.d/

# 放置 SSL 证书到 /etc/nginx/ssl/
mkdir -p /etc/nginx/ssl
# （把华为云下载的证书上传到此处，或用 Let's Encrypt）
# Let's Encrypt 方式：
# yum install -y certbot python3-certbot-nginx
# certbot --nginx -d forum.example.com

# 启动 Nginx
nginx -t
systemctl start nginx
systemctl enable nginx
```

## 华为云安全组放行端口
- 80 (HTTP)、443 (HTTPS)、8000（后端，调试用）、22 (SSH)

## 企业微信后台配置
- 可信域名：forum.example.com
- 应用主页：https://forum.example.com
- 确认 CorpID / AgentId / Secret 与 .env 一致

## 常用运维命令
```bash
systemctl status voicehub      # 查看状态
systemctl restart voicehub     # 重启
journalctl -u voicehub -f      # 实时日志
systemctl restart nginx        # 重启 Nginx
```
