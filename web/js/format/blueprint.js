const AIR = 'minecraft:air';

/**
 * 图例字符：A-Z → a-z → 0-9，共 62 个单字符。
 * 必须保证每格只占 1 个字符，否则逐行图纸会错位；超出部分统一用 ? 占位。
 */
const LEGEND_SYMBOLS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

/** 材料清单最多输出的行数，再大多半是误操作了立体模式 */
const MAX_CSV_ROWS = 1_000_000;

function buildLegend(palette) {
  const used = palette.filter((name) => name !== AIR);
  return buildLegendFrom(used);
}

/** 按给定顺序生成 符号 → 方块 的图例，用于单层图纸或每一层单独出图例 */
function buildLegendFrom(names) {
  const legend = new Map();
  names.forEach((name, index) => {
    legend.set(name, LEGEND_SYMBOLS[index] || '?');
  });
  return legend;
}

/** 去掉 minecraft: 前缀，图纸更易读 */
function shortName(name) {
  return name.replace('minecraft:', '');
}

function pad(value, width) {
  const text = String(value);
  return text.length >= width ? text : ' '.repeat(width - text.length) + text;
}

/**
 * 手动搭建图纸（Markdown）
 * 面向不装投影模组、或使用基岩版/网易版的玩家：按行给出方块，逐行摆放即可。
 */
function generateBlueprint(result, meta = {}) {
  const { width, height, grid, palette, counts, plane, size, volume } = result;
  const layers = size ? size.y : 1;
  // 竖立结构本身就是一张 2D 图，逐行给正面图即可；只有平铺的立体结构才按层出图
  const isStack = layers > 1 && plane !== 'xy';
  const legend = buildLegend(palette);
  const lines = [];

  lines.push(`# ${meta.name || 'SunPixel 施工图纸'}`);
  lines.push('');
  lines.push(
    isStack
      ? `- 尺寸：**${size.x} × ${size.y} × ${size.z}**（宽 × 高 × 深，立体）`
      : `- 尺寸：**${width} × ${height}**${plane === 'xy' ? '（竖立，贴墙）' : '（平铺，地面）'}`
  );
  lines.push(`- 方块总数：**${result.totalBlocks}**（空气 ${result.airCount}）`);
  lines.push(`- 方块种类：**${counts.size}**`);
  if (counts.size > LEGEND_SYMBOLS.length) {
    lines.push(
      isStack
        ? `- 注意：整座结构有 ${counts.size} 种方块，总图例只列出前 ${LEGEND_SYMBOLS.length} 种；每层图纸下方另有该层自己的图例，照层内图例摆放即可`
        : `- 注意：方块超过 ${LEGEND_SYMBOLS.length} 种，图纸中第 ${LEGEND_SYMBOLS.length} 种之后的方块以 \`?\` 表示，请对照材料清单`
    );
  }
  lines.push(`- 生成时间：${new Date().toLocaleString('zh-CN')}`);
  lines.push('');
  lines.push('## 材料清单');
  lines.push('');
  lines.push('| 方块 | 数量 | 折合组（64/组） |');
  lines.push('| --- | ---: | ---: |');

  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  for (const [block, count] of sorted) {
    lines.push(`| ${shortName(block)} | ${count} | ${(count / 64).toFixed(2)} |`);
  }

  lines.push('');
  lines.push('## 图例');
  lines.push('');
  lines.push('| 符号 | 方块 |');
  lines.push('| :---: | --- |');
  lines.push(`| . | 空气 |`);
  for (const [block, symbol] of legend) {
    lines.push(`| ${symbol} | ${shortName(block)} |`);
  }

  lines.push('');
  lines.push('## 逐行图纸');
  lines.push('');

  const axisWidth = 4;
  const columns = isStack ? size.x : width;
  const rulerTens = [];
  const rulerOnes = [];
  for (let x = 0; x < columns; x++) {
    rulerTens.push(x % 10 === 0 ? String(Math.floor(x / 10) % 10) : ' ');
    rulerOnes.push(String(x % 10));
  }

  if (isStack) {
    // 立体结构（地图画、浮雕、竖立）按层给图，每层都是一张俯视图。
    // 每一层单独出图例：一层的方块种类通常远少于整座结构，
    // 这样 100 多种地图色也不会因为超出 62 个符号而全变成 ?。
    lines.push(`结构共 ${layers} 层，从 Y=0 逐层往上放。每张图的行是 Z、列是 X，每 10 列标一次列号。`);
    lines.push('');
    for (let y = 0; y < layers; y++) {
      // 先扫一遍这一层用到哪些方块，再按出现顺序出图例
      const used = [];
      const seen = new Set();
      for (let z = 0; z < size.z; z++) {
        for (let x = 0; x < size.x; x++) {
          const index = volume[(y * size.z + z) * size.x + x];
          if (index === 0) continue;
          const name = palette[index];
          if (!seen.has(name)) {
            seen.add(name);
            used.push(name);
          }
        }
      }

      const layerLegend = buildLegendFrom(used);
      lines.push(`### Y = ${y}`);
      lines.push('');
      if (used.length) {
        const summary = used
          .map((name) => `${layerLegend.get(name) || '?'}=${shortName(name)}`)
          .join('、');
        lines.push(`图例：${summary}`);
        lines.push('');
      }
      lines.push('```text');
      lines.push(' '.repeat(axisWidth) + rulerTens.join(''));
      lines.push(' '.repeat(axisWidth) + rulerOnes.join(''));
      for (let z = 0; z < size.z; z++) {
        let row = '';
        for (let x = 0; x < size.x; x++) {
          const index = volume[(y * size.z + z) * size.x + x];
          row += index === 0 ? '.' : layerLegend.get(palette[index]) || '?';
        }
        lines.push(`${pad(z, axisWidth - 1)} ${row}`);
      }
      lines.push('```');
      lines.push('');
    }
  } else {
    lines.push('每行开头是第几行（从 0 开始），第一行在最上方。每 10 列标一次列号。');
    lines.push('');
    lines.push('```text');
    lines.push(' '.repeat(axisWidth) + rulerTens.join(''));
    lines.push(' '.repeat(axisWidth) + rulerOnes.join(''));

    for (let y = 0; y < height; y++) {
      let row = '';
      for (let x = 0; x < width; x++) {
        const index = grid[y * width + x];
        if (index === 0) {
          row += '.';
        } else {
          row += legend.get(palette[index]) || '?';
        }
      }
      lines.push(`${pad(y, axisWidth - 1)} ${row}`);
    }
    lines.push('```');
    lines.push('');
  }

  return {
    blob: new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' }),
    info: { blockTypes: counts.size }
  };
}

/** 材料清单 CSV：x,y,z,block 每方块一行，方便丢进表格或筛选 */
function generateMaterialCsv(result) {
  const { size, volume, palette } = result;
  // 立体结构可能有几百万个方块，纯文本 CSV 会撑爆内存，超过上限直接给出提示
  if (result.totalBlocks > MAX_CSV_ROWS) {
    throw new Error(
      `方块数 ${result.totalBlocks.toLocaleString('en-US')} 超过 CSV 上限 ${MAX_CSV_ROWS.toLocaleString('en-US')}，请改用 .schem / .litematic`
    );
  }
  const rows = ['x,y,z,block'];
  for (let y = 0; y < size.y; y++) {
    for (let z = 0; z < size.z; z++) {
      for (let x = 0; x < size.x; x++) {
        const index = volume[(y * size.z + z) * size.x + x];
        if (index === 0) continue;
        rows.push(`${x},${y},${z},${palette[index]}`);
      }
    }
  }
  return {
    blob: new Blob([rows.join('\n') + '\n'], { type: 'text/csv;charset=utf-8' }),
    info: { rows: rows.length - 1 }
  };
}

export { generateBlueprint, generateMaterialCsv, buildLegend, buildLegendFrom, LEGEND_SYMBOLS };
