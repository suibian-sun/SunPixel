const AIR = 'minecraft:air';

/**
 * 图例字符：A-Z → a-z → 0-9，共 62 个单字符。
 * 必须保证每格只占 1 个字符，否则逐行图纸会错位；超出部分统一用 ? 占位。
 */
const LEGEND_SYMBOLS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

function buildLegend(palette) {
  const used = palette.filter((name) => name !== AIR);
  const legend = new Map();
  used.forEach((name, index) => {
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
  const { width, height, grid, palette, counts, plane } = result;
  const legend = buildLegend(palette);
  const lines = [];

  lines.push(`# ${meta.name || 'SunPixel 施工图纸'}`);
  lines.push('');
  lines.push(`- 尺寸：**${width} × ${height}**${plane === 'xy' ? '（竖立，贴墙）' : '（平铺，地面）'}`);
  lines.push(`- 方块总数：**${result.totalBlocks}**（空气 ${result.airCount}）`);
  lines.push(`- 方块种类：**${counts.size}**`);
  if (counts.size > LEGEND_SYMBOLS.length) {
    lines.push(`- 注意：方块超过 ${LEGEND_SYMBOLS.length} 种，图纸中第 ${LEGEND_SYMBOLS.length} 种之后的方块以 \`?\` 表示，请对照材料清单`);
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
  lines.push('每行开头是第几行（从 0 开始），第一行在最上方。每 10 列标一次列号。');
  lines.push('');

  const axisWidth = 4;
  const rulerTens = [];
  const rulerOnes = [];
  for (let x = 0; x < width; x++) {
    rulerTens.push(x % 10 === 0 ? String(Math.floor(x / 10) % 10) : ' ');
    rulerOnes.push(String(x % 10));
  }
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

  return {
    blob: new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' }),
    info: { blockTypes: counts.size }
  };
}

/** 材料清单 CSV：x,y,z,block 每方块一行，方便丢进表格或筛选 */
function generateMaterialCsv(result) {
  const { size, volume, palette } = result;
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

export { generateBlueprint, generateMaterialCsv, buildLegend, LEGEND_SYMBOLS };
