/**
 * 颜色匹配核心
 *
 * 相比旧版本：
 *  - 改用 CIE Lab（D65）感知色差，替代原来的 Redmean 近似，渐变与肤色区域明显更准
 *  - 调色板按“方块名 + 数据值”去重，避免多个方块类型选中后重复计算
 *  - 增加 5 位量化缓存，128×128 乃至 512×512 的转换不再重复做全表扫描
 */

const D65 = { x: 0.95047, y: 1.0, z: 1.08883 };

function srgbToLinear(channel) {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

/** sRGB(0-255) -> CIE Lab */
function rgbToLab(r, g, b) {
  const rl = srgbToLinear(r);
  const gl = srgbToLinear(g);
  const bl = srgbToLinear(b);

  const x = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) / D65.x;
  const y = (rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750) / D65.y;
  const z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) / D65.z;

  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : (7.787 * t) + 16 / 116);
  const fx = f(x);
  const fy = f(y);
  const fz = f(z);

  return [
    116 * fy - 16,
    500 * (fx - fy),
    200 * (fy - fz)
  ];
}

/** 解析 "(R,G,B)" 形式的颜色键 */
function parseColorKey(key) {
  const clean = String(key).replace(/[()\[\]\s]/g, '');
  const parts = clean.split(',');
  if (parts.length < 3) return null;
  const rgb = parts.slice(0, 3).map((v) => Number.parseInt(v, 10));
  if (rgb.some((v) => !Number.isFinite(v))) return null;
  return rgb;
}

/**
 * 由方块类型构建调色板
 * @param {string[]} blockTypes 例如 ['wool', 'concrete']
 * @param {object} blockData BLOCK_DATA
 * @returns {{entries: Array<{block:string,data:number,rgb:number[],lab:number[]}>, blocks: string[]}}
 */
function buildPalette(blockTypes, blockData) {
  const seen = new Set();
  const entries = [];

  for (const type of blockTypes) {
    const group = blockData[type];
    if (!group) continue;
    for (const [colorKey, info] of Object.entries(group.colors)) {
      const rgb = parseColorKey(colorKey);
      if (!rgb) continue;
      const block = info[0];
      const data = info[1] || 0;
      const dedupeKey = `${block}@${data}`;
      if (seen.has(dedupeKey)) continue;
      seen.add(dedupeKey);
      entries.push({ block, data, rgb, lab: rgbToLab(rgb[0], rgb[1], rgb[2]) });
    }
  }

  return { entries, blocks: entries.map((e) => e.block) };
}

/** 最近颜色查找器，带 5 位量化缓存 */
function createMatcher(palette, metric = 'lab') {
  const entries = palette.entries;
  if (!entries.length) throw new Error('调色板为空，请至少选择一种方块类型');

  const labs = entries.map((e) => e.lab);
  const rgbs = entries.map((e) => e.rgb);
  const cache = new Map();
  const useLab = metric !== 'rgb';

  function distanceTo(index, r, g, b) {
    if (useLab) {
      const lab = rgbToLab(r, g, b);
      const dl = lab[0] - labs[index][0];
      const da = lab[1] - labs[index][1];
      const db = lab[2] - labs[index][2];
      return dl * dl + da * da + db * db;
    }
    const dr = r - rgbs[index][0];
    const dg = g - rgbs[index][1];
    const db = b - rgbs[index][2];
    // Redmean 加权，比纯欧氏距离更接近人眼感受
    const rMean = (r + rgbs[index][0]) / 2;
    return (2 + rMean / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rMean) / 256) * db * db;
  }

  function nearest(r, g, b) {
    const key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3);
    const hit = cache.get(key);
    if (hit !== undefined) return hit;

    let best = 0;
    let bestDistance = Infinity;

    if (useLab) {
      // 目标色只转换一次，避免在 240 个候选里重复做 Lab 变换
      const lab = rgbToLab(r, g, b);
      const l = lab[0];
      const a = lab[1];
      const bb = lab[2];
      for (let i = 0; i < entries.length; i++) {
        const dl = l - labs[i][0];
        const da = a - labs[i][1];
        const db = bb - labs[i][2];
        const d = dl * dl + da * da + db * db;
        if (d < bestDistance) {
          bestDistance = d;
          best = i;
        }
      }
    } else {
      for (let i = 0; i < entries.length; i++) {
        const d = distanceTo(i, r, g, b);
        if (d < bestDistance) {
          bestDistance = d;
          best = i;
        }
      }
    }

    cache.set(key, best);
    return best;
  }

  /**
   * 抖动时也走同一套距离度量与量化缓存。
   * 旧实现用 RGB 欧氏距离扩散误差，和「颜色匹配：CIE Lab」不一致，
   * 渐变区域会出现明明选了 Lab 却按 RGB 取色的偏色。
   */
  return { nearest, entries, cache };
}

export { rgbToLab, parseColorKey, buildPalette, createMatcher, D65 };
