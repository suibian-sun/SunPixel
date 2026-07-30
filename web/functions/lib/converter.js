import { BLOCK_DATA } from './block-data.js';

// 颜色距离计算 (CIE Lab 感知距离的简化版本)
function colorDistance(c1, c2) {
  const rMean = (c1[0] + c2[0]) / 2;
  const rDiff = c1[0] - c2[0];
  const gDiff = c1[1] - c2[1];
  const bDiff = c1[2] - c2[2];
  return Math.sqrt(
    (2 + rMean / 256) * (rDiff ** 2) +
    4 * (gDiff ** 2) +
    (2 + (255 - rMean) / 256) * (bDiff ** 2)
  );
}

// 解析颜色键 "(R,G,B)" -> [R, G, B]
function parseColorKey(key) {
  const clean = key.replace(/[()]/g, '');
  return clean.split(',').map(Number);
}

// 构建颜色映射表
function buildColorMap(selectedBlocks) {
  const colorMap = {};
  for (const blockName of selectedBlocks) {
    const blockData = BLOCK_DATA[blockName];
    if (!blockData) continue;
    for (const [colorKey, blockInfo] of Object.entries(blockData.colors)) {
      const rgb = parseColorKey(colorKey);
      const key = `${rgb[0]},${rgb[1]},${rgb[2]}`;
      colorMap[key] = {
        rgb,
        blockName: blockInfo[0],
        data: blockInfo[1]
      };
    }
  }
  return Object.values(colorMap);
}

// 查找最接近的颜色
function findClosestColor(r, g, b, colorMap) {
  let closest = null;
  let minDist = Infinity;
  for (const entry of colorMap) {
    const dist = colorDistance([r, g, b], entry.rgb);
    if (dist < minDist) {
      minDist = dist;
      closest = entry;
    }
  }
  return closest || { blockName: 'minecraft:white_concrete', data: 0 };
}

// 处理像素数据并生成结构
function processPixels(pixels, width, height, selectedBlocks, format) {
  const colorMap = buildColorMap(selectedBlocks);
  const totalPixels = width * height;
  
  const blockPalette = [];
  const blockPaletteMap = {};
  const blockData = [];
  const blockDataValues = [];
  
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 4;
      const r = pixels[idx];
      const g = pixels[idx + 1];
      const b = pixels[idx + 2];
      
      const match = findClosestColor(r, g, b, colorMap);
      
      if (!(match.blockName in blockPaletteMap)) {
        blockPaletteMap[match.blockName] = blockPalette.length;
        blockPalette.push(match.blockName);
      }
      
      blockData.push(blockPaletteMap[match.blockName]);
      blockDataValues.push(match.data);
    }
  }
  
  return { blockPalette, blockData, blockDataValues, width, height, depth: 1 };
}

// 获取可用的方块类型列表
function getAvailableBlocks() {
  return Object.keys(BLOCK_DATA);
}

// 获取方块中文名称
function getBlockDisplayName(blockName) {
  return BLOCK_DATA[blockName]?.name || blockName;
}

export { processPixels, findClosestColor, buildColorMap, getAvailableBlocks, getBlockDisplayName };