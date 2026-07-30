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

// 从 Canvas 读取像素数据
function getImagePixels(image, width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(image, 0, 0, width, height);
  const imageData = ctx.getImageData(0, 0, width, height);
  return imageData.data;
}

// 处理像素数据并生成结构
function processPixels(pixels, width, height, selectedBlocks, format) {
  const colorMap = buildColorMap(selectedBlocks);
  
  const blockPalette = [];
  const blockPaletteMap = {};
  const blockData = [];
  const blockCounts = {};
  
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
      
      const paletteIdx = blockPaletteMap[match.blockName];
      blockData.push(paletteIdx);
      
      // 统计方块数量
      const shortName = match.blockName.replace('minecraft:', '');
      blockCounts[shortName] = (blockCounts[shortName] || 0) + 1;
    }
  }
  
  return { 
    blockPalette, 
    blockData, 
    blockDataValues: blockData, 
    width, 
    height, 
    depth: 1,
    blockCounts
  };
}

// 生成方块预览图
function generatePreview(pixels, result, width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  
  const colorMap = buildColorMapFromResult(result);
  
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x);
      const paletteIdx = result.blockData[idx];
      const blockName = result.blockPalette[paletteIdx];
      const color = colorMap[blockName] || [255, 255, 255];
      ctx.fillStyle = `rgb(${color[0]},${color[1]},${color[2]})`;
      ctx.fillRect(x, y, 1, 1);
    }
  }
  
  return canvas.toDataURL('image/png');
}

function buildColorMapFromResult(result) {
  const colorMap = {};
  for (const [colorKey, blockInfo] of Object.entries(getAllColors())) {
    const blockName = blockInfo[0];
    if (result.blockPalette.includes(blockName) && !colorMap[blockName]) {
      const rgb = parseColorKey(colorKey);
      colorMap[blockName] = rgb;
    }
  }
  return colorMap;
}

function getAllColors() {
  const allColors = {};
  for (const blockData of Object.values(BLOCK_DATA)) {
    for (const [colorKey, blockInfo] of Object.entries(blockData.colors)) {
      allColors[colorKey] = blockInfo;
    }
  }
  return allColors;
}

export { processPixels, findClosestColor, buildColorMap, getImagePixels, generatePreview };