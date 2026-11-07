import { NBTWriter, nbt, gzipCompress } from '../nbt-writer.js';

/** 有符号 LEB128 VarInt（Sponge Schematic v2 的 BlockData 编码） */
function writeVarInt(target, value) {
  let v = value | 0;
  while (true) {
    const byte = v & 0x7f;
    v >>>= 7;
    if (v !== 0) {
      target.push(byte | 0x80);
    } else {
      target.push(byte);
      break;
    }
  }
}

/**
 * Sponge Schematic v2
 * 坐标顺序遵循规范：index = (y * Length + z) * Width + x
 */
async function generateSchem(result, meta = {}) {
  const { size, palette, volume } = result;
  const writer = new NBTWriter(Math.max(4096, volume.length + 4096));

  const blockData = [];
  for (let i = 0; i < volume.length; i++) writeVarInt(blockData, volume[i]);

  const paletteCompound = {};
  palette.forEach((name, index) => {
    paletteCompound[name] = nbt.int(index);
  });

  const root = nbt.compound({
    Version: nbt.int(2),
    DataVersion: nbt.int(meta.dataVersion || 3955),
    Metadata: nbt.compound({
      Name: nbt.string(meta.name || 'SunPixel'),
      Author: nbt.string(meta.author || 'SunPixel'),
      WEOffsetX: nbt.int(0),
      WEOffsetY: nbt.int(0),
      WEOffsetZ: nbt.int(0)
    }),
    Width: nbt.short(size.x),
    Height: nbt.short(size.y),
    Length: nbt.short(size.z),
    Offset: nbt.intArray([0, 0, 0]),
    Palette: nbt.compound(paletteCompound),
    BlockData: nbt.byteArray(Uint8Array.from(blockData)),
    BlockEntities: nbt.list(10, [])
  });

  writer.writeRoot(root);
  const compressed = await gzipCompress(writer.getBytes());
  return new Blob([compressed], { type: 'application/octet-stream' });
}

export { generateSchem, writeVarInt };
