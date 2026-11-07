import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { rgbToLab, parseColorKey, buildPalette, createMatcher } from '../js/core/color.js';
import { transformPixels, quantize, pixelate, voxelAt } from '../js/core/pixelate.js';
import { BLOCK_DATA } from '../js/block-data.js';

const here = dirname(fileURLToPath(import.meta.url));

/** 造一个纯色 RGBA 图 */
function solid(width, height, rgba) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    data[i * 4] = rgba[0];
    data[i * 4 + 1] = rgba[1];
    data[i * 4 + 2] = rgba[2];
    data[i * 4 + 3] = rgba[3];
  }
  return { width, height, data };
}

test('Lab 转换：白色 L≈100，黑色 L≈0', () => {
  const white = rgbToLab(255, 255, 255);
  const black = rgbToLab(0, 0, 0);
  assert.ok(Math.abs(white[0] - 100) < 0.2, `white L=${white[0]}`);
  assert.ok(Math.abs(black[0]) < 0.01, `black L=${black[0]}`);
});

test('颜色键解析兼容括号与空格', () => {
  assert.deepEqual(parseColorKey('(20, 21, 25)'), [20, 21, 25]);
  assert.deepEqual(parseColorKey('233,236,239'), [233, 236, 239]);
  assert.equal(parseColorKey('bad'), null);
});

test('羊毛调色板包含黑色羊毛（修复前的回归用例）', () => {
  const palette = buildPalette(['wool'], BLOCK_DATA);
  const blocks = palette.entries.map((e) => e.block);
  assert.ok(blocks.includes('minecraft:black_wool'), '羊毛调色板缺少黑色羊毛');
  const whiteCount = blocks.filter((b) => b === 'minecraft:white_wool').length;
  assert.equal(whiteCount, 1, '白色羊毛被重复映射');
});

test('纯黑像素匹配到黑色方块而不是白色', () => {
  const matcher = createMatcher(buildPalette(['wool'], BLOCK_DATA), 'lab');
  const index = matcher.nearest(0, 0, 0);
  assert.equal(matcher.entries[index].block, 'minecraft:black_wool');
});

test('调色板按方块去重，不会重复计算同一方块', () => {
  const palette = buildPalette(['wool', 'concrete'], BLOCK_DATA);
  const keys = palette.entries.map((e) => e.block);
  assert.equal(new Set(keys).size, keys.length);
});

test('完全透明像素变成空气', () => {
  const matcher = createMatcher(buildPalette(['wool'], BLOCK_DATA), 'lab');
  const image = solid(2, 2, [255, 255, 255, 0]);
  const result = pixelate(image, matcher, { plane: 'xz' });
  assert.equal(result.totalBlocks, 0);
  assert.equal(result.airCount, 4);
  assert.equal(result.palette[0], 'minecraft:air');
});

test('竖立摆放：图片首行落在 Y 最高层，不会上下颠倒', () => {
  const matcher = createMatcher(buildPalette(['wool'], BLOCK_DATA), 'lab');
  const image = solid(1, 2, [255, 255, 255, 255]);
  // 第 0 行涂红，第 1 行涂白
  image.data.set([200, 30, 30, 255], 0);
  image.data.set([240, 240, 240, 255], 4);

  const result = pixelate(image, matcher, { plane: 'xy' });
  assert.equal(result.size.x, 1);
  assert.equal(result.size.y, 2);
  assert.equal(result.size.z, 1);

  const top = voxelAt(result, 0, 1, 0);
  const bottom = voxelAt(result, 0, 0, 0);
  assert.equal(result.palette[top], 'minecraft:red_wool');
  assert.equal(result.palette[bottom], 'minecraft:white_wool');
});

test('平铺摆放：图片首行在 Z=0', () => {
  const matcher = createMatcher(buildPalette(['wool'], BLOCK_DATA), 'lab');
  const image = solid(1, 3, [255, 255, 255, 255]);
  image.data.set([200, 30, 30, 255], 0);
  const result = pixelate(image, matcher, { plane: 'xz' });
  assert.deepEqual(result.size, { x: 1, y: 1, z: 3 });
  assert.equal(result.palette[voxelAt(result, 0, 0, 0)], 'minecraft:red_wool');
});

test('旋转 90° 会交换宽高并顺时针搬运像素', () => {
  const data = new Uint8ClampedArray(2 * 1 * 4);
  data.set([255, 0, 0, 255], 0);   // (0,0) 红
  data.set([0, 0, 255, 255], 4);   // (1,0) 蓝
  const out = transformPixels({ width: 2, height: 1, data }, { rotate: 90 });
  assert.equal(out.width, 1);
  assert.equal(out.height, 2);
  // 顺时针旋转后，横向条变成纵向条：左端（红）在上，右端（蓝）在下
  assert.deepEqual([...out.data.slice(0, 3)], [255, 0, 0]);
  assert.deepEqual([...out.data.slice(4, 7)], [0, 0, 255]);
});

test('水平镜像会左右翻转', () => {
  const image = solid(2, 1, [255, 255, 255, 255]);
  image.data.set([10, 20, 30, 255], 0);
  image.data.set([200, 210, 220, 255], 4);
  const out = transformPixels(image, { mirrorX: true });
  assert.deepEqual([...out.data.slice(0, 3)], [200, 210, 220]);
  assert.deepEqual([...out.data.slice(4, 7)], [10, 20, 30]);
});

test('抖动：黑白棋盘在只有黑白两色时误差不大于直接量化', () => {
  const matcher = createMatcher(buildPalette(['concrete'], BLOCK_DATA), 'lab');
  // 中灰，直接量化只能整体变成浅灰或深灰
  const image = solid(8, 8, [128, 128, 128, 255]);
  const plain = quantize(image, matcher, { dither: 'none' });
  const dithered = quantize(solid(8, 8, [128, 128, 128, 255]), matcher, { dither: 'floyd' });
  const distinctPlain = new Set(plain).size;
  const distinctDithered = new Set(dithered).size;
  assert.equal(distinctPlain, 1, '未开抖动时纯色图应只有一种方块');
  assert.ok(distinctDithered >= 2, '抖动后应混合出多种方块');
});

test('方块统计与空气计数一致', () => {
  const matcher = createMatcher(buildPalette(['wool'], BLOCK_DATA), 'lab');
  const image = solid(2, 2, [255, 255, 255, 255]);
  image.data.set([255, 255, 255, 0], 0); // 左上角透明
  const result = pixelate(image, matcher, { plane: 'xz' });
  assert.equal(result.airCount, 1);
  assert.equal(result.totalBlocks, 3);
  assert.equal([...result.counts.values()].reduce((a, b) => a + b, 0), 3);
});
