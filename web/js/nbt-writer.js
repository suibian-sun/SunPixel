/**
 * 最小化 NBT 二进制编码器（大端序，Java Edition 规范）
 *
 * 相比旧版本修复了以下问题：
 *  - TAG_Long_Array 缺少写入分支，导致 litematic 的 BlockStates 完全丢失
 *  - 列表元素类型不再靠猜，统一使用显式类型节点，避免 mcstructure 的
 *    block_indices（List<IntArray>）被写成非法结构
 *  - 字符串长度超出 65535 时给出明确错误，而不是写出损坏的文件
 *  - 缓冲区扩容不再依赖单次翻倍，写入大结构时不会越界
 */

const TAG_END = 0;
const TAG_BYTE = 1;
const TAG_SHORT = 2;
const TAG_INT = 3;
const TAG_LONG = 4;
const TAG_FLOAT = 5;
const TAG_DOUBLE = 6;
const TAG_BYTE_ARRAY = 7;
const TAG_STRING = 8;
const TAG_LIST = 9;
const TAG_COMPOUND = 10;
const TAG_INT_ARRAY = 11;
const TAG_LONG_ARRAY = 12;

/** 显式类型节点构造器：写 NBT 时不再根据 JS 类型去猜标签类型 */
const nbt = {
  byte: (value) => ({ tag: TAG_BYTE, value: Number(value) }),
  short: (value) => ({ tag: TAG_SHORT, value: Number(value) }),
  int: (value) => ({ tag: TAG_INT, value: Number(value) }),
  long: (value) => ({ tag: TAG_LONG, value: typeof value === 'bigint' ? value : BigInt(Math.trunc(Number(value))) }),
  float: (value) => ({ tag: TAG_FLOAT, value: Number(value) }),
  double: (value) => ({ tag: TAG_DOUBLE, value: Number(value) }),
  string: (value) => ({ tag: TAG_STRING, value: String(value) }),
  byteArray: (value) => ({ tag: TAG_BYTE_ARRAY, value }),
  intArray: (value) => ({ tag: TAG_INT_ARRAY, value }),
  longArray: (value) => ({ tag: TAG_LONG_ARRAY, value }),
  /** 列表：type 为元素标签类型，items 为对应类型的裸值或节点 */
  list: (type, items) => ({ tag: TAG_LIST, type, items }),
  compound: (value) => ({ tag: TAG_COMPOUND, value }),
  /** 坐标/尺寸结构 {x,y,z} */
  vec: (x, y, z) => ({ tag: TAG_COMPOUND, value: { x: nbt.int(x), y: nbt.int(y), z: nbt.int(z) } })
};

class NBTWriter {
  constructor(initialSize = 1 << 16) {
    this.buffer = new ArrayBuffer(initialSize);
    this.view = new DataView(this.buffer);
    this.offset = 0;
  }

  ensure(size) {
    const needed = this.offset + size;
    if (needed <= this.buffer.byteLength) return;
    let capacity = this.buffer.byteLength;
    while (capacity < needed) capacity *= 2;
    const next = new ArrayBuffer(capacity);
    new Uint8Array(next).set(new Uint8Array(this.buffer, 0, this.offset));
    this.buffer = next;
    this.view = new DataView(next);
  }

  writeByte(value) {
    this.ensure(1);
    this.view.setInt8(this.offset, (value << 24) >> 24);
    this.offset += 1;
  }

  writeShort(value) {
    this.ensure(2);
    this.view.setInt16(this.offset, (value << 16) >> 16);
    this.offset += 2;
  }

  writeInt(value) {
    this.ensure(4);
    this.view.setInt32(this.offset, value | 0);
    this.offset += 4;
  }

  writeLong(value) {
    this.ensure(8);
    const big = typeof value === 'bigint' ? value : BigInt(Math.trunc(Number(value)));
    this.view.setBigInt64(this.offset, BigInt.asIntN(64, big));
    this.offset += 8;
  }

  writeFloat(value) {
    this.ensure(4);
    this.view.setFloat32(this.offset, value);
    this.offset += 4;
  }

  writeDouble(value) {
    this.ensure(8);
    this.view.setFloat64(this.offset, value);
    this.offset += 8;
  }

  writeString(value) {
    const bytes = new TextEncoder().encode(String(value));
    if (bytes.length > 0xffff) {
      throw new Error(`NBT 字符串超长（${bytes.length} 字节，上限 65535）`);
    }
    this.writeShort(bytes.length);
    this.ensure(bytes.length);
    new Uint8Array(this.buffer, this.offset, bytes.length).set(bytes);
    this.offset += bytes.length;
  }

  writeByteArray(value) {
    this.writeInt(value.length);
    this.ensure(value.length);
    const bytes = value instanceof Uint8Array ? value : Uint8Array.from(value, (v) => v & 0xff);
    new Uint8Array(this.buffer, this.offset, bytes.length).set(bytes);
    this.offset += bytes.length;
  }

  writeIntArray(value) {
    this.writeInt(value.length);
    for (let i = 0; i < value.length; i++) this.writeInt(value[i]);
  }

  writeLongArray(value) {
    this.writeInt(value.length);
    for (let i = 0; i < value.length; i++) this.writeLong(value[i]);
  }

  /** 写一个具名标签（根标签名字传空串） */
  writeTag(tag, name, node) {
    this.writeByte(tag);
    if (tag !== TAG_END) this.writeString(name);
    this.writePayload(tag, node);
  }

  writePayload(tag, node) {
    switch (tag) {
      case TAG_BYTE: this.writeByte(unwrap(node)); break;
      case TAG_SHORT: this.writeShort(unwrap(node)); break;
      case TAG_INT: this.writeInt(unwrap(node)); break;
      case TAG_LONG: this.writeLong(unwrap(node)); break;
      case TAG_FLOAT: this.writeFloat(unwrap(node)); break;
      case TAG_DOUBLE: this.writeDouble(unwrap(node)); break;
      case TAG_BYTE_ARRAY: this.writeByteArray(unwrap(node)); break;
      case TAG_STRING: this.writeString(unwrap(node)); break;
      case TAG_INT_ARRAY: this.writeIntArray(unwrap(node)); break;
      case TAG_LONG_ARRAY: this.writeLongArray(unwrap(node)); break;
      case TAG_LIST: this.writeList(node); break;
      case TAG_COMPOUND: this.writeCompound(unwrap(node)); break;
      default: throw new Error(`未知的 NBT 标签类型: ${tag}`);
    }
  }

  writeList(node) {
    const { type, items } = node;
    this.writeByte(items.length === 0 ? TAG_END : type);
    this.writeInt(items.length);
    for (const item of items) this.writePayload(type, item);
  }

  writeCompound(value) {
    for (const [name, child] of Object.entries(value || {})) {
      if (child === undefined || child === null) continue;
      if (typeof child.tag !== 'number') {
        throw new Error(`字段 ${name} 不是合法的 NBT 节点，请使用 nbt.* 构造器`);
      }
      this.writeTag(child.tag, name, child);
    }
    this.writeByte(TAG_END);
  }

  /** 写一个完整的根复合标签 */
  writeRoot(compoundNode) {
    this.writeTag(TAG_COMPOUND, '', compoundNode);
  }

  getBytes() {
    return new Uint8Array(this.buffer, 0, this.offset);
  }
}

function unwrap(node) {
  return node && typeof node === 'object' && 'value' in node ? node.value : node;
}

/** 使用 CompressionStream 做 gzip 压缩（浏览器与 Node 18+ 均可用） */
async function gzipCompress(data) {
  if (typeof CompressionStream !== 'function') {
    throw new Error('当前环境不支持 CompressionStream，无法压缩 NBT 数据');
  }
  const source = data instanceof Uint8Array ? data : new Uint8Array(data);
  const stream = new Blob([source]).stream().pipeThrough(new CompressionStream('gzip'));
  const buffer = await new Response(stream).arrayBuffer();
  return new Uint8Array(buffer);
}

export {
  NBTWriter,
  nbt,
  gzipCompress,
  TAG_END,
  TAG_BYTE,
  TAG_SHORT,
  TAG_INT,
  TAG_LONG,
  TAG_FLOAT,
  TAG_DOUBLE,
  TAG_BYTE_ARRAY,
  TAG_STRING,
  TAG_LIST,
  TAG_COMPOUND,
  TAG_INT_ARRAY,
  TAG_LONG_ARRAY
};
