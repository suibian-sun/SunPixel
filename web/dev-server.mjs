/**
 * 本地开发服务器（零依赖）
 *
 * 线上是 Cloudflare Pages，`functions/` 里的接口由平台托管；
 * 本地直接 python -m http.server 时这些接口不存在，页面会退回内置数据。
 * 这个脚本把静态资源与两个 API 一起跑起来，方便本地验收：
 *
 *   node dev-server.mjs          # http://127.0.0.1:8788
 */

import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { onRequest as blocksApi } from './functions/api/blocks.js';
import { onRequest as changelogApi } from './functions/api/changelog.js';

const root = dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 8788);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.properties': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8'
};

async function serveStatic(pathname, res) {
  const relative = normalize(decodeURIComponent(pathname)).replace(/^(\.\.[/\\])+/, '');
  let filePath = join(root, relative);
  try {
    const info = await stat(filePath);
    if (info.isDirectory()) filePath = join(filePath, 'index.html');
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('404 Not Found');
    return;
  }

  try {
    const body = await readFile(filePath);
    res.writeHead(200, {
      'Content-Type': MIME[extname(filePath).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-store'
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('404 Not Found');
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (url.pathname === '/api/blocks' || url.pathname === '/api/changelog') {
    const handler = url.pathname === '/api/blocks' ? blocksApi : changelogApi;
    const response = await handler({ request: req });
    const body = await response.text();
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(body);
    return;
  }

  await serveStatic(url.pathname === '/' ? '/index.html' : url.pathname, res);
});

server.listen(port, '127.0.0.1', () => {
  console.log(`SunPixel 本地服务已启动：http://127.0.0.1:${port}`);
});
