"""独立的 NBT 校验脚本：用成熟的 nbtlib 解析 SunPixel 导出的文件，
再把结构还原成方块索引，交给 Node 测试逐像素比对。
这样导出的文件就被一个完全独立的实现验证过，而不是自己验自己。
"""
import gzip
import io
import json
import sys
from pathlib import Path

import nbtlib


def load(path: Path, byteorder: str = "big"):
    """Java 版是 gzip + 大端；基岩版 .mcstructure 是裸 NBT + 小端。"""
    raw = path.read_bytes()
    if byteorder == "big":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    return nbtlib.File.parse(io.BytesIO(raw), byteorder=byteorder)


def as_int_list(tag):
    return [int(v) for v in tag]


def read_varints(payload):
    out = []
    value = 0
    shift = 0
    for byte in payload:
        b = int(byte) & 0xFF
        value |= (b & 0x7F) << shift
        if b & 0x80:
            shift += 7
        else:
            out.append(value)
            value = 0
            shift = 0
    return out


def unpack_longs(longs, bits):
    mask = (1 << bits) - 1
    out = []
    total_bits = len(longs) * 64
    index = 0
    bit_pos = 0
    while bit_pos + bits <= total_bits:
        long_index = bit_pos // 64
        offset = bit_pos % 64
        chunk = int(longs[long_index]) & 0xFFFFFFFFFFFFFFFF
        value = chunk >> offset
        if offset + bits > 64:
            nxt = int(longs[long_index + 1]) & 0xFFFFFFFFFFFFFFFF
            value |= nxt << (64 - offset)
        out.append(value & mask)
        bit_pos += bits
        index += 1
    return out


def check_schem(path: Path):
    root = load(path)
    palette = {str(k): int(v) for k, v in root["Palette"].items()}
    blocks = read_varints(root["BlockData"])
    return {
        "width": int(root["Width"]),
        "height": int(root["Height"]),
        "length": int(root["Length"]),
        "version": int(root["Version"]),
        "paletteSize": len(palette),
        "palette": list(palette.keys()),
        "blocks": blocks,
        "blockEntities": len(root.get("BlockEntities", [])),
        "hasOffset": "Offset" in root,
        "paletteMax": int(root.get("PaletteMax", -1)),
    }


def check_litematic(path: Path):
    root = load(path)
    region = root["Regions"]["SunPixel"]
    palette = [str(entry["Name"]) for entry in region["BlockStatePalette"]]
    size = region["Size"]
    bits = max(2, (len(palette) - 1).bit_length())
    states = unpack_longs([int(v) for v in region["BlockStates"]], bits)
    volume = int(size["x"]) * int(size["y"]) * int(size["z"])
    return {
        "version": int(root["Version"]),
        "palette": palette,
        "size": [int(size["x"]), int(size["y"]), int(size["z"])],
        "totalBlocks": int(root["Metadata"]["TotalBlocks"]),
        "totalVolume": int(root["Metadata"]["TotalVolume"]),
        "enclosing": [int(root["Metadata"]["EnclosingSize"][k]) for k in ("x", "y", "z")],
        "states": states[:volume],
        "stateCount": len(states),
        "regionCount": int(root["Metadata"]["RegionCount"]),
    }


def check_mcstructure(path: Path):
    root = load(path, byteorder="little")
    indices = [int(v) for v in root["structure"]["block_indices"][0]]
    second = [int(v) for v in root["structure"]["block_indices"][1]]
    palette = [str(entry["name"]) for entry in root["structure"]["palette"]["default"]["block_palette"]]
    return {
        "formatVersion": int(root["format_version"]),
        "size": as_int_list(root["size"]),
        "palette": palette,
        "indices": indices,
        "secondLayer": second,
        "origin": as_int_list(root["structure_world_origin"]),
    }


def check_nbt(path: Path):
    """Java 结构方块文件：size 是 3 个 int 的列表，blocks 里每条带 pos 与 state。"""
    root = load(path)
    size = as_int_list(root["size"])
    sx, sy, sz = size
    palette = [str(entry["Name"]) for entry in root["palette"]]
    states = [0] * (sx * sy * sz)
    for entry in root["blocks"]:
        x, y, z = as_int_list(entry["pos"])
        states[(y * sz + z) * sx + x] = int(entry["state"])
    return {
        "size": size,
        "palette": palette,
        "states": states,
        "blockCount": len(root["blocks"]),
        "author": str(root.get("author", "")),
        "hasEntities": "entities" in root,
    }


def main():
    directory = Path(sys.argv[1])
    report = {}
    for name, fn in (
        ("schem", check_schem),
        ("litematic", check_litematic),
        ("mcstructure", check_mcstructure),
        ("nbt", check_nbt),
    ):
        path = directory / f"sample.{name}"
        try:
            report[name] = fn(path)
        except Exception as exc:  # noqa: BLE001
            report[name] = {"error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(report))


if __name__ == "__main__":
    main()
