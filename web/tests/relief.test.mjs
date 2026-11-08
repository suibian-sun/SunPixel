import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

import { pixelateRelief, applyCurve, MAX_VOLUME } from '../js/core/relief.js';
import { buildPalette, createMatcher } from '../js/core/color.js';
import { BLOCK_DATA } from '../js/block-data.js';
import { generateOutput } from '../js/formatter.js';

/** 造一张灰度图：fn(x,z) 返回 0-255 的亮度 */
function grayImage(width, height, fn, alpha = 255) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let z = 0; z < height; z++) {
    for (let x = 0; x < width; x++) {
      const v = fn(x, z);
      data.set([v, v, v, alpha], (z * width + x) * 4);
    }
  }
  return { width, height, data };
}

const matcher = createMatcher(buildPalette(['wool'], BLOCK_DATA), 'lab');

/** 取某列最高的非空气方块的 Y，没有方块返回 -1 */
function topOf(result, x, z) {
  for (let y = result.size.y - 1; y >= 0; y--) {
    if (result.volume[(y * result.size.z + z) * result.size.x + x] !== 0) return y;
  }
  return -1;
}

test('立体：越亮越高，尺寸按 宽 × 高度上限 × 深 输出', () => {
  // 左黑右白，左右各两列
  const image = grayImage(4, 2, (x) => (x < 2 ? 0 : 255));
  const result = pixelateRelief(image, matcher, { minHeight: 1, maxHeight: 9 });

  assert.equal(result.relief, true);
  assert.deepEqual(result.size, { x: 4, y: 9, z: 2 });
  assert.equal(result.layers, 9);

  const dark = topOf(result, 0, 0) + 1; // 高度 = 最高下标 + 1
  const light = topOf(result, 3, 1) + 1;
  assert.equal(dark, 1, '纯黑应压到最低高度');
  assert.equal(light, 9, '纯白应升到最高高度');
});

test('立体：表面厚度与填充方块', () => {
  const image = grayImage(2, 2, () => 255);
  const solid = pixelateRelief(image, matcher, { maxHeight: 6, shellThickness: 1, fillBlock: 'minecraft:stone' });

  // 每列 6 格，其中 1 格是表层，5 格是石头
  assert.equal(solid.counts.get('minecraft:stone'), 4 * 5);
  assert.equal(solid.totalBlocks, 4 * 6);
  assert.ok(!solid.counts.has('minecraft:air'));

  const thick = pixelateRelief(image, matcher, { maxHeight: 6, shellThickness: 3 });
  assert.equal(thick.counts.get('minecraft:stone'), 4 * 3, '表层厚度 3 时石头只剩下面 3 层');
});

test('立体：空心模式只保留表层', () => {
  const image = grayImage(2, 2, () => 255);
  const hollow = pixelateRelief(image, matcher, { maxHeight: 6, shellThickness: 2, hollow: true });

  assert.equal(hollow.totalBlocks, 4 * 2, '空心只留 2 层表层');
  assert.ok(!hollow.counts.has('minecraft:stone'), '空心不应出现填充方块');
  assert.equal(hollow.palette.includes('minecraft:stone'), false);
});

test('立体：透明像素不生成柱子', () => {
  const image = grayImage(3, 1, () => 200);
  image.data.set([0, 0, 0, 0], 4); // 第二格透明
  const result = pixelateRelief(image, matcher, { maxHeight: 4 });

  assert.equal(topOf(result, 1, 0), -1);
  assert.ok(result.airCount > 0);
  assert.equal(result.totalBlocks, (topOf(result, 0, 0) + 1) + (topOf(result, 2, 0) + 1));
});

test('立体：反转高度与曲线会改变柱高', () => {
  const image = grayImage(1, 1, () => 40);

  const normal = pixelateRelief(image, matcher, { minHeight: 1, maxHeight: 11 });
  const inverted = pixelateRelief(image, matcher, { minHeight: 1, maxHeight: 11, invert: true });
  assert.ok(topOf(inverted, 0, 0) > topOf(normal, 0, 0), '反转后暗部应更高');

  const linear = pixelateRelief(image, matcher, { minHeight: 1, maxHeight: 11, curve: 'linear' });
  const sqrt = pixelateRelief(image, matcher, { minHeight: 1, maxHeight: 11, curve: 'sqrt' });
  const square = pixelateRelief(image, matcher, { minHeight: 1, maxHeight: 11, curve: 'square' });
  assert.ok(topOf(sqrt, 0, 0) >= topOf(linear, 0, 0), 'sqrt 应抬高低处');
  assert.ok(topOf(square, 0, 0) <= topOf(linear, 0, 0), 'square 应压低低处');

  assert.ok(Math.abs(applyCurve(0.25, 'sqrt') - 0.5) < 1e-9);
  assert.equal(applyCurve(0.5, 'square'), 0.25);
  assert.equal(applyCurve(0.5, 'linear'), 0.5);
});

test('立体：高度上下限会被修正，体积超限直接报错', () => {
  const image = grayImage(2, 2, () => 128);
  const fixed = pixelateRelief(image, matcher, { minHeight: 8, maxHeight: 2 });
  assert.equal(fixed.size.y, 8, '最高高度低于最低高度时应抬到最低高度');

  // 200 × 200 × 128 = 512 万，仍在限内；再大就该拒绝
  const big = grayImage(200, 200, () => 128);
  assert.doesNotThrow(() => pixelateRelief(big, matcher, { maxHeight: 128 }));
  const tooBig = grayImage(400, 400, () => 128);
  assert.throws(
    () => pixelateRelief(tooBig, matcher, { maxHeight: 128 }),
    /体积|上限/
  );
  assert.ok(MAX_VOLUME <= 8_000_000);
});

test('立体结构能被三种 NBT 格式正确写出', async () => {
  const image = grayImage(5, 4, (x, z) => ((x * 37 + z * 91) % 256));
  const result = pixelateRelief(image, matcher, { minHeight: 1, maxHeight: 6, shellThickness: 2 });

  const directory = mkdtempSync(join(tmpdir(), 'sunpixel-relief-'));
  for (const format of ['schem', 'litematic', 'mcstructure', 'nbt']) {
    const output = await generateOutput(result, format, 'sample');
    writeFileSync(join(directory, output.filename), Buffer.from(await output.blob.arrayBuffer()));
  }

  const report = JSON.parse(
    execFileSync('python3', [new URL('./validate_nbt.py', import.meta.url).pathname, directory], { encoding: 'utf8' })
  );

  assert.ok(!report.schem.error, report.schem.error);
  assert.deepEqual(
    [report.schem.width, report.schem.height, report.schem.length],
    [result.size.x, result.size.y, result.size.z]
  );
  assert.deepEqual(report.schem.blocks, Array.from(result.volume));

  assert.ok(!report.litematic.error, report.litematic.error);
  assert.deepEqual(report.litematic.states, Array.from(result.volume));

  assert.ok(!report.mcstructure.error, report.mcstructure.error);
  assert.deepEqual(report.mcstructure.size, [result.size.x, result.size.y, result.size.z]);

  assert.ok(!report.nbt.error, report.nbt.error);
  assert.deepEqual(report.nbt.states, Array.from(result.volume));
  assert.equal(report.nbt.blockCount, result.totalBlocks);
});
