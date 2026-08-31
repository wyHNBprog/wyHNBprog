// Node 生产服务器：静态文件服务 + API 反向代理到 FastAPI
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
const STATIC_DIR = path.join(__dirname, 'frontend', 'dist');

const app = express();

// API 反向代理到 FastAPI 后端
app.use(
  '/api',
  createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
  })
);

// 静态文件服务（Vue 构建产物）
app.use(express.static(STATIC_DIR));

// SPA 回退：非 API 路由都返回 index.html
app.get('*', (req, res) => {
  if (req.path.startsWith('/api/')) {
    return res.status(404).json({ code: 404, message: 'API 不存在', data: null });
  }
  res.sendFile(path.join(STATIC_DIR, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`[Node] 生产服务器已启动: http://localhost:${PORT}`);
  console.log(`[Node] 后端代理目标: ${BACKEND_URL}`);
  console.log(`[Node] 静态文件目录: ${STATIC_DIR}`);
});
