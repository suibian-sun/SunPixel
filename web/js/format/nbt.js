import { NBTWriter, nbt, gzipCompress } from '../nbt-writer.js';

/** blocks 列表里每条都是一整个复合标签，几十万条就会吃掉大量内存，超过就劝退 */
const MAX_BLOCKS = 1_500_000;

/**
 * Java 版结构方块文件（structure block / 数据包结构）
 *
 * 和 .schem、.litematic 不同，这个格式是游戏原生的：
 * 放进存档的 generated/... 目录或用结构方块保存的同名位置即可直接加载，
 * 也能被 Amulet、MCEdit-Unified 等工具读取。
 *
 * 结构（1.13+）：
 *   DataVersion / author / size[3] / palette[{Name,Properties}] / blocks[{pos[3],state}] / entities[]
 * 坐标采用 (x, y, z)，与内部体素顺序 (y * z + z) * x + x 不同，这里逐格换算。
 */
async function generateStructureNbt(result, meta = {}) {
  const { size, palette, volume } = result;

  if (result.totalBlocks > MAX_BLOCKS) {
    throw new Error(
      `方块数 ${result.totalBlocks.toLocaleString('en-US')} 过多，结构方块文件会非常大，请改用 .schem 或 .litematic`
    );
  }

  const blocks = [];
  for (let y = 0; y < size.y; y++) {
    for (let z = 0; z < size.z; z++) {
      for (let x = 0; x < size.x; x++) {
        const state = volume[(y * size.z + z) * size.x + x];
        if (state === 0) continue;
        blocks.push(nbt.compound({
          pos: nbt.list(3, [nbt.int(x), nbt.int(y), nbt.int(z)]),
          state: nbt.int(state)
        }));
      }
    }
  }

  const root = nbt.compound({
    DataVersion: nbt.int(meta.dataVersion || 3955),
    author: nbt.string(meta.author || 'SunPixel'),
    size: nbt.list(3, [nbt.int(size.x), nbt.int(size.y), nbt.int(size.z)]),
    palette: nbt.list(10, palette.map((name) => nbt.compound({
      Name: nbt.string(name),
      Properties: nbt.compound({})
    }))),
    blocks: nbt.list(10, blocks),
    entities: nbt.list(10, [])
  });

  const writer = new NBTWriter(Math.max(4096, blocks.length * 24 + 4096));
  writer.writeRoot(root);
  const compressed = await gzipCompress(writer.getBytes());
  return new Blob([compressed], { type: 'application/octet-stream' });
}

export { generateStructureNbt, MAX_BLOCKS };
