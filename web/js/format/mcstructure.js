import { NBTWriter, nbt, gzipCompress } from '../nbt-writer.js';

/** 基岩版方块版本号，随游戏版本变化，写入时保持与主流转换器一致 */
const BEDROCK_BLOCK_VERSION = 17959425;

/** 把 Sponge 顺序 (y,z,x) 的体素重排为基岩版 order (x,y,z) */
function toBedrockOrder(volume, size) {
  const out = new Int32Array(volume.length);
  for (let y = 0; y < size.y; y++) {
    for (let z = 0; z < size.z; z++) {
      for (let x = 0; x < size.x; x++) {
        out[x * size.y * size.z + y * size.z + z] = volume[(y * size.z + z) * size.x + x];
      }
    }
  }
  return out;
}

/**
 * 基岩版结构文件 .mcstructure
 * block_indices 是 List<IntArray>：第一条是方块索引，第二条是 "方块实体层"（全部 -1）
 */
async function generateMcstructure(result, meta = {}) {
  const { size, palette, volume } = result;
  const indices = Array.from(toBedrockOrder(volume, size));

  const root = nbt.compound({
    format_version: nbt.int(1),
    size: nbt.list(3, [size.x, size.y, size.z]),
    structure: nbt.compound({
      block_indices: nbt.list(11, [
        nbt.intArray(indices),
        nbt.intArray(new Array(indices.length).fill(-1))
      ]),
      entities: nbt.list(10, []),
      palette: nbt.compound({
        default: nbt.compound({
          block_palette: nbt.list(10, palette.map((name) => nbt.compound({
            name: nbt.string(name),
            states: nbt.compound({}),
            version: nbt.int(BEDROCK_BLOCK_VERSION)
          }))),
          block_position_data: nbt.compound({})
        })
      })
    }),
    structure_world_origin: nbt.list(3, [0, 0, 0])
  });

  const writer = new NBTWriter(Math.max(4096, indices.length * 8));
  writer.writeRoot(root);
  const compressed = await gzipCompress(writer.getBytes());
  return new Blob([compressed], { type: 'application/octet-stream' });
}

export { generateMcstructure, toBedrockOrder, BEDROCK_BLOCK_VERSION };
