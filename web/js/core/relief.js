/**
 * 立体浮雕：把图片的明暗转成高度，生成真正的三维地形
 *
 * 和平面像素画不同，这里每一列不是一格方块，而是一根从地基长到目标高度的柱子：
 *  - 柱顶用图片该像素匹配到的方块，远看就是原图
 *  - 柱身用统一的填充方块（石头、泥土…），省材料也符合地形观感
 *  - 柱高由亮度决定，于是照片会变成山脊、沟谷与台地
 *
 * 只依赖纯数据，不碰 DOM，方便在 Node 里单测。
 */

import { AIR } from './pixelate.js';

/** 一次生成的最大方块体积，防止 512×512×128 把标签页撑爆 */
const MAX_VOLUME = 8_000_000;

const DEFAULT_OPTIONS = {
  minHeight: 1,
  maxHeight: 24,
  shellThickness: 1,
  hollow: false,
  fillBlock: 'minecraft:stone',
  curve: 'linear',
  invert: false
};

function clampInt(value, min, max, fallback) {
  const number = Math.round(Number(value));
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, number));
}

/** 高度曲线：linear 线性 / sqrt 抬高低处 / square 压低低处 */
function applyCurve(t, curve) {
  if (curve === 'sqrt') return Math.sqrt(t);
  if (curve === 'square') return t * t;
  return t;
}

/**
 * @param {{width:number,height:number,data:Uint8ClampedArray}} imageData
 * @param {{entries:Array,nearest:Function}} matcher 调色板匹配器
 * @param {object} options 见 DEFAULT_OPTIONS
 */
function pixelateRelief(imageData, matcher, options = {}) {
  const config = { ...DEFAULT_OPTIONS, ...options };
  const width = Math.max(1, Math.round(imageData.width));
  const height = Math.max(1, Math.round(imageData.height));
  const data = imageData.data;

  const alphaThreshold = config.alphaThreshold === undefined ? 128 : Number(config.alphaThreshold);
  // 最低留 1 格，否则暗部会整列消失，看起来像破洞
  const minHeight = clampInt(config.minHeight, 1, 255, DEFAULT_OPTIONS.minHeight);
  const maxHeight = clampInt(config.maxHeight, minHeight, 255, Math.max(minHeight, DEFAULT_OPTIONS.maxHeight));
  const shellThickness = clampInt(config.shellThickness, 1, 16, DEFAULT_OPTIONS.shellThickness);
  const hollow = !!config.hollow;
  const invert = !!config.invert;
  const curve = config.curve;
  const fillBlock = config.fillBlock || DEFAULT_OPTIONS.fillBlock;

  const totalColumns = width * height;
  const totalVolume = totalColumns * maxHeight;
  if (totalVolume > MAX_VOLUME) {
    throw new Error(
      `立体结构体积 ${totalVolume.toLocaleString('en-US')} 超过上限，请降低最高高度或缩小尺寸`
    );
  }

  const heights = new Int16Array(totalColumns);
  const surfaceOf = new Int32Array(totalColumns).fill(-1);

  const span = maxHeight - minHeight;
  for (let i = 0; i < totalColumns; i++) {
    const p = i * 4;
    if (data[p + 3] < alphaThreshold) continue;

    const r = data[p];
    const g = data[p + 1];
    const b = data[p + 2];
    let luma = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    if (invert) luma = 1 - luma;
    const t = Math.min(1, Math.max(0, applyCurve(luma, curve)));

    heights[i] = Math.min(maxHeight, Math.max(1, minHeight + Math.round(t * span)));
    surfaceOf[i] = matcher.nearest(r, g, b);
  }

  // 调色板：空气 + 实际用到的表层方块 + 填充方块
  const palette = [AIR];
  const indexOfBlock = new Map();
  const ensureIndex = (name) => {
    let index = indexOfBlock.get(name);
    if (index === undefined) {
      index = palette.length;
      palette.push(name);
      indexOfBlock.set(name, index);
    }
    return index;
  };

  const airIndex = 0;
  // 空心模式不需要填充方块，避免调色板里挂一个没用到的方块
  const fillIndex = hollow ? -1 : ensureIndex(fillBlock);
  const surfaceIndex = new Int32Array(totalColumns);
  const grid = new Int32Array(totalColumns);
  const counts = new Map();
  const volume = new Int32Array(totalVolume);
  const preview = new Uint8ClampedArray(totalColumns * 4);
  const heightRange = Math.max(1, maxHeight - minHeight);

  let totalBlocks = 0;

  for (let z = 0; z < height; z++) {
    for (let x = 0; x < width; x++) {
      const i = z * width + x;
      const h = heights[i];
      const entry = surfaceOf[i];

      if (h <= 0 || entry < 0) {
        grid[i] = airIndex;
        continue;
      }

      const block = matcher.entries[entry];
      const blockIndex = ensureIndex(block.block);
      surfaceIndex[i] = blockIndex;
      grid[i] = blockIndex;

      const topLayers = Math.min(shellThickness, h);
      for (let y = 0; y < h; y++) {
        const isSurface = y >= h - topLayers;
        let index;
        if (isSurface) {
          index = blockIndex;
        } else if (hollow) {
          continue;
        } else {
          index = fillIndex;
        }
        volume[(y * height + z) * width + x] = index;
        counts.set(palette[index], (counts.get(palette[index]) || 0) + 1);
        totalBlocks += 1;
      }

      // 顶视图按高度提亮，网页上直接能看出起伏
      const shade = 0.72 + 0.28 * ((h - minHeight) / heightRange);
      const p = i * 4;
      preview[p] = Math.min(255, Math.round(block.rgb[0] * shade));
      preview[p + 1] = Math.min(255, Math.round(block.rgb[1] * shade));
      preview[p + 2] = Math.min(255, Math.round(block.rgb[2] * shade));
      preview[p + 3] = 255;
    }
  }

  return {
    width,
    height,
    plane: 'xz',
    relief: true,
    size: { x: width, y: maxHeight, z: height },
    palette,
    airIndex,
    grid,
    volume,
    counts,
    airCount: totalVolume - totalBlocks,
    totalBlocks,
    totalVolume,
    layers: maxHeight,
    minHeight,
    maxHeight,
    previewPixels: { width, height, data: preview }
  };
}

export { pixelateRelief, applyCurve, DEFAULT_OPTIONS, MAX_VOLUME };
