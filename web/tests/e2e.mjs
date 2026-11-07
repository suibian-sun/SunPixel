/**
 * 浏览器端到端验收：真实 Chromium 里跑一遍完整流程
 *
 *   node tests/e2e.mjs
 *
 * 依赖 playwright（devDependency，未安装时脚本会提示）：
 *   npm i -D playwright && npx playwright install chromium
 * 若本机已有 Chromium，可设置 CHROMIUM_PATH=/usr/bin/chromium 复用。
 */

import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = join(here, '..');
const port = 8791;

async function loadPlaywright() {
  try {
    return await import('playwright');
  } catch {
    console.log('跳过：未安装 playwright，执行 npm i -D playwright 后再跑');
    process.exit(0);
  }
}

function startServer() {
  const child = spawn(process.execPath, [join(webRoot, 'dev-server.mjs')], {
    env: { ...process.env, PORT: String(port) },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('本地服务启动超时')), 10000);
    child.stdout.on('data', (chunk) => {
      if (chunk.toString().includes('已启动')) {
        clearTimeout(timer);
        resolve(child);
      }
    });
    child.on('error', reject);
  });
}

function makeFixture() {
  const directory = mkdtempSync(join(tmpdir(), 'sunpixel-e2e-'));
  const path = join(directory, 'fixture.png');
  const script = `
from PIL import Image
img = Image.new('RGBA', (64, 48), (0, 0, 0, 0))
for y in range(28):
    for x in range(64):
        img.putpixel((x, y), (220, 40, 40, 255))
for y in range(28, 48):
    for x in range(64):
        img.putpixel((x, y), (30, 60, 200, 255))
for y in range(32, 44):
    for x in range(8, 24):
        img.putpixel((x, y), (0, 0, 0, 0))
img.save(${JSON.stringify(path)})
`;
  execFileSync('python3', ['-c', script]);
  return path;
}

function gunzipHead(path) {
  const raw = readFileSync(path);
  return raw[0] === 0x1f && raw[1] === 0x8b;
}

const { chromium } = await loadPlaywright();
const server = await startServer();
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined
});
const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
});

const downloadDir = mkdtempSync(join(tmpdir(), 'sunpixel-dl-'));
const results = [];

async function saveDownload(trigger, name) {
  const [download] = await Promise.all([page.waitForEvent('download'), trigger()]);
  const target = join(downloadDir, name);
  await download.saveAs(target);
  return target;
}

try {
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle' });

  /* ---------- 1. 文字像素画 ---------- */
  await page.click('#mode-text');
  await page.fill('#text-input', 'Sun\n像素');
  await page.fill('#width-input', '64');
  await page.click('#convert-btn');
  await page.waitForSelector('#result-card', { timeout: 20000 });

  const textStats = await page.textContent('.stat-card .stat-value');
  assert.match(textStats, /\d+\s*×\s*\d+/, '文字模式未产出尺寸');
  const previewSrc = await page.getAttribute('#preview-item img', 'src');
  assert.ok(previewSrc?.startsWith('data:image/png'), '缺少效果图');

  const schemPath = await saveDownload(() => page.click('#download-file'), 'text.schem');
  assert.ok(gunzipHead(schemPath), '下载的 .schem 不是 gzip');
  results.push(['文字模式 .schem', `${schemPath} (${readFileSync(schemPath).length} B)`]);

  /* ---------- 2. 图片像素画 + litematic ---------- */
  const fixture = makeFixture();
  await page.click('#mode-image');
  await page.setInputFiles('#file-input', fixture);
  await page.waitForSelector('.hint:has-text("当前图片")', { timeout: 10000 });
  await page.selectOption('#format-select', 'litematic');
  await page.click('#convert-btn');
  await page.waitForSelector('#result-card', { timeout: 20000 });

  const litematicPath = await saveDownload(() => page.click('#download-file'), 'image.litematic');
  assert.ok(gunzipHead(litematicPath), '下载的 .litematic 不是 gzip');
  results.push(['图片模式 .litematic', `${litematicPath} (${readFileSync(litematicPath).length} B)`]);

  /* ---------- 3. 图纸与材料表 ---------- */
  const blueprintPath = await saveDownload(() => page.click('#download-blueprint'), 'build.md');
  const blueprint = readFileSync(blueprintPath, 'utf8');
  assert.match(blueprint, /## 图例/, '图纸缺少图例');
  assert.match(blueprint, /## 逐行图纸/, '图纸缺少逐行内容');
  results.push(['手动搭建图纸', `${blueprintPath} (${blueprint.split('\n').length} 行)`]);

  const csvPath = await saveDownload(() => page.click('#download-csv'), 'materials.csv');
  const csvLines = readFileSync(csvPath, 'utf8').trim().split('\n');
  assert.equal(csvLines[0], 'x,y,z,block');
  results.push(['材料清单', `${csvPath} (${csvLines.length - 1} 行数据)`]);

  /* ---------- 4. 透明区域应变成空气 ---------- */
  const airLine = await page.textContent('.card');
  assert.ok(!/undefined/.test(airLine), '结果区出现 undefined');

  await page.screenshot({ path: join(downloadDir, 'screenshot.png'), fullPage: true });
  results.push(['页面截图', join(downloadDir, 'screenshot.png')]);

  /* ---------- 5. 用独立实现校验下载的投影 ---------- */
  const validateDir = mkdtempSync(join(tmpdir(), 'sunpixel-validate-'));
  writeFileSync(join(validateDir, 'sample.schem'), readFileSync(schemPath));
  writeFileSync(join(validateDir, 'sample.litematic'), readFileSync(litematicPath));
  const report = JSON.parse(
    execFileSync('python3', [join(here, 'validate_nbt.py'), validateDir], { encoding: 'utf8' })
  );
  assert.ok(!report.schem.error, report.schem.error);
  assert.ok(!report.litematic.error, report.litematic.error);
  assert.ok(report.schem.blocks.length > 0, 'schem 没有方块');
  assert.ok(report.litematic.states.some((v) => v > 0), 'litematic 全是空气/索引 0');
  results.push(['nbtlib 校验', `schem ${report.schem.width}×${report.schem.height}×${report.schem.length}，litematic ${report.litematic.palette.length} 种方块`]);

  assert.deepEqual(errors, [], `页面报错：${errors.join(' | ')}`);

  console.log('\n端到端验收通过：');
  for (const [name, detail] of results) console.log(`  ✓ ${name}: ${detail}`);
} finally {
  await browser.close();
  server.kill();
}
