/**
 * RunAway 交换格式 .json
 * 保留旧版字段（format/version/palette/blocks）以便兼容老工具，
 * 同时补充 size、origin、materials 等便于二次处理的字段。
 */
function generateRunaway(result, meta = {}) {
  const { size, palette, volume, counts, airCount } = result;

  const data = {
    format: 'RunAway',
    version: 2,
    generated_by: 'SunPixel',
    generated_at: new Date().toISOString(),
    name: meta.name || 'SunPixel',
    dimensions: { width: size.x, height: size.y, depth: size.z },
    size: [size.x, size.y, size.z],
    origin: [0, 0, 0],
    plane: result.plane,
    // 索引顺序：x 变化最快，其次 z，最后 y
    order: 'y,z,x',
    palette,
    blocks: Array.from(volume),
    statistics: {
      block_count: result.totalBlocks,
      air_count: airCount,
      block_types: counts.size,
      block_details: Object.fromEntries(counts)
    }
  };

  return {
    blob: new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' }),
    info: { blockTypes: counts.size }
  };
}

export { generateRunaway };
