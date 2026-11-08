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
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
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

function gzipHead(path) {
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

/** 当前已完成多少轮转换 */
async function runCount() {
  return page.evaluate(() => Number(document.documentElement.dataset.run || 0));
}

/** 等下一轮转换结束（比轮询按钮状态可靠：自动刷新也会计入轮次） */
async function waitRun(previous, timeout = 30000) {
  await page.waitForFunction(
    (prev) => Number(document.documentElement.dataset.run || 0) > prev,
    previous,
    { timeout }
  );
  await page.waitForSelector('#download-file:not([disabled])', { timeout: 10000 });
}

/** 读取预览画布的位图尺寸与显示尺寸 */
function readPreview() {
  return page.evaluate(() => {
    const canvas = document.querySelector('#preview-item canvas');
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const ctx = canvas.getContext('2d');
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let opaque = 0;
    for (let i = 3; i < data.length; i += 4) if (data[i] > 0) opaque++;
    const pixel = (x, y) => {
      const d = ctx.getImageData(x, y, 1, 1).data;
      return [d[0], d[1], d[2], d[3]];
    };
    return {
      width: canvas.width,
      height: canvas.height,
      cssWidth: Math.round(rect.width),
      cssHeight: Math.round(rect.height),
      opaque,
      topLeft: pixel(1, 1),
      bottomLeft: pixel(1, canvas.height - 2)
    };
  });
}

try {
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle' });

  /* ---------- 1. 文字像素画 ---------- */
  await page.click('#mode-text');
  let mark = await runCount();
  await page.fill('#text-input', 'Sun\n像素');
  await page.fill('#width-input', '64');
  await waitRun(mark);
  await page.waitForSelector('#result-card', { timeout: 20000 });

  const textStats = await page.textContent('.stat-card .stat-value');
  assert.match(textStats, /\d+\s*×\s*\d+/, '文字模式未产出尺寸');

  const textPreview = await readPreview();
  assert.ok(textPreview, '缺少预览画布');
  assert.equal(textPreview.width, 64, '预览画布宽度应等于方块宽度');
  assert.ok(textPreview.cssWidth > 100, `预览显示宽度过小：${textPreview.cssWidth}`);
  assert.ok(textPreview.opaque > 0, '预览画布是空的');

  const schemPath = await saveDownload(() => page.click('#download-file'), 'text.schem');
  assert.ok(gzipHead(schemPath), '下载的 .schem 不是 gzip');
  results.push(['文字模式 .schem', `${schemPath} (${readFileSync(schemPath).length} B)`]);

  /* ---------- 2. 图片像素画：上传后应自动出预览 ---------- */
  const fixture = makeFixture();
  await page.click('#mode-image');
  mark = await runCount();
  await page.setInputFiles('#file-input', fixture);
  await waitRun(mark);
  await page.waitForSelector('.hint:has-text("当前图片")', { timeout: 10000 });

  const imagePreview = await readPreview();
  const currentWidth = Number(await page.inputValue('#width-input'));
  assert.equal(imagePreview.width, currentWidth, '预览画布宽度应跟随宽度设置');
  assert.ok(imagePreview.cssWidth >= 200, '预览图没有放大到可读尺寸');
  // 样例图上半红、下半蓝，预览顶部应偏红、底部偏蓝
  assert.ok(imagePreview.topLeft[0] > imagePreview.topLeft[2], '预览上方应为红色系');
  assert.ok(imagePreview.bottomLeft[2] > imagePreview.bottomLeft[0], '预览下方应为蓝色系');
  results.push(['图片模式预览', `${imagePreview.width}×${imagePreview.height} 位图，显示 ${imagePreview.cssWidth}px`]);

  /* ---------- 3. 竖立摆放时预览不能上下颠倒 ---------- */
  mark = await runCount();
  await page.selectOption('#plane-select', 'xy');
  await waitRun(mark);
  const wallPreview = await readPreview();
  assert.ok(wallPreview.topLeft[0] > wallPreview.topLeft[2], '竖立时预览上方仍应是红色系');
  assert.ok(wallPreview.bottomLeft[2] > wallPreview.bottomLeft[0], '竖立时预览下方仍应是蓝色系');
  results.push(['竖立预览方向', '上红下蓝，未翻转']);
  mark = await runCount();
  await page.selectOption('#plane-select', 'xz');
  await waitRun(mark);

  /* ---------- 4. 切换格式并下载 litematic ---------- */
  await page.selectOption('#format-select', 'litematic');
  mark = await runCount();
  await page.click('#convert-btn');
  await waitRun(mark);
  const litematicPath = await saveDownload(() => page.click('#download-file'), 'image.litematic');
  assert.ok(gzipHead(litematicPath), '下载的 .litematic 不是 gzip');
  results.push(['图片模式 .litematic', `${litematicPath} (${readFileSync(litematicPath).length} B)`]);

  /* ---------- 5. mcstructure 必须是小端未压缩 NBT ---------- */
  await page.selectOption('#format-select', 'mcstructure');
  mark = await runCount();
  await page.click('#convert-btn');
  await waitRun(mark);
  const mcPath = await saveDownload(() => page.click('#download-file'), 'image.mcstructure');
  const mcRaw = readFileSync(mcPath);
  assert.ok(!(mcRaw[0] === 0x1f && mcRaw[1] === 0x8b), '.mcstructure 不应被 gzip 压缩');
  assert.equal(mcRaw[0], 10, '.mcstructure 应以 TAG_Compound 开头');
  results.push(['基岩版 .mcstructure', `${mcPath} (${mcRaw.length} B，未压缩)`]);

  /* ---------- 6. 图纸与材料表 ---------- */
  const blueprintPath = await saveDownload(() => page.click('#download-blueprint'), 'build.md');
  const blueprint = readFileSync(blueprintPath, 'utf8');
  assert.match(blueprint, /## 图例/, '图纸缺少图例');
  assert.match(blueprint, /## 逐行图纸/, '图纸缺少逐行内容');
  results.push(['搭建图纸', `${blueprintPath} (${blueprint.split('\n').length} 行)`]);

  const csvPath = await saveDownload(() => page.click('#download-csv'), 'materials.csv');
  const csvLines = readFileSync(csvPath, 'utf8').trim().split('\n');
  assert.equal(csvLines[0], 'x,y,z,block');
  results.push(['材料清单', `${csvPath} (${csvLines.length - 1} 行数据)`]);

  /* ---------- 7. 强化地图画：应生成多层结构 ---------- */
  await page.selectOption('#format-select', 'schem');
  mark = await runCount();
  await page.check('#mapart-toggle');
  await waitRun(mark);

  assert.ok(
    (await page.locator('.stat-card:has-text("层数")').count()) > 0,
    '地图画应显示层数统计'
  );
  const mapCaption = await page.locator('#preview-item figcaption').textContent();
  assert.match(mapCaption, /地图配色/, '地图画预览应提示按地图配色显示');

  const mapPath = await saveDownload(() => page.click('#download-file'), 'map.schem');
  const mapDir = mkdtempSync(join(tmpdir(), 'sunpixel-map-'));
  writeFileSync(join(mapDir, 'sample.schem'), readFileSync(mapPath));
  const mapReport = JSON.parse(
    execFileSync('python3', [join(here, 'validate_nbt.py'), mapDir], { encoding: 'utf8' })
  );
  assert.ok(!mapReport.schem.error, mapReport.schem.error);
  assert.ok(mapReport.schem.height > 1, `地图画应有高度差，实际 ${mapReport.schem.height}`);
  results.push(['强化地图画', `${mapReport.schem.width}×${mapReport.schem.height}×${mapReport.schem.length}`]);

  mark = await runCount();
  await page.uncheck('#mapart-toggle');
  await waitRun(mark);

  /* ---------- 8. 图片调节应改变效果图 ---------- */
  const beforeAdjust = await readPreview();
  mark = await runCount();
  await page.evaluate(() => {
    const input = document.querySelector('#brightness');
    input.value = '70';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await waitRun(mark);
  const afterAdjust = await readPreview();
  assert.notDeepEqual(afterAdjust.topLeft, beforeAdjust.topLeft, '调亮度后效果图应变化');
  results.push(['图片调节', `亮度 +70 后左上角 ${afterAdjust.topLeft.join(',')}`]);

  mark = await runCount();
  await page.evaluate(() => {
    const input = document.querySelector('#brightness');
    input.value = '0';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await waitRun(mark);

  /* ---------- 9. 文字：字形拉伸与逐字导出 ---------- */
  await page.click('#mode-text');
  mark = await runCount();
  await page.fill('#text-input', 'AB');
  await waitRun(mark);

  mark = await runCount();
  await page.evaluate(() => {
    const input = document.querySelector('#scale-x');
    input.value = '140';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await waitRun(mark);

  const zipPath = await saveDownload(() => page.click('#download-chars'), 'chars.zip');
  const zipNames = JSON.parse(
    execFileSync(
      'python3',
      ['-c', 'import json,sys,zipfile; print(json.dumps(zipfile.ZipFile(sys.argv[1]).namelist()))', zipPath],
      { encoding: 'utf8' }
    )
  );
  assert.deepEqual(zipNames.sort(), ['A.schem', 'B.schem'], '逐字导出内容不对');
  results.push(['逐字导出', `${zipPath}（${zipNames.join('、')}）`]);

  const cardText = await page.textContent('#result-card');
  assert.ok(!/undefined|NaN/.test(cardText), '结果区出现 undefined / NaN');

  await page.screenshot({ path: join(downloadDir, 'screenshot.png'), fullPage: true });
  results.push(['页面截图', join(downloadDir, 'screenshot.png')]);

  /* ---------- 7. 用独立实现校验下载的投影 ---------- */
  const validateDir = mkdtempSync(join(tmpdir(), 'sunpixel-validate-'));
  writeFileSync(join(validateDir, 'sample.schem'), readFileSync(schemPath));
  writeFileSync(join(validateDir, 'sample.litematic'), readFileSync(litematicPath));
  writeFileSync(join(validateDir, 'sample.mcstructure'), readFileSync(mcPath));
  const report = JSON.parse(
    execFileSync('python3', [join(here, 'validate_nbt.py'), validateDir], { encoding: 'utf8' })
  );
  assert.ok(!report.schem.error, report.schem.error);
  assert.ok(!report.litematic.error, report.litematic.error);
  assert.ok(!report.mcstructure.error, report.mcstructure.error);
  assert.ok(report.schem.blocks.length > 0, 'schem 没有方块');
  assert.ok(report.litematic.states.some((v) => v > 0), 'litematic 全是空气/索引 0');
  assert.equal(report.mcstructure.size[0], currentWidth, 'mcstructure 宽度不对');
  results.push([
    'nbtlib 校验',
    `schem ${report.schem.width}×${report.schem.height}×${report.schem.length}，` +
    `litematic ${report.litematic.palette.length} 种方块，` +
    `mcstructure ${report.mcstructure.palette.length} 种方块`
  ]);

  assert.deepEqual(errors, [], `页面报错：${errors.join(' | ')}`);

  console.log('\n端到端验收通过：');
  for (const [name, detail] of results) console.log(`  ✓ ${name}: ${detail}`);
} finally {
  await browser.close();
  server.kill();
}
