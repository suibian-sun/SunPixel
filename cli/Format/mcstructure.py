import struct
import json
import os
import math
import zlib
import time
import sys
from enum import IntEnum
from typing import Dict, List, Tuple, Optional, Any, BinaryIO, Union
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from collections import OrderedDict
import hashlib
import io
import base64

class Color:
    """终端颜色枚举"""
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    GRAY = '\033[90m'
    DARK_RED = '\033[31m'
    DARK_GREEN = '\033[32m'
    DARK_YELLOW = '\033[33m'
    DARK_BLUE = '\033[34m'
    DARK_MAGENTA = '\033[35m'
    DARK_CYAN = '\033[36m'

@dataclass
class Size:
    """结构尺寸"""
    width: int = 0
    height: int = 0
    length: int = 0
    
    def get_volume(self) -> int:
        return self.width * self.height * self.length
    
    def get_chunk_x_count(self) -> int:
        return (self.width + 15) // 16
    
    def get_chunk_z_count(self) -> int:
        return (self.length + 15) // 16
    
    def __str__(self) -> str:
        return f"{self.width}x{self.height}x{self.length}"

@dataclass
class Vector3:
    """三维向量"""
    x: int = 0
    y: int = 0
    z: int = 0
    
    def __getitem__(self, index: int) -> int:
        if index == 0: return self.x
        elif index == 1: return self.y
        elif index == 2: return self.z
        raise IndexError(f"Index {index} out of range")
    
    def __setitem__(self, index: int, value: int):
        if index == 0: self.x = value
        elif index == 1: self.y = value
        elif index == 2: self.z = value
        else: raise IndexError(f"Index {index} out of range")
    
    def __add__(self, other: 'Vector3') -> 'Vector3':
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other: 'Vector3') -> 'Vector3':
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar: int) -> 'Vector3':
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def __neg__(self) -> 'Vector3':
        return Vector3(-self.x, -self.y, -self.z)

class Origin(Vector3):
    """世界原点"""
    pass

class Offset(Vector3):
    """偏移量"""
    def X(self) -> int:
        return self.x
    
    def Y(self) -> int:
        return self.y
    
    def Z(self) -> int:
        return self.z

@dataclass
class ChunkPos:
    """区块位置"""
    x: int = 0
    z: int = 0
    
    def X(self) -> int:
        return self.x
    
    def Z(self) -> int:
        return self.z
    
    def __hash__(self):
        return hash((self.x, self.z))
    
    def __eq__(self, other):
        if not isinstance(other, ChunkPos):
            return False
        return self.x == other.x and self.z == other.z

@dataclass
class BlockPos:
    """方块位置"""
    x: int = 0
    y: int = 0
    z: int = 0
    
    def X(self) -> int:
        return self.x
    
    def Y(self) -> int:
        return self.y
    
    def Z(self) -> int:
        return self.z
    
    def __hash__(self):
        return hash((self.x, self.y, self.z))
    
    def __eq__(self, other):
        if not isinstance(other, BlockPos):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z

@dataclass
class SubChunkPos:
    """子区块位置"""
    x: int = 0
    y: int = 0
    z: int = 0
    
    def X(self) -> int:
        return self.x
    
    def Y(self) -> int:
        return self.y
    
    def Z(self) -> int:
        return self.z

class NBTType(IntEnum):
    """NBT标签类型"""
    TAG_End = 0
    TAG_Byte = 1
    TAG_Short = 2
    TAG_Int = 3
    TAG_Long = 4
    TAG_Float = 5
    TAG_Double = 6
    TAG_Byte_Array = 7
    TAG_String = 8
    TAG_List = 9
    TAG_Compound = 10
    TAG_Int_Array = 11
    TAG_Long_Array = 12

class DimensionID(IntEnum):
    """维度ID"""
    OVERWORLD = 0
    NETHER = 1
    END = 2

class ProgressDisplay:
    """进度显示类"""
    def __init__(self, total: int, description: str, config=None):
        self.total = total
        self.description = description
        self.config = config
        self.current = 0
        self.start_time = time.time()
        self.use_color = config.getboolean('ui', 'colored_output', True) if config else True
        self.last_update = 0
        self.language_manager = None
        if config and hasattr(config, 'get_language_manager'):
            self.language_manager = config.get_language_manager()
        
    def get_text(self, key: str, default: Optional[str] = None) -> str:
        """获取翻译文本"""
        if self.language_manager:
            return self.language_manager.get(key, default)
        return default if default is not None else key
        
    def update(self, value: int):
        """更新进度并显示"""
        self.current = value
        current_time = time.time()
        
        # 限制更新频率
        if current_time - self.last_update >= 0.25 or value >= self.total:
            self.last_update = current_time
            self._display()
            
    def increment(self, value: int = 1):
        """增加进度"""
        self.update(self.current + value)
        
    def complete(self):
        """完成进度显示"""
        self.current = self.total
        self._display()
        sys.stdout.write('\n')
        sys.stdout.flush()
        
    def _display(self):
        """显示进度条"""
        progress = min(100.0, (self.current / self.total) * 100) if self.total > 0 else 100.0
        bar_length = 30
        filled_length = int(bar_length * self.current // self.total) if self.total > 0 else bar_length
        
        if self.use_color:
            bar = f'{Color.GREEN}█{Color.RESET}' * filled_length + f'{Color.GRAY}░{Color.RESET}' * (bar_length - filled_length)
        else:
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        elapsed = time.time() - self.start_time
        if self.current > 0 and elapsed > 0:
            speed = self.current / elapsed
            eta = (self.total - self.current) / speed if speed > 0 else 0
            time_info = f" [{elapsed:.1f}s, {speed:.1f}块/s, ETA: {eta:.1f}s]"
        else:
            time_info = ""
            
        sys.stdout.write(f'\r📊 {self.description}: [{bar}] {self.current}/{self.total} ({progress:.1f}%){time_info}')
        sys.stdout.flush()

class NBTReader:
    """完整的NBT读取器"""
    def __init__(self, little_endian: bool = True):
        self.little_endian = little_endian
        self.endian = '<' if little_endian else '>'
    
    def read_tag(self, file_obj: BinaryIO) -> Tuple[NBTType, str]:
        """读取标签类型和名称"""
        try:
            tag_byte = file_obj.read(1)
            if not tag_byte:
                return NBTType.TAG_End, ""
            tag_id = struct.unpack('B', tag_byte)[0]
            
            if tag_id == NBTType.TAG_End:
                return NBTType.TAG_End, ""
            
            name_length_data = file_obj.read(2)
            if len(name_length_data) < 2:
                return NBTType.TAG_End, ""
            name_length = struct.unpack(f'{self.endian}H', name_length_data)[0]
            
            name_data = file_obj.read(name_length)
            if len(name_data) < name_length:
                return NBTType.TAG_End, ""
            
            name = name_data.decode('utf-8')
            return NBTType(tag_id), name
            
        except Exception as e:
            raise ValueError(f"读取标签失败: {e}")
    
    def read_tag_int32(self, file_obj: BinaryIO) -> int:
        """读取32位整数"""
        data = file_obj.read(4)
        if len(data) < 4:
            raise ValueError("读取int32数据不完整")
        return struct.unpack(f'{self.endian}i', data)[0]
    
    def read_tag_byte(self, file_obj: BinaryIO) -> int:
        """读取字节"""
        data = file_obj.read(1)
        if not data:
            raise ValueError("读取byte数据不完整")
        return struct.unpack('B', data)[0]
    
    def read_tag_short(self, file_obj: BinaryIO) -> int:
        """读取短整数"""
        data = file_obj.read(2)
        if len(data) < 2:
            raise ValueError("读取short数据不完整")
        return struct.unpack(f'{self.endian}h', data)[0]
    
    def read_tag_long(self, file_obj: BinaryIO) -> int:
        """读取长整数"""
        data = file_obj.read(8)
        if len(data) < 8:
            raise ValueError("读取long数据不完整")
        return struct.unpack(f'{self.endian}q', data)[0]
    
    def read_tag_float(self, file_obj: BinaryIO) -> float:
        """读取浮点数"""
        data = file_obj.read(4)
        if len(data) < 4:
            raise ValueError("读取float数据不完整")
        return struct.unpack(f'{self.endian}f', data)[0]
    
    def read_tag_double(self, file_obj: BinaryIO) -> float:
        """读取双精度浮点数"""
        data = file_obj.read(8)
        if len(data) < 8:
            raise ValueError("读取double数据不完整")
        return struct.unpack(f'{self.endian}d', data)[0]
    
    def read_tag_string(self, file_obj: BinaryIO) -> str:
        """读取字符串"""
        length_data = file_obj.read(2)
        if len(length_data) < 2:
            raise ValueError("读取string长度数据不完整")
        length = struct.unpack(f'{self.endian}H', length_data)[0]
        
        string_data = file_obj.read(length)
        if len(string_data) < length:
            raise ValueError("读取string数据不完整")
        
        return string_data.decode('utf-8')
    
    def read_tag_byte_array(self, file_obj: BinaryIO) -> bytes:
        """读取字节数组"""
        length = self.read_tag_int32(file_obj)
        if length < 0:
            return b""
        
        data = file_obj.read(length)
        if len(data) < length:
            raise ValueError("读取byte array数据不完整")
        
        return data
    
    def read_tag_int_array(self, file_obj: BinaryIO) -> List[int]:
        """读取整数数组"""
        length = self.read_tag_int32(file_obj)
        if length <= 0:
            return []
        
        result = []
        for _ in range(length):
            result.append(self.read_tag_int32(file_obj))
        return result
    
    def read_tag_long_array(self, file_obj: BinaryIO) -> List[int]:
        """读取长整数数组"""
        length = self.read_tag_int32(file_obj)
        if length <= 0:
            return []
        
        result = []
        for _ in range(length):
            result.append(self.read_tag_long(file_obj))
        return result
    
    def read_tag_list(self, file_obj: BinaryIO) -> List[Any]:
        """读取列表"""
        try:
            type_byte = file_obj.read(1)
            if not type_byte:
                return []
            element_type = NBTType(struct.unpack('B', type_byte)[0])
            
            length = self.read_tag_int32(file_obj)
            if length <= 0:
                return []
            
            result = []
            for _ in range(length):
                if element_type == NBTType.TAG_Byte:
                    result.append(self.read_tag_byte(file_obj))
                elif element_type == NBTType.TAG_Short:
                    result.append(self.read_tag_short(file_obj))
                elif element_type == NBTType.TAG_Int:
                    result.append(self.read_tag_int32(file_obj))
                elif element_type == NBTType.TAG_Long:
                    result.append(self.read_tag_long(file_obj))
                elif element_type == NBTType.TAG_Float:
                    result.append(self.read_tag_float(file_obj))
                elif element_type == NBTType.TAG_Double:
                    result.append(self.read_tag_double(file_obj))
                elif element_type == NBTType.TAG_String:
                    result.append(self.read_tag_string(file_obj))
                elif element_type == NBTType.TAG_Byte_Array:
                    result.append(self.read_tag_byte_array(file_obj))
                elif element_type == NBTType.TAG_Int_Array:
                    result.append(self.read_tag_int_array(file_obj))
                elif element_type == NBTType.TAG_Long_Array:
                    result.append(self.read_tag_long_array(file_obj))
                elif element_type == NBTType.TAG_List:
                    result.append(self.read_tag_list(file_obj))
                elif element_type == NBTType.TAG_Compound:
                    result.append(self.read_tag_compound(file_obj))
                else:
                    raise ValueError(f"不支持的列表元素类型: {element_type}")
            
            return result
            
        except Exception as e:
            raise ValueError(f"读取列表失败: {e}")
    
    def read_tag_compound(self, file_obj: BinaryIO) -> Dict[str, Any]:
        """读取复合标签"""
        result = OrderedDict()
        
        while True:
            try:
                tag_type, tag_name = self.read_tag(file_obj)
                if tag_type == NBTType.TAG_End:
                    break
                
                if tag_type == NBTType.TAG_Byte:
                    result[tag_name] = self.read_tag_byte(file_obj)
                elif tag_type == NBTType.TAG_Short:
                    result[tag_name] = self.read_tag_short(file_obj)
                elif tag_type == NBTType.TAG_Int:
                    result[tag_name] = self.read_tag_int32(file_obj)
                elif tag_type == NBTType.TAG_Long:
                    result[tag_name] = self.read_tag_long(file_obj)
                elif tag_type == NBTType.TAG_Float:
                    result[tag_name] = self.read_tag_float(file_obj)
                elif tag_type == NBTType.TAG_Double:
                    result[tag_name] = self.read_tag_double(file_obj)
                elif tag_type == NBTType.TAG_String:
                    result[tag_name] = self.read_tag_string(file_obj)
                elif tag_type == NBTType.TAG_Byte_Array:
                    result[tag_name] = self.read_tag_byte_array(file_obj)
                elif tag_type == NBTType.TAG_Int_Array:
                    result[tag_name] = self.read_tag_int_array(file_obj)
                elif tag_type == NBTType.TAG_Long_Array:
                    result[tag_name] = self.read_tag_long_array(file_obj)
                elif tag_type == NBTType.TAG_List:
                    result[tag_name] = self.read_tag_list(file_obj)
                elif tag_type == NBTType.TAG_Compound:
                    result[tag_name] = self.read_tag_compound(file_obj)
                else:
                    raise ValueError(f"不支持的标签类型: {tag_type}")
                    
            except Exception as e:
                raise ValueError(f"读取复合标签失败: {e}")
        
        return result
    
    def skip_tag_value(self, file_obj: BinaryIO, tag_type: NBTType):
        """跳过标签值"""
        try:
            if tag_type == NBTType.TAG_Byte:
                file_obj.read(1)
            elif tag_type == NBTType.TAG_Short:
                file_obj.read(2)
            elif tag_type == NBTType.TAG_Int:
                file_obj.read(4)
            elif tag_type == NBTType.TAG_Long:
                file_obj.read(8)
            elif tag_type == NBTType.TAG_Float:
                file_obj.read(4)
            elif tag_type == NBTType.TAG_Double:
                file_obj.read(8)
            elif tag_type == NBTType.TAG_Byte_Array:
                length = self.read_tag_int32(file_obj)
                if length > 0:
                    file_obj.read(length)
            elif tag_type == NBTType.TAG_String:
                length_data = file_obj.read(2)
                if len(length_data) == 2:
                    length = struct.unpack(f'{self.endian}H', length_data)[0]
                    file_obj.read(length)
            elif tag_type == NBTType.TAG_Int_Array:
                length = self.read_tag_int32(file_obj)
                if length > 0:
                    file_obj.read(4 * length)
            elif tag_type == NBTType.TAG_Long_Array:
                length = self.read_tag_int32(file_obj)
                if length > 0:
                    file_obj.read(8 * length)
            elif tag_type == NBTType.TAG_List:
                type_byte = file_obj.read(1)
                if type_byte:
                    element_type = NBTType(struct.unpack('B', type_byte)[0])
                    length = self.read_tag_int32(file_obj)
                    for _ in range(length):
                        self.skip_tag_value(file_obj, element_type)
            elif tag_type == NBTType.TAG_Compound:
                while True:
                    sub_type, sub_name = self.read_tag(file_obj)
                    if sub_type == NBTType.TAG_End:
                        break
                    self.skip_tag_value(file_obj, sub_type)
        except Exception:
            pass

class NBTWriter:
    """NBT写入器"""
    def __init__(self, little_endian: bool = True):
        self.little_endian = little_endian
        self.endian = '<' if little_endian else '>'
    
    def write_tag(self, file_obj: BinaryIO, tag_type: NBTType, name: str = ""):
        """写入标签类型和名称"""
        file_obj.write(struct.pack('B', tag_type.value))
        if tag_type != NBTType.TAG_End:
            name_bytes = name.encode('utf-8')
            file_obj.write(struct.pack(f'{self.endian}H', len(name_bytes)))
            file_obj.write(name_bytes)
    
    def write_tag_int32(self, file_obj: BinaryIO, value: int):
        """写入32位整数"""
        file_obj.write(struct.pack(f'{self.endian}i', value))
    
    def write_tag_byte(self, file_obj: BinaryIO, value: int):
        """写入字节"""
        file_obj.write(struct.pack('B', value & 0xFF))
    
    def write_tag_short(self, file_obj: BinaryIO, value: int):
        """写入短整数"""
        file_obj.write(struct.pack(f'{self.endian}h', value))
    
    def write_tag_long(self, file_obj: BinaryIO, value: int):
        """写入长整数"""
        file_obj.write(struct.pack(f'{self.endian}q', value))
    
    def write_tag_float(self, file_obj: BinaryIO, value: float):
        """写入浮点数"""
        file_obj.write(struct.pack(f'{self.endian}f', value))
    
    def write_tag_double(self, file_obj: BinaryIO, value: float):
        """写入双精度浮点数"""
        file_obj.write(struct.pack(f'{self.endian}d', value))
    
    def write_tag_string(self, file_obj: BinaryIO, value: str):
        """写入字符串"""
        value_bytes = value.encode('utf-8')
        file_obj.write(struct.pack(f'{self.endian}H', len(value_bytes)))
        file_obj.write(value_bytes)
    
    def write_tag_byte_array(self, file_obj: BinaryIO, value: bytes):
        """写入字节数组"""
        self.write_tag_int32(file_obj, len(value))
        file_obj.write(value)
    
    def write_tag_int_array(self, file_obj: BinaryIO, value: List[int]):
        """写入整数数组"""
        self.write_tag_int32(file_obj, len(value))
        for item in value:
            self.write_tag_int32(file_obj, item)
    
    def write_tag_long_array(self, file_obj: BinaryIO, value: List[int]):
        """写入长整数数组"""
        self.write_tag_int32(file_obj, len(value))
        for item in value:
            self.write_tag_long(file_obj, item)
    
    def write_tag_list(self, file_obj: BinaryIO, value: List[Any], element_type: Optional[NBTType] = None):
        """写入列表"""
        if not value:
            self.write_tag_byte(file_obj, NBTType.TAG_End.value)
            self.write_tag_int32(file_obj, 0)
            return
        
        if element_type is None:
            # 自动检测元素类型
            first_item = value[0]
            if isinstance(first_item, int) and -128 <= first_item <= 127:
                element_type = NBTType.TAG_Byte
            elif isinstance(first_item, int) and -32768 <= first_item <= 32767:
                element_type = NBTType.TAG_Short
            elif isinstance(first_item, int) and -2147483648 <= first_item <= 2147483647:
                element_type = NBTType.TAG_Int
            elif isinstance(first_item, int):
                element_type = NBTType.TAG_Long
            elif isinstance(first_item, float):
                element_type = NBTType.TAG_Double
            elif isinstance(first_item, str):
                element_type = NBTType.TAG_String
            elif isinstance(first_item, bytes):
                element_type = NBTType.TAG_Byte_Array
            elif isinstance(first_item, list):
                element_type = NBTType.TAG_List
            elif isinstance(first_item, dict):
                element_type = NBTType.TAG_Compound
            else:
                raise ValueError(f"不支持的元素类型: {type(first_item)}")
        
        self.write_tag_byte(file_obj, element_type.value)
        self.write_tag_int32(file_obj, len(value))
        
        for item in value:
            if element_type == NBTType.TAG_Byte:
                self.write_tag_byte(file_obj, item)
            elif element_type == NBTType.TAG_Short:
                self.write_tag_short(file_obj, item)
            elif element_type == NBTType.TAG_Int:
                self.write_tag_int32(file_obj, item)
            elif element_type == NBTType.TAG_Long:
                self.write_tag_long(file_obj, item)
            elif element_type == NBTType.TAG_Float:
                self.write_tag_float(file_obj, item)
            elif element_type == NBTType.TAG_Double:
                self.write_tag_double(file_obj, item)
            elif element_type == NBTType.TAG_String:
                self.write_tag_string(file_obj, item)
            elif element_type == NBTType.TAG_Byte_Array:
                self.write_tag_byte_array(file_obj, item)
            elif element_type == NBTType.TAG_List:
                self.write_tag_list(file_obj, item)
            elif element_type == NBTType.TAG_Compound:
                self.write_tag_compound(file_obj, item)
    
    def write_tag_compound(self, file_obj: BinaryIO, value: Dict[str, Any]):
        """写入复合标签"""
        for key, val in value.items():
            if isinstance(val, int) and -128 <= val <= 127:
                self.write_tag(file_obj, NBTType.TAG_Byte, key)
                self.write_tag_byte(file_obj, val)
            elif isinstance(val, int) and -32768 <= val <= 32767:
                self.write_tag(file_obj, NBTType.TAG_Short, key)
                self.write_tag_short(file_obj, val)
            elif isinstance(val, int) and -2147483648 <= val <= 2147483647:
                self.write_tag(file_obj, NBTType.TAG_Int, key)
                self.write_tag_int32(file_obj, val)
            elif isinstance(val, int):
                self.write_tag(file_obj, NBTType.TAG_Long, key)
                self.write_tag_long(file_obj, val)
            elif isinstance(val, float):
                self.write_tag(file_obj, NBTType.TAG_Double, key)
                self.write_tag_double(file_obj, val)
            elif isinstance(val, str):
                self.write_tag(file_obj, NBTType.TAG_String, key)
                self.write_tag_string(file_obj, val)
            elif isinstance(val, bytes):
                self.write_tag(file_obj, NBTType.TAG_Byte_Array, key)
                self.write_tag_byte_array(file_obj, val)
            elif isinstance(val, list):
                self.write_tag(file_obj, NBTType.TAG_List, key)
                self.write_tag_list(file_obj, val)
            elif isinstance(val, dict):
                self.write_tag(file_obj, NBTType.TAG_Compound, key)
                self.write_tag_compound(file_obj, val)
            else:
                raise ValueError(f"不支持的值类型: {type(val)}")
        
        self.write_tag(file_obj, NBTType.TAG_End)

class BlockRegistry:
    """方块注册表"""
    # 基础方块映射
    BLOCK_NAME_TO_RUNTIME_ID = {
        "minecraft:air": 0,
        "minecraft:stone": 1,
        "minecraft:grass": 2,
        "minecraft:dirt": 3,
        "minecraft:cobblestone": 4,
        "minecraft:planks": 5,
        "minecraft:bedrock": 7,
        "minecraft:water": 9,
        "minecraft:lava": 11,
        "minecraft:sand": 12,
        "minecraft:gravel": 13,
        "minecraft:gold_ore": 14,
        "minecraft:iron_ore": 15,
        "minecraft:coal_ore": 16,
        "minecraft:log": 17,
        "minecraft:leaves": 18,
        "minecraft:glass": 20,
        "minecraft:lapis_ore": 21,
        "minecraft:lapis_block": 22,
        "minecraft:sandstone": 24,
        "minecraft:wool": 35,
        "minecraft:gold_block": 41,
        "minecraft:iron_block": 42,
        "minecraft:stone_slab": 44,
        "minecraft:brick_block": 45,
        "minecraft:tnt": 46,
        "minecraft:bookshelf": 47,
        "minecraft:mossy_cobblestone": 48,
        "minecraft:obsidian": 49,
        "minecraft:diamond_ore": 56,
        "minecraft:diamond_block": 57,
        "minecraft:farmland": 60,
        "minecraft:furnace": 61,
        "minecraft:redstone_ore": 73,
        "minecraft:ice": 79,
        "minecraft:snow_block": 80,
        "minecraft:cactus": 81,
        "minecraft:clay": 82,
        "minecraft:jukebox": 84,
        "minecraft:pumpkin": 86,
        "minecraft:netherrack": 87,
        "minecraft:soul_sand": 88,
        "minecraft:glowstone": 89,
        "minecraft:melon_block": 103,
        "minecraft:mycelium": 110,
        "minecraft:nether_brick": 112,
        "minecraft:end_stone": 121,
        "minecraft:emerald_ore": 129,
        "minecraft:emerald_block": 133,
        "minecraft:beacon": 138,
        "minecraft:redstone_block": 152,
        "minecraft:quartz_ore": 153,
        "minecraft:quartz_block": 155,
        "minecraft:stained_hardened_clay": 159,
        "minecraft:sea_lantern": 169,
        "minecraft:hay_block": 170,
        "minecraft:coal_block": 173,
        "minecraft:packed_ice": 174,
        "minecraft:slime": 165,
        "minecraft:concrete": 236,
        "minecraft:concrete_powder": 237,
        "minecraft:white_concrete": 236,
        "minecraft:orange_concrete": 236,
        "minecraft:magenta_concrete": 236,
        "minecraft:light_blue_concrete": 236,
        "minecraft:yellow_concrete": 236,
        "minecraft:lime_concrete": 236,
        "minecraft:pink_concrete": 236,
        "minecraft:gray_concrete": 236,
        "minecraft:light_gray_concrete": 236,
        "minecraft:cyan_concrete": 236,
        "minecraft:purple_concrete": 236,
        "minecraft:blue_concrete": 236,
        "minecraft:brown_concrete": 236,
        "minecraft:green_concrete": 236,
        "minecraft:red_concrete": 236,
        "minecraft:black_concrete": 236,
    }
    
    BLOCK_RUNTIME_ID_TO_NAME = {v: k for k, v in BLOCK_NAME_TO_RUNTIME_ID.items()}
    
    # 方块状态到runtime_id的映射
    STATE_TO_RUNTIME_ID = {}
    
    @classmethod
    def state_to_runtime_id(cls, name: str, properties: Dict[str, Any]) -> Tuple[int, bool]:
        """将方块状态转换为runtime_id"""
        base_id = cls.BLOCK_NAME_TO_RUNTIME_ID.get(name, 0)
        
        # 创建状态键
        if properties:
            state_key = name + ":" + json.dumps(properties, sort_keys=True)
            if state_key in cls.STATE_TO_RUNTIME_ID:
                return cls.STATE_TO_RUNTIME_ID[state_key], True
            
            # 为不同状态分配新的runtime_id
            new_id = base_id + len(properties) * 1000  # 简化的映射
            cls.STATE_TO_RUNTIME_ID[state_key] = new_id
            cls.BLOCK_RUNTIME_ID_TO_NAME[new_id] = name
            return new_id, True
        
        return base_id, base_id != 0
    
    @classmethod
    def runtime_id_to_state(cls, runtime_id: int) -> Tuple[str, Dict[str, Any], bool]:
        """将runtime_id转换为方块状态"""
        name = cls.BLOCK_RUNTIME_ID_TO_NAME.get(runtime_id, "minecraft:air")
        
        # 查找对应的状态
        for state_key, rid in cls.STATE_TO_RUNTIME_ID.items():
            if rid == runtime_id:
                if ":" in state_key:
                    name_part, props_str = state_key.split(":", 1)
                    try:
                        properties = json.loads(props_str)
                        return name_part, properties, True
                    except:
                        pass
        
        return name, {}, name != "minecraft:air"

class SubChunk:
    """子区块类"""
    def __init__(self, default_block_id: int = 0):
        # 使用3D数组存储方块runtime_id
        self.blocks = np.full((16, 16, 16), default_block_id, dtype=np.uint32)
        self.block_entities = {}  # 存储方块实体数据
        
    def set_block(self, x: int, y: int, z: int, layer: int, block_runtime_id: int):
        """设置方块"""
        if 0 <= x < 16 and 0 <= y < 16 and 0 <= z < 16:
            self.blocks[x, y, z] = block_runtime_id
    
    def get_block(self, x: int, y: int, z: int, layer: int) -> int:
        """获取方块"""
        if 0 <= x < 16 and 0 <= y < 16 and 0 <= z < 16:
            return self.blocks[x, y, z]
        return 0
    
    def block(self, x: int, y: int, z: int, layer: int) -> int:
        """获取方块（别名）"""
        return self.get_block(x, y, z, layer)
    
    def set_block_entity(self, x: int, y: int, z: int, nbt_data: Dict[str, Any]):
        """设置方块实体"""
        key = (x, y, z)
        self.block_entities[key] = nbt_data
    
    def get_block_entity(self, x: int, y: int, z: int) -> Optional[Dict[str, Any]]:
        """获取方块实体"""
        key = (x, y, z)
        return self.block_entities.get(key)

class Chunk:
    """区块类"""
    def __init__(self, default_block_id: int = 0, range_y: int = 384):
        self.range_y = range_y
        self.sub_chunks = {}  # y坐标到SubChunk的映射
        self.block_entities = {}  # 全局方块实体数据
        self.entities = []  # 实体数据
        self.height_map = None  # 高度图
        
    def set_block(self, local_x: int, local_y: int, local_z: int, layer: int, block_runtime_id: int):
        """设置方块"""
        sub_chunk_y = local_y // 16
        if sub_chunk_y not in self.sub_chunks:
            self.sub_chunks[sub_chunk_y] = SubChunk()
        
        sub_chunk = self.sub_chunks[sub_chunk_y]
        sub_y = local_y % 16
        sub_chunk.set_block(local_x, sub_y, local_z, layer, block_runtime_id)
    
    def get_block(self, local_x: int, local_y: int, local_z: int, layer: int) -> int:
        """获取方块"""
        sub_chunk_y = local_y // 16
        if sub_chunk_y in self.sub_chunks:
            sub_chunk = self.sub_chunks[sub_chunk_y]
            sub_y = local_y % 16
            return sub_chunk.get_block(local_x, sub_y, local_z, layer)
        return 0
    
    def set_block_entity(self, local_x: int, local_y: int, local_z: int, nbt_data: Dict[str, Any]):
        """设置方块实体"""
        key = (local_x, local_y, local_z)
        self.block_entities[key] = nbt_data
    
    def get_block_entity(self, local_x: int, local_y: int, local_z: int) -> Optional[Dict[str, Any]]:
        """获取方块实体"""
        key = (local_x, local_y, local_z)
        return self.block_entities.get(key)

class MCStructure:
    """MCStructure 文件处理类"""
    
    # 常量
    AIR_RUNTIME_ID = 0
    UNKNOWN_BLOCK_RUNTIME_ID = 1
    
    def __init__(self, config=None):
        self.config = config
        self.file_path = None
        self.file_handle = None
        self.size = Size()
        self.original_size = Size()
        self.format_version = 0
        self.origin = Origin()
        self.offset = Offset()
        self.entity_nbt = []
        self.block_nbt = {}
        self.palette = {}  # index -> runtime_id
        self.reverse_palette = {}  # runtime_id -> index
        self.offset_pos = Offset()
        self.block_index_tag_offset = 0
        self.language_manager = None
        self.block_registry = BlockRegistry()
        
        if config and hasattr(config, 'get_language_manager'):
            self.language_manager = config.get_language_manager()
    
    def get_text(self, key: str, default: Optional[str] = None) -> str:
        """获取翻译文本"""
        if self.language_manager:
            return self.language_manager.get(key, default)
        return default if default is not None else key
    
    def from_file(self, file_path: str) -> bool:
        """从文件加载MCStructure"""
        self.file_path = file_path
        
        loading_msg = self.get_text('mcstructure.loading', '正在加载MCStructure文件...')
        print(f"{Color.CYAN}📁 {loading_msg}{Color.RESET}")
        
        try:
            self.file_handle = open(file_path, 'rb')
            reader = NBTReader(little_endian=True)
            
            # 读取根标签
            root_type, root_name = reader.read_tag(self.file_handle)
            if root_type != NBTType.TAG_Compound:
                error_msg = self.get_text('mcstructure.invalid_root_tag', '无效的根标签类型')
                print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
                return False
            
            # 解析根标签内容
            self._parse_root_compound(reader)
            
            # 验证必要数据
            if self.block_index_tag_offset == 0:
                error_msg = self.get_text('mcstructure.invalid_file', '无效的MCStructure文件')
                print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
                return False
            
            loaded_msg = self.get_text('mcstructure.loaded', 'MCStructure文件加载成功')
            print(f"{Color.GREEN}✅ {loaded_msg} ({self.original_size}){Color.RESET}")
            return True
            
        except Exception as e:
            error_msg = self.get_text('mcstructure.load_failed', '加载MCStructure文件失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return False
    
    def _parse_root_compound(self, reader: NBTReader):
        """解析根复合标签"""
        while True:
            tag_type, tag_name = reader.read_tag(self.file_handle)
            if tag_type == NBTType.TAG_End:
                break
            
            if tag_name == "format_version":
                if tag_type != NBTType.TAG_Int:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                self.format_version = reader.read_tag_int32(self.file_handle)
                
            elif tag_name == "size":
                if tag_type != NBTType.TAG_List:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                size_list = reader.read_tag_list(self.file_handle)
                if len(size_list) >= 3:
                    self.size.width = int(size_list[0])
                    self.size.height = int(size_list[1])
                    self.size.length = int(size_list[2])
                    self.original_size.width = self.size.width
                    self.original_size.height = self.size.height
                    self.original_size.length = self.size.length
                    
            elif tag_name == "structure_world_origin":
                if tag_type != NBTType.TAG_List:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                origin_list = reader.read_tag_list(self.file_handle)
                if len(origin_list) >= 3:
                    self.origin.x = int(origin_list[0])
                    self.origin.y = int(origin_list[1])
                    self.origin.z = int(origin_list[2])
                    
            elif tag_name == "structure":
                if tag_type != NBTType.TAG_Compound:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                self._parse_structure_compound(reader)
                
            else:
                reader.skip_tag_value(self.file_handle, tag_type)
    
    def _parse_structure_compound(self, reader: NBTReader):
        """解析structure复合标签"""
        while True:
            tag_type, tag_name = reader.read_tag(self.file_handle)
            if tag_type == NBTType.TAG_End:
                break
            
            if tag_name == "block_indices":
                if tag_type != NBTType.TAG_List:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                
                # 记录block_indices的位置
                self.block_index_tag_offset = self.file_handle.tell()
                
                # 跳过block_indices（两层列表）
                element_type = NBTType(struct.unpack('B', self.file_handle.read(1))[0])
                if element_type != NBTType.TAG_List:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                
                list_length = reader.read_tag_int32(self.file_handle)
                if list_length != 2:
                    # 跳过整个block_indices
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                
                # 跳过两个列表
                for _ in range(2):
                    sub_element_type = NBTType(struct.unpack('B', self.file_handle.read(1))[0])
                    sub_list_length = reader.read_tag_int32(self.file_handle)
                    if sub_element_type == NBTType.TAG_Int:
                        self.file_handle.read(4 * sub_list_length)
                    else:
                        for _ in range(sub_list_length):
                            reader.skip_tag_value(self.file_handle, sub_element_type)
                
            elif tag_name == "entities":
                if tag_type != NBTType.TAG_List:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                self.entity_nbt = reader.read_tag_list(self.file_handle)
                
            elif tag_name == "palette":
                if tag_type != NBTType.TAG_Compound:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                self._parse_palette_compound(reader)
                
            else:
                reader.skip_tag_value(self.file_handle, tag_type)
    
    def _parse_palette_compound(self, reader: NBTReader):
        """解析palette复合标签"""
        while True:
            tag_type, tag_name = reader.read_tag(self.file_handle)
            if tag_type == NBTType.TAG_End:
                break
            
            if tag_name == "default":
                if tag_type != NBTType.TAG_Compound:
                    reader.skip_tag_value(self.file_handle, tag_type)
                    continue
                
                palette_data = reader.read_tag_compound(self.file_handle)
                
                # 处理方块调色板
                if "block_palette" in palette_data:
                    block_palette = palette_data["block_palette"]
                    if isinstance(block_palette, list):
                        for i, block_data in enumerate(block_palette):
                            if isinstance(block_data, dict):
                                name = block_data.get("name", "minecraft:air")
                                states = block_data.get("states", {})
                                
                                # 转换方块状态为runtime_id
                                runtime_id, found = self.block_registry.state_to_runtime_id(name, states)
                                if not found:
                                    runtime_id = self.UNKNOWN_BLOCK_RUNTIME_ID
                                
                                self.palette[i] = runtime_id
                                self.reverse_palette[runtime_id] = i
                
                # 处理方块实体数据
                if "block_position_data" in palette_data:
                    position_data = palette_data["block_position_data"]
                    if isinstance(position_data, dict):
                        for idx_str, data in position_data.items():
                            try:
                                idx = int(idx_str)
                                if isinstance(data, dict) and "block_entity_data" in data:
                                    self.block_nbt[idx] = data["block_entity_data"]
                            except ValueError:
                                continue
            
            else:
                reader.skip_tag_value(self.file_handle, tag_type)
    
    def get_palette(self) -> Dict[int, int]:
        """获取调色板"""
        return self.palette.copy()
    
    def get_offset_pos(self) -> Offset:
        """获取偏移位置"""
        return Offset(self.offset_pos.x, self.offset_pos.y, self.offset_pos.z)
    
    def set_offset_pos(self, offset: Offset):
        """设置偏移位置"""
        self.offset_pos = offset
        self.size.width = self.original_size.width + abs(offset.x)
        self.size.length = self.original_size.length + abs(offset.z)
        self.size.height = self.original_size.height + abs(offset.y)
    
    def get_size(self) -> Size:
        """获取尺寸"""
        return Size(self.size.width, self.size.height, self.size.length)
    
    def count_non_air_blocks(self) -> int:
        """统计非空气方块数量"""
        volume = self.original_size.get_volume()
        
        # 查找空气方块的索引
        air_index = None
        for idx, runtime_id in self.palette.items():
            if runtime_id == self.AIR_RUNTIME_ID:
                air_index = idx
                break
        
        if air_index is None:
            return volume
        
        non_air_blocks = 0
        
        try:
            # 重新打开文件读取block_indices
            with open(self.file_path, 'rb') as f:
                f.seek(self.block_index_tag_offset)
                reader = NBTReader(little_endian=True)
                
                # 读取block_indices[0]列表
                element_type = NBTType(struct.unpack('B', f.read(1))[0])
                if element_type != NBTType.TAG_List:
                    return volume
                
                list_length = reader.read_tag_int32(f)
                if list_length < 1:
                    return volume
                
                # 读取第一个列表（方块索引列表）
                sub_element_type = NBTType(struct.unpack('B', f.read(1))[0])
                if sub_element_type != NBTType.TAG_Int:
                    return volume
                
                block_count = reader.read_tag_int32(f)
                
                # 统计非空气方块
                for _ in range(block_count):
                    val = reader.read_tag_int32(f)
                    if val != air_index:
                        non_air_blocks += 1
                
                return non_air_blocks
                
        except Exception as e:
            error_msg = self.get_text('mcstructure.count_failed', '统计非空气方块失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            return volume
    
    def get_chunks(self, pos_list: List[ChunkPos]) -> Dict[ChunkPos, Chunk]:
        """获取指定区块位置的数据"""
        chunks = {}
        
        # 初始化所有请求的区块为空气
        for pos in pos_list:
            chunks[pos] = Chunk(self.AIR_RUNTIME_ID, range_y=384)
        
        if not self.palette:
            return chunks
        
        # 原始建筑的尺寸
        orig_width = self.original_size.width
        orig_length = self.original_size.length
        orig_height = self.original_size.height
        
        # 偏移量
        offset_x = self.offset_pos.x
        offset_y = self.offset_pos.y
        offset_z = self.offset_pos.z
        
        # 收集需要读取的原始建筑方块索引
        all_indices = []
        for pos in pos_list:
            chunk_min_x = pos.x * 16
            chunk_max_x = chunk_min_x + 16
            chunk_min_z = pos.z * 16
            chunk_max_z = chunk_min_z + 16
            
            # 按ZYX顺序生成索引
            for x in range(orig_width):
                new_x = x + offset_x
                if new_x < chunk_min_x or new_x >= chunk_max_x:
                    continue
                
                for y in range(orig_height):
                    new_y = y + offset_y
                    if new_y < 0 or new_y >= self.size.height:
                        continue
                    
                    for z in range(orig_length):
                        new_z = z + offset_z
                        if new_z < chunk_min_z or new_z >= chunk_max_z:
                            continue
                        
                        # 按ZYX顺序计算索引
                        index = x * orig_height * orig_length + y * orig_length + z
                        all_indices.append(index)
        
        if not all_indices:
            return chunks
        
        # 排序索引
        all_indices.sort()
        
        try:
            # 重新打开文件读取方块数据
            with open(self.file_path, 'rb') as f:
                f.seek(self.block_index_tag_offset)
                reader = NBTReader(little_endian=True)
                
                # 读取block_indices[0]列表
                element_type = NBTType(struct.unpack('B', f.read(1))[0])
                if element_type != NBTType.TAG_List:
                    return chunks
                
                list_length = reader.read_tag_int32(f)
                if list_length < 1:
                    return chunks
                
                # 读取第一个列表（方块索引列表）
                sub_element_type = NBTType(struct.unpack('B', f.read(1))[0])
                if sub_element_type != NBTType.TAG_Int:
                    return chunks
                
                block_count = reader.read_tag_int32(f)
                
                # 流式读取需要的索引
                next_needed = 0
                total = block_count
                
                for idx in range(total):
                    if next_needed >= len(all_indices):
                        break
                    
                    target = all_indices[next_needed]
                    if target < idx:
                        next_needed += 1
                        continue
                    
                    # 跳过不需要的索引
                    skip_count = target - idx
                    if skip_count > 0:
                        f.read(4 * skip_count)
                        idx += skip_count
                    
                    # 读取目标索引
                    val_data = f.read(4)
                    if len(val_data) < 4:
                        break
                    val = struct.unpack('<i', val_data)[0]
                    
                    if val != -1:
                        # 将扁平索引(ZYX顺序)转换为坐标
                        z = idx % orig_length
                        remaining = idx // orig_length
                        y = remaining % orig_height
                        x = remaining // orig_height
                        
                        new_x = x + offset_x
                        new_y = y + offset_y
                        new_z = z + offset_z
                        
                        chunk_x = new_x // 16
                        chunk_z = new_z // 16
                        local_x = new_x % 16
                        local_y = new_y
                        local_z = new_z % 16
                        
                        chunk_pos = ChunkPos(chunk_x, chunk_z)
                        if chunk_pos in chunks:
                            block_runtime_id = self.palette.get(val, self.UNKNOWN_BLOCK_RUNTIME_ID)
                            chunks[chunk_pos].set_block(local_x, local_y - 64, local_z, 0, block_runtime_id)
                    
                    idx += 1
                    next_needed += 1
        
        except Exception as e:
            error_msg = self.get_text('mcstructure.read_chunks_failed', '读取区块数据失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
        
        return chunks
    
    def to_runaway(self, output_path: str) -> Tuple[bool, str]:
        """转换为RunAway格式"""
        converting_msg = self.get_text('mcstructure.converting', '正在转换为RunAway格式...')
        print(f"{Color.CYAN}🔄 {converting_msg}{Color.RESET}")
        
        try:
            # 从Runaway模块导入类
            from runaway import RunAway
            
            # 获取所有方块数据
            blocks = []
            volume = self.original_size.get_volume()
            width = self.original_size.width
            height = self.original_size.height
            length = self.original_size.length
            
            if volume == 0:
                empty_msg = self.get_text('mcstructure.empty_structure', '结构为空')
                print(f"{Color.YELLOW}⚠️  {empty_msg}{Color.RESET}")
                return False, "空结构"
            
            # 创建进度显示
            progress = ProgressDisplay(volume, self.get_text('progress.reading_blocks', '读取方块数据'), self.config)
            
            # 读取方块数据
            with open(self.file_path, 'rb') as f:
                f.seek(self.block_index_tag_offset)
                reader = NBTReader(little_endian=True)
                
                # 读取block_indices[0]列表
                element_type = NBTType(struct.unpack('B', f.read(1))[0])
                if element_type != NBTType.TAG_List:
                    return False, "无效的方块数据格式"
                
                list_length = reader.read_tag_int32(f)
                if list_length < 1:
                    return False, "无方块数据"
                
                # 读取第一个列表（方块索引列表）
                sub_element_type = NBTType(struct.unpack('B', f.read(1))[0])
                if sub_element_type != NBTType.TAG_Int:
                    return False, "无效的方块索引格式"
                
                block_count = reader.read_tag_int32(f)
                
                # 读取所有方块
                for idx in range(min(block_count, volume)):
                    val = reader.read_tag_int32(f)
                    
                    if val != -1:
                        # 将扁平索引(ZYX顺序)转换为坐标
                        z = idx % length
                        remaining = idx // length
                        y = remaining % height
                        x = remaining // height
                        
                        # 获取方块的runtime_id
                        runtime_id = self.palette.get(val, self.UNKNOWN_BLOCK_RUNTIME_ID)
                        
                        if runtime_id != self.AIR_RUNTIME_ID:
                            # 将runtime_id转换为方块名称
                            block_name, block_states, found = self.block_registry.runtime_id_to_state(runtime_id)
                            
                            if found:
                                # 创建方块数据
                                block_data = {
                                    "name": block_name,
                                    "aux": 0,  # 简化处理，实际需要从states中提取
                                    "x": x,
                                    "y": y,
                                    "z": z
                                }
                                blocks.append(block_data)
                    
                    progress.update(idx + 1)
            
            progress.complete()
            
            if not blocks:
                no_blocks_msg = self.get_text('mcstructure.no_blocks', '没有可转换的方块')
                print(f"{Color.YELLOW}⚠️  {no_blocks_msg}{Color.RESET}")
                return False, "没有方块数据"
            
            # 创建RunAway对象并保存
            runaway = RunAway()
            runaway.blocks.extend(blocks)
            
            if not output_path.lower().endswith('.json'):
                output_path += '.json'
            
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            runaway.save_as(output_path)
            
            converted_msg = self.get_text('mcstructure.converted', '转换完成: {} ({}个方块)').format(output_path, len(blocks))
            print(f"{Color.GREEN}✅ {converted_msg}{Color.RESET}")
            return True, f"成功转换 {len(blocks)} 个方块"
            
        except ImportError:
            error_msg = self.get_text('mcstructure.import_failed', '无法导入RunAway模块')
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            return False, "缺少RunAway模块"
        except Exception as e:
            error_msg = self.get_text('mcstructure.convert_failed', '转换失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def close(self):
        """关闭文件句柄"""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None

# 兼容性别名
Converter = mcstructureConverter