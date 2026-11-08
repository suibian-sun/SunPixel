/**
 * 强化地图画：用「柱子的高度差」换取额外色阶
 *
 * Minecraft 的地图在渲染某一格时，会把该格方块的颜色按它与北侧方块的
 * 高度差调亮或调暗：高一格偏亮、低一格偏暗、同高保持原色。于是同一种
 * 方块在地图上就能呈现三档颜色，16 色方块因此变成 48 档。
 *
 * 做法：
 *  1. 每个像素在「方块 × 三档明暗」里找最接近的颜色（CIE Lab）
 *  2. 沿 Z 轴（地图的南北向）累积高度，使相邻柱子的高度差等于所选明暗
 *  3. 每列只放一格方块，材料量与平面像素画相同，只是高度不同
 *
 * 思路参考 TgkRuobin/vue3-mcpixelart 的强化地图画，
 * 但高度累积改以「像素自身的明暗」为准（原实现把明暗错位给了南侧像素）。
 */

import { rgbToLab } from './color.js';
import { MAP_BLOCK_DATA } from '../data/map-colors.js';
import { AIR } from './pixelate.js';

const SHADE_NORMAL = 0;
const SHADE_LOW = 1;
const SHADE_HIGH = 2;

/** 地图最多用几层高低差，避免渐变区域把结构堆成塔 */
const DEFAULT_LAYERS = 8;

/** 单次生成的地图画上限（宽 × 高），超过后地图拼接成本过高 */
const MAX_MAP_WIDTH = 384;
const MAX_MAP_HEIGHT = 256;

/**
 * 构建地图画调色板
 * @param {string[]} types 方块类型（wool / concrete / terracotta…），空则全部
 */
function buildMapPalette(types = []) {
  const wanted = new Set(types);
  const entries = [];

  const push = (block, info) => {
    for (let shade = SHADE_NORMAL; shade <= SHADE_HIGH; shade++) {
      const rgb = info.shades[shade];
      entries.push({
        block: `minecraft:${block}`,
        type: info.type,
        name: info.name,
        shade,
        rgb,
        lab: rgbToLab(rgb[0], rgb[1], rgb[2])
      });
    }
  };

  for (const [block, info] of Object.entries(MAP_BLOCK_DATA)) {
    if (!wanted.size || wanted.has(info.type)) push(block, info);
  }

  // 所选类型没有地图色（例如只选了木板）时，退回全部地图色方块
  if (!entries.length) {
    for (const [block, info] of Object.entries(MAP_BLOCK_DATA)) push(block, info);
  }

  return entries;
}

/**
 * 每像素匹配「方块 + 明暗档位」
 *
 * 不能直接在「方块 × 三档」里取全局最近色：那样纯色区域会一路选偏亮档，
 * 柱子就会不停升高。这里改成两步：
 *   1. 三档各自找最接近的方块（候选）
 *   2. 只有目标像素比北侧像素明显更亮/更暗时，才允许用亮档/暗档
 * 于是纯色区保持同高，明暗交界处才出现高度差。
 *
 * @returns {Int16Array} entries 下标，-1 表示空气
 */
function quantizeMap(imageData, entries, options = {}) {
  const { width, height, data } = imageData;
  const threshold = options.alphaThreshold === undefined ? 128 : options.alphaThreshold;
  const lumaThreshold = options.lumaThreshold === undefined ? 4 : options.lumaThreshold;
  const total = width * height;

  // 按档位分组，避免每个像素都遍历整个色板
  const byShade = [[], [], []];
  entries.forEach((entry, index) => byShade[entry.shade].push(index));

  const candidate = new Int16Array(total * 3).fill(-1);
  const luma = new Float32Array(total);
  const cache = new Map();

  for (let i = 0; i < total; i++) {
    const p = i * 4;
    if (data[p + 3] < threshold) continue;

    const r = data[p];
    const g = data[p + 1];
    const b = data[p + 2];
    luma[i] = 0.2126 * r + 0.7152 * g + 0.0722 * b;

    const key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3);
    const hit = cache.get(key);
    if (hit) {
      candidate[i * 3] = hit[0];
      candidate[i * 3 + 1] = hit[1];
      candidate[i * 3 + 2] = hit[2];
      continue;
    }

    const lab = rgbToLab(r, g, b);
    const chosen = [-1, -1, -1];
    for (let shade = 0; shade < 3; shade++) {
      let best = -1;
      let bestDistance = Infinity;
      for (const index of byShade[shade]) {
        const target = entries[index].lab;
        const dl = lab[0] - target[0];
        const da = lab[1] - target[1];
        const db = lab[2] - target[2];
        const d = dl * dl + da * da + db * db;
        if (d < bestDistance) {
          bestDistance = d;
          best = index;
        }
      }
      chosen[shade] = best;
    }
    cache.set(key, chosen);
    candidate[i * 3] = chosen[0];
    candidate[i * 3 + 1] = chosen[1];
    candidate[i * 3 + 2] = chosen[2];
  }

  const entryOf = new Int16Array(total).fill(-1);

  for (let z = 0; z < height; z++) {
    for (let x = 0; x < width; x++) {
      const i = z * width + x;
      if (candidate[i * 3] < 0) continue;

      let shade = SHADE_NORMAL;
      if (z > 0) {
        const previous = i - width;
        // 北侧是空气时没有比较对象，保持原色
        if (candidate[previous * 3] >= 0) {
          const delta = luma[i] - luma[previous];
          if (delta > lumaThreshold) shade = SHADE_HIGH;
          else if (delta < -lumaThreshold) shade = SHADE_LOW;
        }
      }

      const picked = candidate[i * 3 + shade];
      entryOf[i] = picked >= 0 ? picked : candidate[i * 3];
    }
  }

  return entryOf;
}

/**
 * 沿 Z 累积每列高度
 * @returns {{depth: Int16Array, layers: number}}
 */
function computeDepths(entryOf, entries, width, height, maxLayers = DEFAULT_LAYERS) {
  const depth = new Int16Array(width * height);
  const spans = new Int16Array(width);
  const layers = Math.max(1, Math.round(maxLayers));
  // 高低两侧平分额度，保证整列总高度不超过 layers
  const lower = -Math.floor((layers - 1) / 2);
  const upper = Math.ceil((layers - 1) / 2);

  for (let x = 0; x < width; x++) {
    let pos = 0;
    let low = 0;
    let high = 0;

    for (let z = 0; z < height; z++) {
      const i = z * width + x;
      const entry = entryOf[i];

      // 第 0 行是整列的基准；其余像素按自身明暗决定与北侧邻居的高度差
      if (z > 0 && entry >= 0) {
        const shade = entries[entry].shade;
        if (shade === SHADE_HIGH) pos = Math.min(upper, pos + 1);
        else if (shade === SHADE_LOW) pos = Math.max(lower, pos - 1);
      }

      depth[i] = pos;
      if (pos < low) low = pos;
      if (pos > high) high = pos;
    }

    // 整列下移，最低一格为 Y=0
    if (low !== 0) {
      for (let z = 0; z < height; z++) depth[z * width + x] -= low;
    }
    spans[x] = high - low;
  }

  let totalLayers = 1;
  for (let x = 0; x < width; x++) totalLayers = Math.max(totalLayers, spans[x] + 1);

  return { depth, layers: totalLayers };
}

/**
 * 生成地图画
 * @param {{width:number,height:number,data:Uint8ClampedArray}} imageData
 * @param {object} options { types, alphaThreshold, mapLayers }
 */
function pixelateMap(imageData, options = {}) {
  const width = Math.max(1, Math.round(imageData.width));
  const height = Math.max(1, Math.round(imageData.height));
  // 旋转 / 镜像在进入本函数前已经做过，这里按最终尺寸校验
  if (width > MAX_MAP_WIDTH || height > MAX_MAP_HEIGHT) {
    throw new Error(`强化地图画最大 ${MAX_MAP_WIDTH} × ${MAX_MAP_HEIGHT}，当前为 ${width} × ${height}`);
  }
  const entries = buildMapPalette(options.types || []);
  const entryOf = quantizeMap({ ...imageData, width, height }, entries, options);
  const { depth, layers } = computeDepths(
    entryOf,
    entries,
    width,
    height,
    options.mapLayers || DEFAULT_LAYERS
  );

  const size = { x: width, y: layers, z: height };
  const palette = [AIR];
  const indexOfBlock = new Map();
  const volume = new Int32Array(width * layers * height);
  const grid = new Int32Array(width * height);
  const counts = new Map();
  const preview = new Uint8ClampedArray(width * height * 4);

  let totalBlocks = 0;

  for (let z = 0; z < height; z++) {
    for (let x = 0; x < width; x++) {
      const i = z * width + x;
      const entry = entryOf[i];

      if (entry < 0) {
        grid[i] = 0;
        continue;
      }

      const { block, rgb } = entries[entry];
      let index = indexOfBlock.get(block);
      if (index === undefined) {
        index = palette.length;
        palette.push(block);
        indexOfBlock.set(block, index);
      }

      const y = depth[i];
      volume[(y * height + z) * width + x] = index;
      grid[i] = index;
      counts.set(block, (counts.get(block) || 0) + 1);
      totalBlocks += 1;

      const p = i * 4;
      preview[p] = rgb[0];
      preview[p + 1] = rgb[1];
      preview[p + 2] = rgb[2];
      preview[p + 3] = 255;
    }
  }

  const totalPixels = width * height;

  return {
    width,
    height,
    plane: 'xz',
    mapArt: true,
    size,
    palette,
    airIndex: 0,
    volume,
    grid,
    counts,
    airCount: totalPixels - totalBlocks,
    totalBlocks,
    totalVolume: totalPixels,
    layers,
    // 地图画的效果图要按明暗档位上色，才能在网页上看出「地图里的样子」
    previewPixels: { width, height, data: preview }
  };
}

export {
  SHADE_NORMAL,
  SHADE_LOW,
  SHADE_HIGH,
  DEFAULT_LAYERS,
  MAX_MAP_WIDTH,
  MAX_MAP_HEIGHT,
  buildMapPalette,
  quantizeMap,
  computeDepths,
  pixelateMap
};
