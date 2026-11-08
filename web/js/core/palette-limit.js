/**
 * 备料优化：把调色板限制到 N 种方块
 *
 * 逐色匹配 240 种方块时成品最准，但备料也最麻烦。这里在 Lab 空间做
 * K-means 聚类，把相近的颜色归为一类，每类只保留一个方块，
 * 从而在「像不像」与「要备多少种方块」之间取舍。
 */

/**
 * @param {Array<{block:string,rgb:number[],lab:number[]}>} entries
 * @param {number} maxBlocks 最多保留几种方块
 * @returns {Array} 过滤后的 entries（保持原顺序）
 */
function limitPalette(entries, maxBlocks) {
  const limit = Math.max(1, Math.round(maxBlocks));
  if (!entries.length) return entries;

  // 同一方块可能有多个数据值，按方块名归并，用第一条颜色作代表
  const groups = new Map();
  for (const entry of entries) {
    if (!groups.has(entry.block)) groups.set(entry.block, entry);
  }
  const blocks = [...groups.keys()];

  if (blocks.length <= limit) return entries;

  const points = blocks.map((name) => groups.get(name).lab);

  // 均匀抽样初始化，保证同样输入得到同样结果
  const centers = [];
  for (let k = 0; k < limit; k++) {
    const index = Math.floor((k + 0.5) * points.length / limit);
    centers.push([...points[Math.min(points.length - 1, index)]]);
  }

  const assign = new Int32Array(points.length).fill(-1);

  for (let iteration = 0; iteration < 12; iteration++) {
    let changed = false;

    for (let i = 0; i < points.length; i++) {
      let best = 0;
      let bestDistance = Infinity;
      for (let k = 0; k < centers.length; k++) {
        const dl = points[i][0] - centers[k][0];
        const da = points[i][1] - centers[k][1];
        const db = points[i][2] - centers[k][2];
        const d = dl * dl + da * da + db * db;
        if (d < bestDistance) {
          bestDistance = d;
          best = k;
        }
      }
      if (assign[i] !== best) {
        assign[i] = best;
        changed = true;
      }
    }

    const sums = centers.map(() => [0, 0, 0, 0]);
    for (let i = 0; i < points.length; i++) {
      const slot = sums[assign[i]];
      slot[0] += points[i][0];
      slot[1] += points[i][1];
      slot[2] += points[i][2];
      slot[3] += 1;
    }
    for (let k = 0; k < centers.length; k++) {
      if (sums[k][3] === 0) continue; // 空类保留原中心
      centers[k] = [sums[k][0] / sums[k][3], sums[k][1] / sums[k][3], sums[k][2] / sums[k][3]];
    }

    if (!changed && iteration > 0) break;
  }

  // 每类里挑距离中心最近的方块作为代表
  const keep = new Set();
  const bestOf = new Map();
  for (let i = 0; i < points.length; i++) {
    const k = assign[i];
    const dl = points[i][0] - centers[k][0];
    const da = points[i][1] - centers[k][1];
    const db = points[i][2] - centers[k][2];
    const distance = dl * dl + da * da + db * db;
    const current = bestOf.get(k);
    if (current === undefined || distance < current.distance) {
      bestOf.set(k, { distance, block: blocks[i] });
    }
  }
  for (const { block } of bestOf.values()) keep.add(block);

  return entries.filter((entry) => keep.has(entry.block));
}

export { limitPalette };
