/**
 * 像素画核心：几何变换 → 颜色量化（可抖动）→ 体素栅格
 *
 * 全部为纯函数，不依赖 DOM，方便在 Node 里直接跑单元测试。
 */

const AIR = 'minecraft:air';

/** 旋转 / 镜像。rotate 为顺时针角度（0/90/180/270） */
function transformPixels(imageData, options = {}) {
  const { width: srcW, height: srcH, data: src } = imageData;
  const rotate = ((Math.round((options.rotate || 0) / 90) * 90) % 360 + 360) % 360;
  const mirrorX = !!options.mirrorX;
  const mirrorY = !!options.mirrorY;
  const turns = rotate / 90;

  if (turns === 0 && !mirrorX && !mirrorY) {
    return { width: srcW, height: srcH, data: Uint8ClampedArray.from(src) };
  }

  const outW = turns % 2 === 1 ? srcH : srcW;
  const outH = turns % 2 === 1 ? srcW : srcH;
  const out = new Uint8ClampedArray(outW * outH * 4);

  for (let y = 0; y < outH; y++) {
    for (let x = 0; x < outW; x++) {
      const fx = mirrorX ? outW - 1 - x : x;
      const fy = mirrorY ? outH - 1 - y : y;

      let sx;
      let sy;
      switch (turns) {
        case 1: // 顺时针 90°
          sx = fy;
          sy = srcH - 1 - fx;
          break;
        case 2:
          sx = srcW - 1 - fx;
          sy = srcH - 1 - fy;
          break;
        case 3:
          sx = srcW - 1 - fy;
          sy = fx;
          break;
        default:
          sx = fx;
          sy = fy;
      }

      const s = (sy * srcW + sx) * 4;
      const d = (y * outW + x) * 4;
      out[d] = src[s];
      out[d + 1] = src[s + 1];
      out[d + 2] = src[s + 2];
      out[d + 3] = src[s + 3];
    }
  }

  return { width: outW, height: outH, data: out };
}

/**
 * 把像素映射到调色板索引
 * @returns {Int32Array} 每像素的调色板索引，-1 表示空气
 */
function quantize(imageData, matcher, options = {}) {
  const { width, height, data } = imageData;
  const alphaThreshold = options.alphaThreshold === undefined ? 128 : options.alphaThreshold;
  const dither = options.dither === 'floyd';
  const serpentine = options.serpentine !== false;

  const total = width * height;
  const indices = new Int32Array(total);
  const rgb = new Float32Array(total * 3);
  const opaque = new Uint8Array(total);

  for (let i = 0; i < total; i++) {
    const p = i * 4;
    opaque[i] = data[p + 3] >= alphaThreshold ? 1 : 0;
    rgb[i * 3] = data[p];
    rgb[i * 3 + 1] = data[p + 1];
    rgb[i * 3 + 2] = data[p + 2];
  }

  if (!dither) {
    for (let i = 0; i < total; i++) {
      if (!opaque[i]) {
        indices[i] = -1;
        continue;
      }
      indices[i] = matcher.nearest(
        clamp(rgb[i * 3]),
        clamp(rgb[i * 3 + 1]),
        clamp(rgb[i * 3 + 2])
      );
    }
    return indices;
  }

  const entries = matcher.entries;
  for (let y = 0; y < height; y++) {
    const leftToRight = !serpentine || y % 2 === 0;
    for (let step = 0; step < width; step++) {
      const x = leftToRight ? step : width - 1 - step;
      const i = y * width + x;
      if (!opaque[i]) {
        indices[i] = -1;
        continue;
      }

      const r = clamp(rgb[i * 3]);
      const g = clamp(rgb[i * 3 + 1]);
      const b = clamp(rgb[i * 3 + 2]);
      const idx = matcher.nearest(r, g, b);
      indices[i] = idx;

      const target = entries[idx].rgb;
      const errR = r - target[0];
      const errG = g - target[1];
      const errB = b - target[2];

      const spread = (ox, oy, factor) => {
        const nx = x + (leftToRight ? ox : -ox);
        const ny = y + oy;
        if (nx < 0 || nx >= width || ny >= height) return;
        const ni = ny * width + nx;
        if (!opaque[ni]) return;
        // 只有仍在图像内的不透明像素才吸收误差
        rgb[ni * 3] += errR * factor;
        rgb[ni * 3 + 1] += errG * factor;
        rgb[ni * 3 + 2] += errB * factor;
      };

      spread(1, 0, 7 / 16);
      spread(-1, 1, 3 / 16);
      spread(0, 1, 5 / 16);
      spread(1, 1, 1 / 16);
    }
  }

  return indices;
}

function clamp(value) {
  return value < 0 ? 0 : value > 255 ? 255 : Math.round(value);
}

/**
 * 由调色板索引构建体素栅格
 * @param {Int32Array} indices 平面像素的调色板索引（-1 = 空气）
 * @param {number} width 平面宽（X）
 * @param {number} height 平面高（Z 或 Y）
 * @param {string[]} blocks 调色板方块名（不含空气）
 * @param {object} options plane: 'xz' 平铺 / 'xy' 竖立
 */
function buildVoxelGrid(indices, width, height, blocks, options = {}) {
  const plane = options.plane === 'xy' ? 'xy' : 'xz';

  // 先按完整调色板编号，再压缩成"只包含实际用到的方块"，避免文件里挂着一堆没用的方块
  const raw = new Int32Array(width * height);
  const used = new Set();
  for (let i = 0; i < indices.length; i++) {
    raw[i] = indices[i] < 0 ? 0 : indices[i] + 1;
    used.add(raw[i]);
  }
  used.add(0);

  const remap = new Map();
  const palette = [];
  for (let oldIndex = 0; oldIndex < blocks.length + 1; oldIndex++) {
    if (!used.has(oldIndex)) continue;
    remap.set(oldIndex, palette.length);
    palette.push(oldIndex === 0 ? AIR : blocks[oldIndex - 1]);
  }

  const grid = new Int32Array(width * height);
  for (let i = 0; i < raw.length; i++) grid[i] = remap.get(raw[i]);

  const airIndex = 0;
  const size = plane === 'xy'
    ? { x: width, y: height, z: 1 }
    : { x: width, y: 1, z: height };

  const volume = new Int32Array(size.x * size.y * size.z).fill(airIndex);

  const counts = new Map();
  let airCount = 0;

  for (let py = 0; py < height; py++) {
    for (let px = 0; px < width; px++) {
      const paletteIndex = grid[py * width + px];
      let vx;
      let vy;
      let vz;
      if (plane === 'xy') {
        // 竖立：图片第 0 行在最上层，避免成品上下颠倒
        vx = px;
        vy = height - 1 - py;
        vz = 0;
      } else {
        vx = px;
        vy = 0;
        vz = py;
      }
      volume[(vy * size.z + vz) * size.x + vx] = paletteIndex;

      if (paletteIndex === airIndex) {
        airCount++;
      } else {
        const name = palette[paletteIndex];
        counts.set(name, (counts.get(name) || 0) + 1);
      }
    }
  }

  const totalBlocks = width * height;
  return {
    width,
    height,
    plane,
    size,
    palette,
    airIndex,
    grid,
    volume,
    counts,
    airCount,
    totalBlocks: totalBlocks - airCount,
    totalVolume: totalBlocks
  };
}

/** 组合流程：变换 → 量化 → 体素化 */
function pixelate(imageData, matcher, options = {}) {
  const transformed = transformPixels(imageData, options);
  const indices = quantize(transformed, matcher, options);
  return buildVoxelGrid(indices, transformed.width, transformed.height, matcher.entries.map((e) => e.block), options);
}

/** 从体素栅格取某个坐标的调色板索引 */
function voxelAt(result, x, y, z) {
  const { size } = result;
  if (x < 0 || y < 0 || z < 0 || x >= size.x || y >= size.y || z >= size.z) return -1;
  return result.volume[(y * size.z + z) * size.x + x];
}

export { AIR, transformPixels, quantize, buildVoxelGrid, pixelate, voxelAt };
