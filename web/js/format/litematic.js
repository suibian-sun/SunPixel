import { NBTWriter, nbt, gzipCompress } from '../nbt-writer.js';

/**
 * 把调色板索引打包进 64 位长整型流（Litematica 的 BlockStates 存储方式）
 * 每个 long 存放 floor(64 / bits) 个索引，跨 long 连续排列。
 */
function packBlockStates(indices, bitsPerBlock) {
  const bits = Math.max(2, bitsPerBlock);
  const mask = (1n << BigInt(bits)) - 1n;
  const values = [];
  let current = 0n;
  let filled = 0;

  for (let i = 0; i < indices.length; i++) {
    let remaining = bits;
    let value = BigInt(indices[i]) & mask;

    while (remaining > 0) {
      const available = 64 - filled;
      const take = Math.min(available, remaining);
      const chunkMask = (1n << BigInt(take)) - 1n;
      current |= (value & chunkMask) << BigInt(filled);
      filled += take;
      remaining -= take;
      value >>= BigInt(take);

      if (filled === 64) {
        values.push(BigInt.asIntN(64, current));
        current = 0n;
        filled = 0;
      }
    }
  }

  if (filled > 0) values.push(BigInt.asIntN(64, current));
  return values;
}

function bitsNeeded(paletteSize) {
  let bits = 1;
  while ((1 << bits) < paletteSize) bits++;
  return bits;
}

/**
 * Litematica v6
 * 结构：Version / MinecraftDataVersion / Metadata / Regions
 * 每个 region：Position、Size、BlockStatePalette、BlockStates、Entities、TileEntities
 * （旧版本把 BlockStatePalette 写成了 BlockPalette，且 BlockStates 完全没有写入，
 *   导致投影打开后只剩单一方块，这里一并修正。）
 */
async function generateLitematic(result, meta = {}) {
  const { size, palette, volume, totalBlocks } = result;
  const now = BigInt(Date.now());

  const states = packBlockStates(volume, bitsNeeded(palette.length));

  const root = nbt.compound({
    MinecraftDataVersion: nbt.int(meta.dataVersion || 3955),
    Version: nbt.int(6),
    Metadata: nbt.compound({
      Name: nbt.string(meta.name || 'SunPixel'),
      Author: nbt.string(meta.author || 'SunPixel'),
      Description: nbt.string(meta.description || `由 SunPixel 生成 · ${size.x}×${size.y}×${size.z}`),
      RegionCount: nbt.int(1),
      TimeCreated: nbt.long(now),
      TimeModified: nbt.long(now),
      TotalBlocks: nbt.int(totalBlocks),
      TotalVolume: nbt.int(size.x * size.y * size.z),
      EnclosingSize: nbt.vec(size.x, size.y, size.z)
    }),
    Regions: nbt.compound({
      SunPixel: nbt.compound({
        Position: nbt.vec(0, 0, 0),
        Size: nbt.vec(size.x, size.y, size.z),
        BlockStatePalette: nbt.list(10, palette.map((name) => nbt.compound({
          Name: nbt.string(name),
          Properties: nbt.compound({})
        }))),
        BlockStates: nbt.longArray(states),
        Entities: nbt.list(10, []),
        TileEntities: nbt.list(10, []),
        PendingBlockTicks: nbt.list(10, []),
        PendingFluidTicks: nbt.list(10, [])
      })
    })
  });

  const writer = new NBTWriter(Math.max(4096, states.length * 8 + 4096));
  writer.writeRoot(root);
  const compressed = await gzipCompress(writer.getBytes());
  return new Blob([compressed], { type: 'application/octet-stream' });
}

export { generateLitematic, packBlockStates, bitsNeeded };
