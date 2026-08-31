# VoiceHub 项目维护手册

> 本文档整合自服务器上的 `README.md` 与 `README-DEPLOY.md`，并结合生产服务器（<服务器IP>）的实际运行状态核实整理（核实时间：2026-08-31），供后续维护者使用。
> 服务器上如已有 README 与本文冲突，以本文为准（本文按线上实际情况修正）。

---

## 一、项目概述

VoiceHub 是一个基于 **FastAPI + Vue 3** 的企业内部论坛系统（移动端 H5 / PWA，主要在企业微信内打开），通过**企业微信 OAuth 登录**，无游客模式。

功能模块：

| 模块 | 功能 |
|---|---|
| 留言板 | 列表、详情、发布、点赞、评论、审核 |
| 金点子 | 提交、投票、献花、分类筛选、评审 |
| 反馈 | 分类提交、管理员回复、状态跟踪 |
| 私信 | 用户发私信、管理员回复（WebSocket 实时聊天） |
| 公告 | 查看、编辑、置顶 |
| 通知 | SSE 实时推送、标记已读、未读角标 |
| 数据看板 | KPI、柱状图、用户排行榜（管理员） |

---

## 二、生产环境速查表 ★

维护这台服务器前先记住这张表：

| 项目 | 值 |
|---|---|
| 服务器 | 华为云 ECS `<服务器IP>`（主机名 `<服务器主机名>`，Ubuntu，SSH 用户 root） |
| 正式域名 | `https://forum.example.com`（HTTP 自动 301 跳 HTTPS；Nginx 同时绑定了 IP，可直接 IP 访问） |
| 代码目录 | `/home/app/voicehub/voicehub-deploy` |
| **前端线上目录** | **`/var/www/voicehub`**（Nginx 直接托管静态文件，见下方"架构"说明） |
| 后端入口 | `backend/app/main.py`（FastAPI，`app.main:app`） |
| 后端进程 | gunicorn + uvicorn worker，1 个 worker，监听 `0.0.0.0:8000` |
| Python 环境 | `/root/miniconda3/envs/voicehub`（Python 3.11，conda 环境 `voicehub`） |
| 后端系统服务 | systemd 服务 `voicehub`（enabled，开机自启） |
| Web 服务 | Nginx，监听 80 / 443，站点配置 `/etc/nginx/sites-enabled/voicehub` |
| SSL 证书 | `/etc/nginx/ssl/forum.example.com.pem` / `.key` |
| 数据库 | MySQL 8（本机），库名 `voicehub`，utf8mb4，14 张表 |
| 缓存 / 限流 | Redis（本机 6379，db 0） |
| 健康检查 | `curl http://127.0.0.1:8000/api/health` → `{"code":200,...,"status":"healthy"}` |
| 登录方式 | 企业微信 OAuth（`WECOM_ENABLED=true`）+ JWT（有效期 24 小时） |
| 数据库备份 | `/home/app/voicehub/backups/`（如 `voicehub_20260812_141018.sql`） |

> 2026-08-31 核实：`voicehub` 服务 active，自 2026-08-12 起持续运行，内存占用约 135MB，健康检查正常。

---

## 三、架构与请求链路

```
用户（企业微信 / 浏览器）
        │  https://forum.example.com
        ▼
   Nginx (443, TLS)
        │
        ├─ /            → 静态文件 /var/www/voicehub（Vue 构建产物，SPA 回退 index.html）
        ├─ /wecom/      → 反代 127.0.0.1:8000   （企业微信 OAuth 回调）
        ├─ /api/        → 反代 127.0.0.1:8000   （FastAPI REST API）
        ├─ /api/ws      → 反代 8000，带 Upgrade 头（WebSocket 实时聊天，read_timeout 86400）
        ├─ /api/sse     → 反代 8000，proxy_buffering off（SSE 通知推送，read_timeout 86400）
        ▼
   gunicorn (uvicorn worker) :8000  ←→  MySQL(本机) + Redis(本机)
```

### Nginx 缓存策略（很重要，别改坏）

线上配置对缓存做了精细控制，原因是**企业微信内置浏览器会强缓存旧版文件**：

- `index.html`、`sw.js`、`registerSW.js`、`manifest.webmanifest` → 强制 `no-cache, no-store, must-revalidate`（每次都向服务器校验新版本）；
- 带内容 hash 指纹的静态资源（js/css/图片/字体）→ 缓存 30 天 `immutable`；
- HTTP 80 全部 301 跳 HTTPS（企微 OAuth 强制要求 HTTPS）。

### 一个容易搞混的点

- **线上前端静态文件由 Nginx 从 `/var/www/voicehub` 直接提供**；
- 同时 `backend/app/main.py` 里也有一套 SPA 托管逻辑（指向 `frontend/dist`），直连 8000 端口也能打开页面——那只是备用/调试用途；
- **两处内容需保持一致，以 `/var/www/voicehub` 为线上正式版本。** 发版时别忘了同步它（见"发版流程"）。

---

## 四、目录结构

```
/home/app/voicehub/
├── backups/                        # 数据库备份（mysqldump 产物）
├── voicehub_deploy_latest.zip      # 上传的部署包存档
└── voicehub-deploy/                # ★ 项目主目录（systemd 工作目录指向这里）
    ├── backend/
    │   ├── app/
    │   │   ├── main.py             # FastAPI 入口（CORS + 路由注册 + 建表 + seed + SPA 托管）
    │   │   ├── config.py           # 读取 .env 配置
    │   │   ├── database.py         # SQLAlchemy 引擎 / SessionLocal / get_db
    │   │   ├── security.py         # JWT 创建/验证 + 密码哈希 + Token 撤销
    │   │   ├── deps.py             # 依赖注入（认证 / 管理员权限）
    │   │   ├── scheduler.py        # 定时任务（统计快照等）
    │   │   ├── seed.py             # 初始化测试数据
    │   │   ├── models/  schemas/  services/   # ORM 模型 / Pydantic 模型 / 企微 API 等
    │   │   └── routes/             # 14 个路由模块：
    │   │       auth  user  voice  comment  idea  feedback  message
    │   │       announce  notification  dashboard  data
    │   │       sse  websocket  wecom_auth
    │   ├── requirements.txt
    │   ├── .env                    # ★ 生产环境配置（真实密钥在这里，勿外传/勿提交）
    │   └── .env.example            # 配置模板
    ├── frontend/
    │   ├── src/                    # Vue3 源码（views/components/stores/api/composables）
    │   ├── vite.config.js          # PWA + 压缩 + 分包 + dev 代理
    │   ├── dist/                   # 前端构建产物
    │   └── dist.bak_v2p05/         # 上一版 dist 备份（手工回滚用）
    ├── nginx/voicehub.conf         # ⚠️ 早期 Nginx 配置模板，与线上配置有差异（见"已知事项"）
    ├── voicehub.service            # systemd 服务模板（deploy-server.sh 会按实际路径重写）
    ├── server.mjs                  # 备用方案：Node 静态服务 + API 代理（端口 3000，当前未启用）
    ├── deploy.ps1                  # Windows 本地一键部署脚本（打包→scp→服务器解压重启）
    ├── deploy.sh                   # Linux 本地一键部署脚本（同上）
    ├── deploy-server.sh            # 服务器端一键初始化脚本（首次装环境用）
    ├── package.json                # 顶层脚本（dev/build/start 等）
    ├── README.md                   # 项目原 README（功能、开发说明）
    └── README-DEPLOY.md            # 部署原 README（本手册已整合其内容）
```

---

## 五、技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | FastAPI + SQLAlchemy 2.0 + PyMySQL | REST API，JWT 认证，GZip 中间件 |
| 运行时 | gunicorn + UvicornWorker（Python 3.11） | `--max-requests 5000` 自动回收 worker，属正常现象 |
| 前端 | Vue 3 + Vite 5 + Pinia + Vue Router(hash) + Vue Query + GSAP | 移动端 H5 |
| PWA | vite-plugin-pwa + brotli/gzip 压缩 + 手动分包 | Service Worker 自动更新 |
| 实时通信 | SSE（通知推送）+ WebSocket（私信聊天） | Nginx 有专门的反代配置 |
| 认证 | 企业微信 OAuth + JWT（python-jose，HS256，24h） | 无游客模式 |
| 数据 | MySQL 8.0（utf8mb4，14 张表）+ Redis 5+ | 启动时 `create_all()` 自动建表 + 种子数据 |
| 部署 | systemd + Nginx（HTTPS） | 见下文 |

---

## 六、配置文件说明（backend/.env）

生产环境配置文件在服务器 `backend/.env`，**改完任何一项必须 `systemctl restart voicehub` 才生效**。以下为项目 `.env` 的完整内容（含各配置项的注释说明）：

```env
# ===== 数据库 =====
DATABASE_URL=mysql+pymysql://root:<MySQL密码>@localhost:3306/voicehub?charset=utf8mb4

# ===== JWT =====
JWT_SECRET_KEY=<JWT密钥>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRES=86400

# ===== 管理员 =====
ADMIN_DEFAULT_PASSWORD=<管理员密码>
ADMIN_TOKEN_SECRET=<管理员Token密钥>

# ===== CORS =====
CORS_ORIGINS=https://forum.example.com,http://<服务器IP>,http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173

# ===== 运行环境 =====
FLASK_ENV=development

# ===== Redis =====
REDIS_URL=redis://localhost:6379/0

# ===== 企业微信 =====
# 总开关：备案完成后设为 true 启用（测试阶段保持 false）
WECOM_ENABLED=true
WECHAT_WORK_CORP_ID=<你的企业CorpID>
WECHAT_WORK_AGENT_ID=<AgentId-A>
WECHAT_WORK_SECRET=<企微应用Secret>
# 通讯录同步应用 Secret（用于拉取组织架构和成员）
WECOM_CONTACT_SECRET=<企微通讯录Secret>
# OAuth 回调地址：必须与企微后台「可信域名」一致（HTTPS、已备案）
WECHAT_WORK_OAUTH_REDIRECT_URI=https://forum.example.com/wecom/callback
# 管理员企微 UserId 白名单（逗号分隔）
WECOM_ADMIN_IDS=<企微管理员UserId白名单>
# 应用访问地址（用于企微推送消息点击跳转）
WECOM_APP_URL=https://forum.example.com

# ===== 端口 =====
PORT=8000
```

### ⚠️ 重要：此文件与服务器线上生效版本存在差异（2026-08-31 核对）

上面这份是开发/模板版配置。SSH 到服务器实际读到的线上 `backend/.env` 与它**并不相同**，发版时切勿拿这份文件直接覆盖线上 `.env`：

| 配置项 | 本文档版 | 线上实际值 | 影响 |
|---|---|---|---|
| WECHAT_WORK_AGENT_ID | <AgentId-A> | **<AgentId-B>** | 对应企微后台**两个不同的自建应用**，Secret 也不同。线上 OAuth 走的是 <AgentId-B>；若换成 <AgentId-A> 而企微后台应用未同步调整，登录会失败 |
| WECHAT_WORK_SECRET | <Secret-A前缀>（<AgentId-A> 的） | <Secret-B前缀>（<AgentId-B> 的） | 必须与 AgentId 配套使用 |
| JWT_SECRET_KEY | <JWT密钥> | 另一个随机值 | 一旦改掉，所有在线用户 token 立即失效，需重新登录 |
| FLASK_ENV | development | **production** | 生产环境必须为 production |
| CORS_ORIGINS | 6 项（含 localhost） | 2 项（域名 + IP） | 线上配置更严格 |
| POOL_SIZE / POOL_RECYCLE | 没有 | 20 / 3600 | 线上有数据库连接池配置 |
| ADMIN_DEFAULT_PASSWORD / ADMIN_TOKEN_SECRET | 有 | **无此二键** | 若后端代码会读取这两个键，线上与开发版行为可能不同 |

**维护原则：需要变更线上配置时，直接 SSH 改服务器上的 `backend/.env`，改前先备份（如复制到 `backups/` 存档），改完 `systemctl restart voicehub`；不要从本地拿旧文件覆盖。**

其他注意事项：
1. `WECHAT_WORK_OAUTH_REDIRECT_URI` 必须与企微后台「可信域名」一致，且必须是 HTTPS。
2. 管理员身份 = 数据库 `users.is_admin` 字段 + `WECOM_ADMIN_IDS` 白名单（YEWA、YHAD、FELY）共同决定。
3. `ADMIN_DEFAULT_PASSWORD=<管理员密码>` 是弱密码且已写入本文档，若该键实际生效，建议尽快更换。

---

## 七、日常运维命令

```bash
# ===== 服务状态 / 日志 / 重启 =====
systemctl status voicehub          # 查看后端状态
journalctl -u voicehub -f          # 实时日志
journalctl -u voicehub -n 200      # 最近 200 行
systemctl restart voicehub         # 重启后端（改 .env / 更新代码后执行）

# ===== 健康检查 =====
curl http://127.0.0.1:8000/api/health        # 后端
curl -I https://forum.example.com                # Nginx + 证书

# ===== Nginx =====
nginx -t                            # 改配置后先测语法
systemctl reload nginx              # 平滑重载
cat /etc/nginx/sites-enabled/voicehub   # 查看线上站点配置

# ===== 数据库备份（建议定期执行）=====
mysqldump -u root -p voicehub > /home/app/voicehub/backups/voicehub_$(date +%Y%m%d_%H%M%S).sql

# ===== 数据库恢复 =====
mysql -u root -p voicehub < /home/app/voicehub/backups/voicehub_XXXX.sql

# ===== 进入后端 Python 环境（手动调试用）=====
source /root/miniconda3/bin/activate voicehub
cd /home/app/voicehub/voicehub-deploy/backend
```

---

## 八、发版（更新）流程 ★

### 前端更新

1. 改代码后，**先递增 `frontend/vite.config.js` 里的 `workbox.cacheId`**（如 `voicehub-v2p05` → `v2p06`）。不递增的话企业微信内置浏览器可能继续用旧缓存。
2. 构建：`cd frontend && npm install && npm run build`（产物在 `frontend/dist`）。
3. 备份线上旧版本：把当前 `/var/www/voicehub` 复制一份留档（2026-08-31 清理后，现存的唯一历史备份是 `frontend/dist.bak_v2p05`，即 v2p05 版）。
4. **把 `dist/` 内容同步到 `/var/www/voicehub/`**（这一步部署脚本不会自动做，必须手动执行，例如 `rsync -a --delete frontend/dist/ /var/www/voicehub/`）。
5. 后端不用重启（静态文件即时生效）；浏览器验证，必要时强刷。

### 后端更新

1. 上传 `backend/` 到 `/home/app/voicehub/voicehub-deploy/`（覆盖 app 目录即可，`.env` 不要覆盖）。
2. 若依赖有变化：`/root/miniconda3/envs/voicehub/bin/pip install -r requirements.txt`。
3. `systemctl restart voicehub`，然后 `curl http://127.0.0.1:8000/api/health` 验证。

### 从本地一键上传（可选）

`deploy.ps1`（Windows）/ `deploy.sh`（Linux）会自动：打包 `backend + frontend/dist + voicehub.service` → scp 到服务器 `/opt/voicehub-fastapi-vue.tar.gz` → 解压到部署目录 → 重启服务。
⚠️ **这两个脚本不会同步 `/var/www/voicehub`**，前端发版仍需按上面第 4 步手动同步。

### 回滚

- 前端：现存唯一历史备份是 `voicehub-deploy/frontend/dist.bak_v2p05`（v2p05 版），恢复时把它同步回 `/var/www/voicehub`；更早的版本需用对应版本源码重新构建。
- 数据库：恢复 `backups/` 里对应时间的 dump。
- 后端：重新部署旧版本代码后 `systemctl restart voicehub`。

---

## 九、首次部署（从零搭建，换新服务器时才需要）

1. 上传整个 `voicehub-deploy` 目录到服务器（WinSCP / scp），放至 `/home/app/voicehub/`。
2. 修改 `backend/.env`：填 MySQL 密码、`JWT_SECRET_KEY`（`openssl rand -hex 32` 生成）、企微四件套。
3. 安装 miniconda 并创建 `voicehub` 环境（Python 3.11），或改用系统 Python（需同步改 service 文件路径）。
4. 执行服务器端一键脚本（自动装 MySQL/Redis、建库、装依赖、构建前端、配置 systemd、健康检查）：
   ```bash
   cd /home/app/voicehub/voicehub-deploy
   bash deploy-server.sh
   ```
   ⚠️ 该脚本第 13 行注释中**含有明文 MySQL root 密码**，部署完成后建议删除该注释。
5. 手动配置 Nginx + 证书（参照下节"已知事项"第 2 条，以线上现配置为模板最好）：
   - 配置放 `/etc/nginx/sites-enabled/voicehub`；
   - 证书放 `/etc/nginx/ssl/forum.example.com.pem/.key`（华为云下载免费证书，或 certbot）；
   - 前端静态：`rsync -a frontend/dist/ /var/www/voicehub/`。
6. 华为云安全组放行：80、443、22。**8000 建议不对公网放行**（统一走 Nginx）。
7. 企业微信后台配置：可信域名 `forum.example.com`，应用主页 `https://forum.example.com`，CorpID / AgentId / Secret 与 `.env` 保持一致。

---

## 十、认证与权限体系

### 登录流程（企业微信 OAuth，唯一登录方式）

1. 进入应用 → 前端检查本地 token，无效则显示登录页；
2. 点击"企业微信登录" → 跳转企微授权页；
3. 授权后回调 `https://forum.example.com/wecom/callback` → 后端用 code 换用户身份、签发 JWT；
4. 前端保存 token，后续请求携带，24 小时过期。

### 角色权限

| 角色 | 权限 |
|---|---|
| user | 发布内容、点赞、评论、投票、反馈、私信 |
| admin | + 审核内容、回复反馈/私信、编辑公告、查看看板 |
| super_admin | + 管理用户角色（拥有全部 admin 权限） |

`super_admin` 由 `.env` 的 `WECOM_ADMIN_IDS` 白名单 + 数据库 `is_admin` 字段决定。

---

## 十一、本地开发

```bash
# 环境要求：Python 3.10+ / Node 18+ / MySQL 8+ / Redis 6+

# 1. 后端
cd backend
pip install -r requirements.txt
cp .env.example .env          # 填好数据库等配置；开发期 WECOM_ENABLED=false
python -m uvicorn app.main:app --reload --port 8000

# 2. 前端
cd frontend
npm install
npm run dev                   # http://localhost:5173，已配置代理 /api → 8000

# 或一键同时启动前后端（顶层目录）
npm run dev
```

前端要点（改代码前了解）：

- Vue 3 `<script setup>` + Composition API；Pinia 五个 store（auth/data/ui/realtime/chat）；
- 路由 hash 模式；实时通信用 SSE + WebSocket（`composables/` 里有封装）；
- 交互模式：乐观更新 + API 校正 + 失败回滚；
- 支持暗色模式；PWA 自动注册 Service Worker。

---

## 十二、已知事项与踩坑记录（务必阅读）

1. **前端线上目录是 `/var/www/voicehub`，不是 `frontend/dist`**。`dist` 只是构建产物；Nginx 从 `/var/www/voicehub` 提供服务，发版必须手动同步（历史上有过忘了同步导致"部署了没生效"的风险）。线上当前版本为 **v2p06**（看 `/var/www/voicehub/sw.js` 里的 cacheId 即可确认），而服务器上的源码副本可能滞后于线上——**一切以 `/var/www/voicehub` 为准**。历史版本备份已于 2026-08-31 清理，现仅存 `frontend/dist.bak_v2p05`（v2p05）。
2. **仓库里的 `nginx/voicehub.conf` 是早期模板，与线上配置不一致**。线上真实配置在 `/etc/nginx/sites-enabled/voicehub`（比模板多了：server_name 额外绑定 IP、`/wecom/` location、index.html/sw.js 强缓存策略、静态资源 30 天 immutable）。要改 Nginx 请以线上文件为准，改完 `nginx -t && systemctl reload nginx`。
3. **企业微信内置浏览器缓存非常顽固**：任何前端发版都必须递增 `vite.config.js` 的 `workbox.cacheId`；Nginx 对 `index.html`/`sw.js` 的 no-cache 配置不要删。
4. **Service Worker 对 `/wecom/` 路径禁用了导航接管**（`navigateFallbackDenylist: [/^\/wecom\//]`），否则企微 OAuth 回调会被 SW 拦截导致**登录死循环**。这是修过的 bug，别回退。
5. 日志中偶见 `/api/ws` 403（约每天十几次）：旧标签页持过期 JWT 反复重连被拒，属正常现象可忽略；若短时间内大量出现再排查 token 逻辑。
6. `server.mjs`（Node 端口 3000，静态 + API 代理）是备用部署方案，**当前未启用**，线上是 Nginx 直连 8000。
7. gunicorn 配了 `--max-requests 5000`，worker 会定期自动重启回收，日志里出现重启属正常。
8. **密钥分布**：`backend/.env`（JWT 密钥、企微 Secret、数据库密码）、`deploy-server.sh` 第 13 行注释（明文 MySQL 密码）、本文档第六节（已脱敏，真实值见服务器backend/.env）。均仅限内部维护人员传阅，勿提交公开仓库。`ADMIN_DEFAULT_PASSWORD`（弱密码，见服务器.env）和 `JWT_SECRET_KEY`（<JWT密钥>）都是弱密钥，建议尽快轮换。
9. 后端 8000 端口监听 `0.0.0.0`（公网可达）。直连 8000 可绕过 Nginx，仅调试用，建议安全组不对公网放行 8000。

---

## 十三、常见问题排查

| 现象 | 排查顺序 |
|---|---|
| 整站打不开 | `systemctl status nginx` → `systemctl status voicehub` → `curl 127.0.0.1:8000/api/health` → 各自日志 |
| 接口 502 | 后端挂了，看 `journalctl -u voicehub -n 100`，常见为 `.env` 配错或依赖缺失 |
| 登录死循环 / 回调失败 | 证书是否过期 → `.env` 回调 URI 与企微后台是否一致 → 是否动了 SW 的 `/wecom/` 排除规则 |
| 前端还是旧版 | `/var/www/voicehub` 是否真的同步了 → `workbox.cacheId` 是否递增 → 强刷 / 清企微缓存 |
| WebSocket / 通知不实时 | Nginx 的 `/api/ws`（Upgrade 头）和 `/api/sse`（关缓冲）配置是否还在 |
| 数据库连接失败 | `systemctl status mysql` → 手动 `mysql -u root -p` 验证密码 → 检查 `.env` 的 `DATABASE_URL`（密码含特殊字符需 URL 编码） |

---

## 附：维护记录

- **2026-08-31 文件清理**：删除了失效的 `voicehub-backend.service` 旧服务单元（指向不存在的 `/home/voicehub/...`，且处于 enabled 状态，每次开机都会启动失败一次）、`voicehub_deploy_latest.zip`（29MB 部署包）、`/tmp` 下 8 个临时文件（含 3 份带密钥的旧 `.env` 备份）、失效的 `/opt/remote-deploy.sh`、空目录 `/app`、Nginx 旧配置备份 `voicehub.bak.`；前端历史备份删除 v2p02 × 2 和 v2p04（目录名 `voicehub_bak_v2p05` 有误导性，实际装的是 v2p04 构建），保留最新备份 `frontend/dist.bak_v2p05`（v2p05）。清理后已验证：服务 active、健康检查 200、`nginx -t` 通过。

*文档核实时间：2026-08-31。服务器状态、路径、配置均以当日线上实际情况为准。*
