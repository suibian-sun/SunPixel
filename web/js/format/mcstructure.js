import { NBTWriter, nbt } from '../nbt-writer.js';

/** 基岩版方块版本号，随游戏版本变化，写入时保持与主流转换器一致 */
const BEDROCK_BLOCK_VERSION = 17959425;

/**
 * 基岩版结构文件的方块索引顺序是 x 变化最快、其次 z、最后 y，
 * 与内部 volume 的 (y * sizeZ + z) * sizeX + x 完全一致，无需重排。
 * （旧实现按 x 最外重排，等于把 X/Z 轴对调，非立方结构会整体转 90°。）
 */
function toBedrockOrder(volume) {
  return volume;
}

/**
 * 基岩版结构文件 .mcstructure
 *
 * 两个容易踩的坑：
 *  1. Bedrock 全部用小端序 NBT，用 Java 的大端写出来游戏直接读不了；
 *  2. .mcstructure 是不压缩的裸 NBT，不能 gzip。
 */
async function generateMcstructure(result, meta = {}) {
  const { size, palette, volume } = result;
  const indices = Array.from(toBedrockOrder(volume));
  const second = new Array(indices.length).fill(-1);

  const root = nbt.compound({
    format_version: nbt.int(1),
    size: nbt.list(3, [size.x, size.y, size.z]),
    structure: nbt.compound({
      block_indices: nbt.list(11, [
        nbt.intArray(indices),
        nbt.intArray(second)
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

  const writer = new NBTWriter(Math.max(4096, indices.length * 8), { littleEndian: true });
  writer.writeRoot(root);
  return new Blob([writer.getBytes()], { type: 'application/octet-stream' });
}

export { generateMcstructure, toBedrockOrder, BEDROCK_BLOCK_VERSION };
