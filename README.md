# VoiceHub - FastAPI + Vue 论坛

基于 FastAPI + Vue 3 的企业内部论坛系统，支持企业微信 OAuth 登录、留言墙、金点子、反馈、私信、公告等功能。

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | FastAPI + SQLAlchemy 2.0 + PyMySQL | REST API，JWT 认证 |
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Axios | 移动端 H5，PWA |
| 数据库 | MySQL 8.0+ (utf8mb4) | 14 张表 |
| 实时通信 | SSE + WebSocket | 替代轮询，低延迟推送 |
| 认证 | JWT (python-jose) + 企业微信 OAuth | 强制登录，无游客模式 |
| 部署 | Gunicorn + Uvicorn + systemd | Linux 生产环境 |

## 目录结构

```
voicehub-fastapi-vue/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py             # FastAPI 入口（CORS + 路由注册 + 建表 + seed）
│   │   ├── config.py           # 配置（读取 .env）
│   │   ├── database.py         # SQLAlchemy 引擎 + SessionLocal + get_db
│   │   ├── security.py         # JWT 创建/验证 + 密码哈希 + Token 撤销
│   │   ├── deps.py             # 依赖注入（认证 / 管理员权限）
│   │   ├── utils.py            # 工具函数 + contextvars 批量预加载
│   │   ├── serialization.py    # 序列化函数
│   │   ├── scheduler.py        # 定时任务（统计快照等）
│   │   ├── seed.py             # 初始化测试数据
│   │   ├── models/             # 数据模型
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── services/           # 企业微信 API、内容安全检测
│   │   └── routes/             # 路由文件
│   ├── requirements.txt
│   ├── .env                    # 环境变量（不提交到版本库）
│   └── .env.example
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── main.js             # Vue 应用入口
│   │   ├── App.vue             # 根组件
│   │   ├── router/index.js     # 路由配置（hash 模式）
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── api/                # Axios API 封装
│   │   ├── views/              # 页面组件
│   │   ├── components/         # 通用组件
│   │   ├── composables/        # SSE / WebSocket 组合式函数
│   │   └── assets/style.css    # 样式（浅色/深色主题）
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── voicehub.service            # systemd 服务文件
├── deploy.ps1                  # Windows 部署脚本
├── deploy.sh                   # Linux 部署脚本
├── .gitignore
└── README.md
```

## 快速开始

### 1. 环境要求
- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Redis 6.0+

### 2. 后端配置
```bash
cd backend
pip install -r requirements.txt
# 复制 .env.example 为 .env，填入数据库连接等配置
```

`.env` 关键配置：
```env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/voicehub?charset=utf8mb4
JWT_SECRET_KEY=your-secret-key
CORS_ORIGINS=http://localhost:5173
REDIS_URL=redis://localhost:6379/0

# 企业微信（备案完成后启用）
WECOM_ENABLED=false
WECHAT_WORK_CORP_ID=your-corp-id
WECHAT_WORK_AGENT_ID=your-agent-id
WECHAT_WORK_SECRET=your-secret
WECHAT_WORK_OAUTH_REDIRECT_URI=https://your-domain.com/wecom/callback
WECOM_ADMIN_IDS=your-wecom-user-id
```

### 3. 数据库初始化
后端启动时自动建表（`db.create_all()`）并插入种子数据。

### 4. 开发模式（前后端分离）
```bash
# 后端
cd backend
python main.py
# 后端运行在 http://localhost:8000

# 前端
cd frontend
npm install
npm run dev
# 前端运行在 http://localhost:5173，API 代理到 8000
```

### 5. 生产部署（Linux）

#### 方式一：使用部署脚本
```bash
# 从 Windows 部署
.\deploy.ps1

# 从 Linux 部署
bash deploy.sh
```

#### 方式二：手动部署
```bash
# 1. 构建前端
cd frontend && npm install && npm run build && cd ..

# 2. 上传到服务器
scp -r backend frontend/dist voicehub.service root@server:/app/voice_hub/

# 3. 安装依赖
ssh root@server
cd /app/voice_hub/backend
pip install -r requirements.txt

# 4. 配置 systemd 服务
cp voicehub.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable voicehub
systemctl start voicehub

# 5. 验证
curl http://localhost:8000/api/health
```

## 认证机制

### 企业微信 OAuth 登录（唯一登录方式）
- 进入应用 → 检查 token → 无效则显示登录页
- 点击"企业微信登录"→ 跳转企微授权 → 回调带 token → 登录成功
- 管理员身份由数据库 `is_admin` 字段 + `WECOM_ADMIN_IDS` 白名单决定

### 权限体系
| 角色 | 权限 |
|---|---|
| user | 发布内容、点赞、评论、投票、反馈、私信 |
| admin | + 审核内容、回复反馈/私信、编辑公告、查看看板 |
| super_admin | + 管理用户角色、所有 admin 权限 |

## 核心功能

| 模块 | 功能 |
|---|---|
| 留言板 | 列表、详情、发布、点赞、评论、审核 |
| 金点子 | 提交、投票、献花、分类筛选、评审 |
| 反馈 | 分类提交、管理员回复、状态跟踪 |
| 私信 | 用户发私信、管理员回复（WebSocket 实时聊天） |
| 公告 | 查看、编辑、置顶 |
| 通知 | 实时推送、标记已读、未读角标 |
| 数据看板 | KPI、柱状图、用户排行榜（管理员） |

## 开发说明

- 前端使用 Vue 3 `<script setup>` + Composition API
- 状态管理用 Pinia（auth/data/ui/realtime/chat 五个 store）
- 路由用 hash 模式（兼容静态部署）
- 实时通信：SSE 推送数据更新 + WebSocket 实时聊天
- 所有交互保持乐观更新 + API 校正 + 失败回滚
- 暗色模式支持
- PWA 支持（VitePWA 自动注册 Service Worker）
