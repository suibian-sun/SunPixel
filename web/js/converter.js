import { BLOCK_DATA, BLOCK_NAMES, BLOCK_DISPLAY_NAMES } from './block-data.js';
import { buildPalette, createMatcher } from './core/color.js';
import { pixelate, transformPixels } from './core/pixelate.js';
import { pixelateMap } from './core/mapart.js';
import { pixelateRelief } from './core/relief.js';
import { limitPalette } from './core/palette-limit.js';
import { MAP_BLOCK_DATA } from './data/map-colors.js';

/**
 * 从图片对象按目标分辨率取像素
 * @param {HTMLImageElement|ImageBitmap|HTMLCanvasElement} image
 */
function getImagePixels(image, width, height, options = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(width));
  canvas.height = Math.max(1, Math.round(height));
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const smooth = options.smooth !== false;
  ctx.imageSmoothingEnabled = smooth;
  if (smooth && 'imageSmoothingQuality' in ctx) ctx.imageSmoothingQuality = 'high';
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  return { width: canvas.width, height: canvas.height, data: imageData.data };
}

/** 由方块类型构建匹配器，可选限制方块种类（备料优化） */
function createMatcherFromTypes(blockTypes, metric = 'lab', maxBlocks = 0) {
  let palette = buildPalette(blockTypes, BLOCK_DATA);
  if (!palette.entries.length) {
    throw new Error('所选方块类型没有任何颜色数据');
  }
  if (maxBlocks > 0 && maxBlocks < new Set(palette.entries.map((e) => e.block)).size) {
    palette = { entries: limitPalette(palette.entries, maxBlocks), blocks: [] };
  }
  return createMatcher(palette, metric);
}

/** 预览色：同一方块只取第一次出现的颜色 */
function colorsForPalette(palette, entries) {
  const byBlock = new Map();
  for (const entry of entries) {
    if (!byBlock.has(entry.block)) byBlock.set(entry.block, entry.rgb);
  }
  return palette.map((name) => byBlock.get(name) || null);
}

/** 是否需要做旋转 / 镜像：地图画与浮雕由本函数自己处理，平面像素画交给 pixelate */
function hasTransform(options) {
  const rotate = ((Math.round((options.rotate || 0) / 90) * 90) % 360 + 360) % 360;
  return rotate !== 0 || !!options.mirrorX || !!options.mirrorY;
}

/** 填充方块不在所选调色板里时，预览给一个中性灰，避免生成图片出现空洞 */
function fallbackColor(name, entries) {
  const hit = entries.find((entry) => entry.block === name);
  if (hit) return hit.rgb;
  if (name === 'minecraft:air') return null;
  return [128, 128, 128];
}

/**
 * 主转换函数
 * @param {{width:number,height:number,data:Uint8ClampedArray}} imageData
 * @param {string[]} blockTypes
 * @param {object} options
 */
function processPixels(imageData, blockTypes, options = {}) {
  const matcher = createMatcherFromTypes(blockTypes, options.metric || 'lab', options.maxBlocks || 0);

  if (options.relief) {
    const oriented = hasTransform(options) ? transformPixels(imageData, options) : imageData;
    // UI 用 reliefXxx 命名避免和图片调节的 invert 撞车，这里映射成核心参数名
    const result = pixelateRelief(oriented, matcher, {
      alphaThreshold: options.alphaThreshold,
      minHeight: options.reliefMin,
      maxHeight: options.reliefMax,
      shellThickness: options.reliefShell,
      hollow: options.reliefHollow,
      fillBlock: options.reliefFill,
      curve: options.reliefCurve,
      invert: options.reliefInvert
    });
    return {
      ...result,
      colors: result.palette.map((name) => fallbackColor(name, matcher.entries)),
      blockPalette: result.palette,
      blockCounts: Object.fromEntries(
        [...result.counts.entries()].map(([name, count]) => [name.replace('minecraft:', ''), count])
      )
    };
  }

  if (options.mapArt) {
    // 地图画同样要响应旋转与镜像，否则勾了旋转成品却不动
    const oriented = hasTransform(options) ? transformPixels(imageData, options) : imageData;
    const result = pixelateMap(oriented, {
      types: blockTypes,
      alphaThreshold: options.alphaThreshold,
      mapLayers: options.mapLayers,
      lumaThreshold: options.lumaThreshold
    });
    const entries = result.palette
      .filter((name) => name !== 'minecraft:air')
      .map((name) => {
        const short = name.replace('minecraft:', '');
        const info = MAP_BLOCK_DATA[short];
        return { block: name, rgb: info ? info.shades[0] : [128, 128, 128] };
      });
    return {
      ...result,
      colors: colorsForPalette(result.palette, entries),
      blockPalette: result.palette,
      blockCounts: Object.fromEntries(
        [...result.counts.entries()].map(([name, count]) => [name.replace('minecraft:', ''), count])
      )
    };
  }

  const result = pixelate(imageData, matcher, options);

  return {
    ...result,
    colors: colorsForPalette(result.palette, matcher.entries),
    blockPalette: result.palette,
    blockCounts: Object.fromEntries(
      [...result.counts.entries()].map(([name, count]) => [name.replace('minecraft:', ''), count])
    )
  };
}

/** 生成效果图（按方块平均色重绘，1 像素 = 1 方块） */
function generatePreview(result, scale = 1) {
  const { width, height, grid, colors } = result;
  const canvas = document.createElement('canvas');
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const index = grid[y * width + x];
      const color = colors[index];
      if (!color) continue;
      ctx.fillStyle = `rgb(${color[0]},${color[1]},${color[2]})`;
      ctx.fillRect(x * scale, y * scale, scale, scale);
    }
  }

  return canvas.toDataURL('image/png');
}

export {
  BLOCK_DATA,
  BLOCK_NAMES,
  BLOCK_DISPLAY_NAMES,
  getImagePixels,
  createMatcherFromTypes,
  processPixels,
  generatePreview
};
