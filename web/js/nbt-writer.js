// 最小化 NBT 二进制编码器 (用于 .schem 格式)
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

class NBTWriter {
  constructor() {
    this.buffer = new ArrayBuffer(65536);
    this.view = new DataView(this.buffer);
    this.offset = 0;
  }

  ensure(size) {
    if (this.offset + size > this.buffer.byteLength) {
      const newBuffer = new ArrayBuffer(this.buffer.byteLength * 2);
      new Uint8Array(newBuffer).set(new Uint8Array(this.buffer, 0, this.offset));
      this.buffer = newBuffer;
      this.view = new DataView(this.buffer);
    }
  }

  writeByte(value) {
    this.ensure(1);
    this.view.setInt8(this.offset, value);
    this.offset += 1;
  }

  writeShort(value) {
    this.ensure(2);
    this.view.setInt16(this.offset, value);
    this.offset += 2;
  }

  writeInt(value) {
    this.ensure(4);
    this.view.setInt32(this.offset, value);
    this.offset += 4;
  }

  writeLong(value) {
    this.ensure(8);
    this.view.setBigInt64(this.offset, BigInt(value));
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
    const encoder = new TextEncoder();
    const bytes = encoder.encode(value);
    this.writeShort(bytes.length);
    this.ensure(bytes.length);
    new Uint8Array(this.buffer, this.offset).set(bytes);
    this.offset += bytes.length;
  }

  writeByteArray(value) {
    this.writeInt(value.length);
    this.ensure(value.length);
    new Uint8Array(this.buffer, this.offset).set(value);
    this.offset += value.length;
  }

  writeIntArray(value) {
    this.writeInt(value.length);
    for (const v of value) {
      this.writeInt(v);
    }
  }

  writeLongArray(value) {
    this.writeInt(value.length);
    for (const v of value) {
      this.writeLong(v);
    }
  }

  writeTag(tag, name, value) {
    this.writeByte(tag);
    if (tag !== TAG_END) {
      this.writeString(name);
    }
    this.writeTagValue(tag, value);
  }

  writeTagValue(tag, value) {
    switch (tag) {
      case TAG_BYTE: this.writeByte(value); break;
      case TAG_SHORT: this.writeShort(value); break;
      case TAG_INT: this.writeInt(value); break;
      case TAG_LONG: this.writeLong(value); break;
      case TAG_FLOAT: this.writeFloat(value); break;
      case TAG_DOUBLE: this.writeDouble(value); break;
      case TAG_BYTE_ARRAY: this.writeByteArray(value); break;
      case TAG_STRING: this.writeString(value); break;
      case TAG_LIST: this.writeList(value); break;
      case TAG_COMPOUND: this.writeCompound(value); break;
      case TAG_INT_ARRAY: this.writeIntArray(value); break;
    }
  }

  writeList(value) {
    const { type, items } = value;
    this.writeByte(type);
    this.writeInt(items.length);
    for (const item of items) {
      this.writeTagValue(type, item);
    }
  }

  writeCompound(value) {
    if (!value) {
      this.writeByte(TAG_END);
      return;
    }
    for (const [name, val] of Object.entries(value)) {
      if (val === null || val === undefined) continue;
      const tag = this.getTagType(val);
      this.writeTag(tag, name, val.value !== undefined ? val.value : val);
    }
    this.writeByte(TAG_END);
  }

  getTagType(val) {
    if (val === null || val === undefined) return TAG_END;
    if (typeof val === 'object' && val.tag !== undefined) return val.tag;
    if (typeof val === 'object' && val.type !== undefined) return TAG_LIST;
    if (typeof val === 'object' && val.value !== undefined) return this.getTagType(val.value);
    if (typeof val === 'object' && !Array.isArray(val)) return TAG_COMPOUND;
    if (Array.isArray(val)) {
      if (val.byteArray) return TAG_BYTE_ARRAY;
      if (val.intArray) return TAG_INT_ARRAY;
      if (val.longArray) return TAG_LONG_ARRAY;
      return TAG_LIST;
    }
    if (typeof val === 'number') {
      if (Number.isInteger(val)) return TAG_INT;
      return TAG_DOUBLE;
    }
    if (typeof val === 'string') return TAG_STRING;
    if (typeof val === 'boolean') return TAG_BYTE;
    return TAG_END;
  }

  getBytes() {
    return new Uint8Array(this.buffer, 0, this.offset);
  }
}

// 使用 CompressionStream API 压缩数据
async function gzipCompress(data) {
  const cs = new CompressionStream('gzip');
  const writer = cs.writable.getWriter();
  writer.write(data);
  writer.close();
  const reader = cs.readable.getReader();
  const chunks = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  const totalLength = chunks.reduce((acc, c) => acc + c.length, 0);
  const result = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

export { NBTWriter, gzipCompress, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY, TAG_LONG_ARRAY };