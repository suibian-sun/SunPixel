import { BLOCK_DATA, BLOCK_NAMES, BLOCK_DISPLAY_NAMES } from './block-data.js';
import { buildPalette, createMatcher } from './core/color.js';
import { pixelate } from './core/pixelate.js';

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

/** 由方块类型构建匹配器 */
function createMatcherFromTypes(blockTypes, metric = 'lab') {
  const palette = buildPalette(blockTypes, BLOCK_DATA);
  if (!palette.entries.length) {
    throw new Error('所选方块类型没有任何颜色数据');
  }
  return createMatcher(palette, metric);
}

/**
 * 主转换函数
 * @param {{width:number,height:number,data:Uint8ClampedArray}} imageData
 * @param {string[]} blockTypes
 * @param {object} options
 */
function processPixels(imageData, blockTypes, options = {}) {
  const matcher = createMatcherFromTypes(blockTypes, options.metric || 'lab');
  const result = pixelate(imageData, matcher, options);

  // 预览用的颜色（与 palette 索引对齐，空气为 null）
  const colors = result.palette.map((name) => {
    const entry = matcher.entries.find((e) => e.block === name);
    return entry ? entry.rgb : null;
  });

  return {
    ...result,
    colors,
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
