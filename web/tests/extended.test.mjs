import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

import { pixelateMap, buildMapPalette, computeDepths, MAX_MAP_WIDTH } from '../js/core/mapart.js';
import { adjustPixels } from '../js/core/adjust.js';
import { limitPalette } from '../js/core/palette-limit.js';
import { buildPalette } from '../js/core/color.js';
import { createZip, crc32 } from '../js/core/zip.js';
import { BLOCK_DATA } from '../js/block-data.js';
import { generateOutput } from '../js/formatter.js';
import { processPixels } from '../js/converter.js';

/** 造一张图：fn(x,z) 返回 [r,g,b,a] */
function makeImage(width, height, fn) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let z = 0; z < height; z++) {
    for (let x = 0; x < width; x++) {
      data.set(fn(x, z), (z * width + x) * 4);
    }
  }
  return { width, height, data };
}

function runValidator(directory) {
  const script = new URL('./validate_nbt.py', import.meta.url).pathname;
  const out = execFileSync('python3', [script, directory], { encoding: 'utf8' });
  return JSON.parse(out);
}

test('地图画：纯色图只有一层，材料数与像素数一致', () => {
  const image = makeImage(4, 3, () => [230, 230, 230, 255]);
  const result = pixelateMap(image, { types: ['wool'] });

  assert.equal(result.mapArt, true, '应标记为地图画');
  assert.equal(result.size.x, 4);
  assert.equal(result.size.z, 3);
  assert.equal(result.size.y, 1, '没有任何明暗起伏时应只有 1 层');
  assert.equal(result.totalBlocks, 12);
  assert.equal(result.palette[0], 'minecraft:air');

  // 每列都放在 Y=0
  for (let z = 0; z < 3; z++) {
    for (let x = 0; x < 4; x++) {
      assert.notEqual(result.volume[(0 * 3 + z) * 4 + x], 0);
    }
  }
});

test('地图画：相邻柱高差不超过 1，层数受上限约束', () => {
  // 上黑下白，中间有渐变，制造明显的明暗变化
  const image = makeImage(6, 12, (x, z) => {
    const v = Math.round((z / 11) * 255);
    return [v, v, v, 255];
  });
  const result = pixelateMap(image, { types: ['wool'], mapLayers: 4 });

  assert.ok(result.size.y > 1, '渐变应产生高度差');
  assert.ok(result.size.y <= 4, `层数应受上限约束，实际 ${result.size.y}`);

  for (let x = 0; x < result.size.x; x++) {
    const heights = [];
    for (let z = 0; z < result.size.z; z++) {
      let y = -1;
      for (let layer = 0; layer < result.size.y; layer++) {
        if (result.volume[(layer * result.size.z + z) * result.size.x + x] !== 0) y = layer;
      }
      heights.push(y);
    }
    for (let z = 1; z < heights.length; z++) {
      const delta = Math.abs(heights[z] - heights[z - 1]);
      assert.ok(delta <= 1, `第 ${x} 列 z=${z} 的高度跳了 ${delta} 格，地图会显示错误颜色`);
    }
  }
});

test('地图画：透明像素输出空气，不占材料', () => {
  const image = makeImage(4, 4, (x, z) => (x === z ? [0, 0, 0, 0] : [200, 30, 30, 255]));
  const result = pixelateMap(image, { types: ['wool'], alphaThreshold: 128 });

  assert.equal(result.totalBlocks, 12);
  assert.equal(result.airCount, 4);
  for (let i = 0; i < 16; i++) {
    if (i % 5 === 0) assert.equal(result.grid[i], 0);
    else assert.notEqual(result.grid[i], 0);
  }
});

test('地图画：只使用所选类型里支持地图色的方块', () => {
  const image = makeImage(2, 2, () => [200, 30, 30, 255]);
  const result = pixelateMap(image, { types: ['wool'] });
  for (const name of result.palette.slice(1)) {
    assert.match(name, /_wool$/, `不应出现非羊毛方块：${name}`);
  }

  // 选了没有地图色的类型时退回全部地图色，而不是报错
  const fallback = pixelateMap(image, { types: ['planks'] });
  assert.ok(fallback.palette.length > 1, '应退回全量地图色板');
});

test('地图画：computeDepths 以像素自身明暗为准', () => {
  const entries = [
    { block: 'a', shade: 0 },
    { block: 'b', shade: 1 },
    { block: 'c', shade: 2 }
  ];
  // 一列：normal / high / high / low，第一格是基准，之后每格与北侧差 ±1
  const width = 1;
  const height = 4;
  const entryOf = Int16Array.from([0, 2, 2, 1]);
  const { depth, layers } = computeDepths(entryOf, entries, width, height, 8);

  assert.deepEqual(Array.from(depth), [0, 1, 2, 1]);
  assert.equal(layers, 3);
});

test('地图画：旋转与镜像会真正作用到成品', () => {
  // 4 × 2：左半黑、右半白，长宽不同，旋转后尺寸应交换
  const image = makeImage(4, 2, (x) => (x < 2 ? [20, 21, 25, 255] : [233, 236, 239, 255]));

  const plain = processPixels(image, ['wool'], { mapArt: true });
  assert.deepEqual([plain.size.x, plain.size.z], [4, 2]);

  const rotated = processPixels(image, ['wool'], { mapArt: true, rotate: 90, mirrorX: true });
  assert.deepEqual([rotated.size.x, rotated.size.z], [2, 4], '旋转后宽高应交换');

  // 顺时针 90° 后左列变顶行，黑色应在最上面
  const blockAt = (result, x, z) => {
    for (let y = result.size.y - 1; y >= 0; y--) {
      const index = result.volume[(y * result.size.z + z) * result.size.x + x];
      if (index !== 0) return result.palette[index];
    }
    return null;
  };
  assert.match(blockAt(rotated, 0, 0), /black_wool/, '旋转后左列应变成顶行（黑）');
  assert.match(blockAt(rotated, 0, 3), /white_wool/, '旋转后右列应变成底行（白）');

  const mirrored = processPixels(image, ['wool'], { mapArt: true, mirrorX: true });
  assert.match(blockAt(mirrored, 0, 0), /white_wool/, '水平镜像后左侧应变白');
});

test('地图画：超过 384 × 256 会给出明确错误', () => {
  assert.equal(MAX_MAP_WIDTH, 384);
  const wide = makeImage(MAX_MAP_WIDTH + 1, 4, () => [200, 200, 200, 255]);
  assert.throws(() => pixelateMap(wide, { types: ['wool'] }), /384|256/);
});

test('立体图纸：每层单独出图例，超过 62 种方块也不出现 ?', async () => {
  const total = 70;
  const palette = ['minecraft:air'];
  for (let i = 1; i <= total; i++) palette.push(`minecraft:test_${i}`);

  const size = { x: 10, y: 2, z: 1 };
  const volume = new Int32Array(size.x * size.y * size.z);
  const counts = new Map();
  for (let x = 0; x < 10; x++) {
    volume[(0 * 1 + 0) * 10 + x] = x + 1;          // 第 0 层：1-10
    volume[(1 * 1 + 0) * 10 + x] = x + 31;         // 第 1 层：31-40
  }
  for (let i = 1; i <= total; i++) counts.set(palette[i], i <= 40 ? 1 : 0);

  const result = {
    width: 10,
    height: 1,
    plane: 'xz',
    size,
    palette,
    volume,
    counts,
    airIndex: 0,
    totalBlocks: 20,
    totalVolume: volume.length
  };

  const output = await generateOutput(result, 'blueprint', 'sample');
  const text = await output.blob.text();

  const blocks = [...text.matchAll(/```text\n([\s\S]*?)```/g)].map((match) => match[1]);
  assert.equal(blocks.length, 2, '两层应输出两张图');
  for (const block of blocks) {
    assert.ok(!block.includes('?'), '层内方块不到 62 种，不应出现 ?');
  }
  assert.equal((text.match(/图例：/g) || []).length, 2, '每层都应有自己的图例');
  assert.match(text, /A=test_1/, '每层图例都从 A 开始编号');
});

test('地图画导出的 litematic / schem / mcstructure 都能被独立解析', async () => {
  const image = makeImage(5, 7, (x, z) => {
    const v = Math.round(((x + z) / 11) * 255);
    return [v, 255 - v, 90, 255];
  });
  const result = await Promise.resolve(pixelateMap(image, { types: ['wool', 'concrete'], mapLayers: 4 }));

  const directory = mkdtempSync(join(tmpdir(), 'sunpixel-map-'));
  for (const format of ['schem', 'litematic', 'mcstructure']) {
    const output = await generateOutput(result, format, 'sample');
    writeFileSync(join(directory, output.filename), Buffer.from(await output.blob.arrayBuffer()));
  }

  const report = runValidator(directory);
  assert.ok(!report.schem.error, report.schem.error);
  assert.equal(report.schem.width, 5);
  assert.equal(report.schem.height, result.size.y);
  assert.equal(report.schem.length, 7);
  assert.ok(!report.litematic.error, report.litematic.error);
  assert.deepEqual(report.litematic.size, [5, result.size.y, 7]);
  assert.ok(!report.mcstructure.error, report.mcstructure.error);
  assert.deepEqual(report.mcstructure.size, [5, result.size.y, 7]);
});

test('图像调节：亮度、对比度、灰度、反色', () => {
  const base = { width: 2, height: 1, data: Uint8ClampedArray.from([100, 100, 100, 255, 200, 200, 200, 255]) };

  const bright = adjustPixels(base, { brightness: 20 });
  assert.ok(bright.data[0] > 100, '亮度应提升');
  assert.equal(bright.data[3], 255, 'alpha 不能被改动');

  const gray = adjustPixels({ width: 1, height: 1, data: Uint8ClampedArray.from([255, 0, 0, 255]) }, { grayscale: true });
  assert.equal(gray.data[0], gray.data[1]);
  assert.equal(gray.data[1], gray.data[2]);

  const inverted = adjustPixels({ width: 1, height: 1, data: Uint8ClampedArray.from([0, 40, 255, 255]) }, { invert: true });
  assert.deepEqual([...inverted.data.slice(0, 3)], [255, 215, 0]);

  // 参数全默认时应原样返回（但复制一份，避免改到原数组）
  const same = adjustPixels(base, {});
  assert.deepEqual([...same.data], [...base.data]);
  assert.notEqual(same.data, base.data);
});

test('图像调节：伽马两端不越界', () => {
  const extreme = { width: 1, height: 1, data: Uint8ClampedArray.from([0, 128, 255, 255]) };
  const darker = adjustPixels(extreme, { gamma: 2.2 });
  assert.equal(darker.data[0], 0);
  assert.ok(darker.data[2] <= 255);
  const brighter = adjustPixels(extreme, { gamma: 0.4 });
  assert.equal(brighter.data[2], 255);
});

test('备料优化：把调色板限制到指定方块种类', () => {
  const palette = buildPalette(['wool', 'concrete', 'terracotta', 'glass'], BLOCK_DATA);
  const unique = new Set(palette.entries.map((e) => e.block));
  assert.ok(unique.size > 24, '测试前提：原始调色板足够大');

  const limited = limitPalette(palette.entries, 12);
  const kept = new Set(limited.map((e) => e.block));
  assert.ok(kept.size <= 12, `应不超过 12 种，实际 ${kept.size}`);
  assert.ok(kept.size >= 8, `不应过度裁剪，实际 ${kept.size}`);

  // 结果必须仍是原调色板的子集
  for (const entry of limited) {
    assert.ok(unique.has(entry.block));
  }

  // 已经少于上限时原样返回
  const small = limitPalette(palette.entries.slice(0, 5), 8);
  assert.equal(small.length, Math.min(5, palette.entries.length));
});

test('ZIP：CRC32 与中央目录结构正确，可被系统 unzip 解开', async () => {
  const files = [
    { name: 'a.txt', data: new TextEncoder().encode('hello') },
    { name: '中文名字.txt', data: new TextEncoder().encode('像素画') }
  ];
  assert.equal(crc32(files[0].data), 0x3610a686, 'CRC32 应与标准值一致');

  const zip = createZip(files);
  const buffer = Buffer.from(await zip.arrayBuffer());
  assert.equal(buffer.readUInt32LE(0), 0x04034b50, '应以本地文件头开始');
  assert.equal(buffer.readUInt32LE(buffer.length - 22), 0x06054b50, '应以 EOCD 结束');
  assert.equal(buffer.readUInt16LE(buffer.length - 12), files.length, '条目数应正确');

  const directory = mkdtempSync(join(tmpdir(), 'sunpixel-zip-'));
  const path = join(directory, 'test.zip');
  writeFileSync(path, buffer);
  // unzip -l 在非 UTF-8 locale 下会把中文显示成乱码，改用 Python 的 zipfile 校验文件名
  const names = execFileSync(
    'python3',
    ['-c', 'import json,sys,zipfile; print(json.dumps(zipfile.ZipFile(sys.argv[1]).namelist()))', path],
    { encoding: 'utf8' }
  );
  assert.deepEqual(JSON.parse(names), ['a.txt', '中文名字.txt']);

  const content = execFileSync(
    'python3',
    ['-c', 'import sys,zipfile; print(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]).decode())', path, 'a.txt'],
    { encoding: 'utf8' }
  );
  assert.equal(content.trim(), 'hello');
});
