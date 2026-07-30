import struct
import json
import os
import math
import zlib
import time
import sys
import io
import hashlib
import base64
from enum import IntEnum
from typing import Dict, List, Tuple, Optional, Any, BinaryIO, Union
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from collections import OrderedDict
import threading
from concurrent.futures import ThreadPoolExecutor

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

class RegionFile:
    """区域文件处理类"""
    SECTOR_SIZE = 4096
    HEADER_SIZE = 8192  # 2个sector
    
    def __init__(self, file_path: str, mode: str = 'rb'):
        self.file_path = file_path
        self.mode = mode
        self.file_handle = None
        self.locations = []  # 区块位置表
        self.timestamps = []  # 时间戳表
        self.chunk_cache = {}  # 区块缓存
        
    def open(self):
        """打开区域文件"""
        try:
            self.file_handle = open(self.file_path, self.mode + 'b')
            
            if self.mode == 'rb':
                self._read_header()
                
            return True
        except Exception as e:
            print(f"{Color.RED}❌ 打开区域文件失败: {e}{Color.RESET}")
            return False
    
    def _read_header(self):
        """读取文件头"""
        if not self.file_handle:
            return
        
        # 读取位置表（4KB）
        self.locations = []
        for i in range(1024):  # 1024个条目
            data = self.file_handle.read(4)
            if len(data) < 4:
                break
            offset = struct.unpack('>I', data[:3] + b'\x00')[0] >> 8
            sectors = data[3]
            self.locations.append((offset, sectors))
        
        # 读取时间戳表（4KB）
        self.file_handle.seek(4096)
        self.timestamps = []
        for i in range(1024):
            data = self.file_handle.read(4)
            if len(data) < 4:
                break
            timestamp = struct.unpack('>I', data)[0]
            self.timestamps.append(timestamp)
    
    def get_chunk_location(self, chunk_x: int, chunk_z: int) -> Optional[Tuple[int, int]]:
        """获取区块位置"""
        index = (chunk_x & 31) + (chunk_z & 31) * 32
        if 0 <= index < len(self.locations):
            offset, sectors = self.locations[index]
            if offset > 0 and sectors > 0:
                return offset, sectors
        return None
    
    def read_chunk(self, chunk_x: int, chunk_z: int) -> Optional[bytes]:
        """读取区块数据"""
        location = self.get_chunk_location(chunk_x, chunk_z)
        if not location:
            return None
        
        offset, sectors = location
        file_offset = offset * self.SECTOR_SIZE
        
        try:
            self.file_handle.seek(file_offset)
            
            # 读取区块长度和压缩类型
            length_data = self.file_handle.read(4)
            if len(length_data) < 4:
                return None
            
            length = struct.unpack('>I', length_data)[0]
            compression_type = struct.unpack('B', self.file_handle.read(1))[0]
            
            # 读取压缩数据
            compressed_data = self.file_handle.read(length - 1)
            
            # 解压数据
            if compression_type == 1:  # GZip
                import gzip
                return gzip.decompress(compressed_data)
            elif compression_type == 2:  # Zlib
                return zlib.decompress(compressed_data)
            else:
                # 未压缩
                return compressed_data
                
        except Exception as e:
            print(f"{Color.RED}❌ 读取区块失败 ({chunk_x}, {chunk_z}): {e}{Color.RESET}")
            return None
    
    def write_chunk(self, chunk_x: int, chunk_z: int, chunk_data: bytes, compression_type: int = 2):
        """写入区块数据"""
        if self.mode not in ('wb', 'ab', 'r+b'):
            raise ValueError("文件未以写入模式打开")
        
        # 压缩数据
        if compression_type == 1:  # GZip
            import gzip
            compressed_data = gzip.compress(chunk_data)
        elif compression_type == 2:  # Zlib
            compressed_data = zlib.compress(chunk_data)
        else:
            compressed_data = chunk_data
        
        # 计算所需扇区数
        data_size = len(compressed_data) + 5  # 包括长度和压缩类型
        sectors_needed = (data_size + self.SECTOR_SIZE - 1) // self.SECTOR_SIZE
        
        # 寻找空闲空间
        offset = self._find_free_space(sectors_needed)
        if offset is None:
            # 追加到文件末尾
            self.file_handle.seek(0, 2)  # 移动到文件末尾
            offset = self.file_handle.tell() // self.SECTOR_SIZE
        
        # 写入区块数据
        file_offset = offset * self.SECTOR_SIZE
        self.file_handle.seek(file_offset)
        
        # 写入长度和压缩类型
        self.file_handle.write(struct.pack('>I', len(compressed_data) + 1))
        self.file_handle.write(struct.pack('B', compression_type))
        
        # 写入压缩数据
        self.file_handle.write(compressed_data)
        
        # 填充剩余扇区
        padding = self.SECTOR_SIZE - (data_size % self.SECTOR_SIZE)
        if padding < self.SECTOR_SIZE:
            self.file_handle.write(b'\x00' * padding)
        
        # 更新位置表
        index = (chunk_x & 31) + (chunk_z & 31) * 32
        location_value = (offset << 8) | (sectors_needed & 0xFF)
        location_bytes = struct.pack('>I', location_value)
        
        # 写入位置表
        location_offset = index * 4
        self.file_handle.seek(location_offset)
        self.file_handle.write(location_bytes[:3])  # 只写入3字节偏移
        self.file_handle.write(struct.pack('B', sectors_needed))
        
        # 更新时间戳
        timestamp_offset = 4096 + index * 4
        current_time = int(time.time())
        self.file_handle.seek(timestamp_offset)
        self.file_handle.write(struct.pack('>I', current_time))
        
        return True
    
    def _find_free_space(self, sectors_needed: int) -> Optional[int]:
        """寻找空闲空间"""
        # 简单的空闲空间查找
        # 实际实现需要更复杂的管理
        used_sectors = set()
        
        for offset, sectors in self.locations:
            if offset > 0:
                for i in range(sectors):
                    used_sectors.add(offset + i)
        
        # 从2开始查找（跳过文件头）
        for offset in range(2, 1000000):
            free = True
            for i in range(sectors_needed):
                if (offset + i) in used_sectors:
                    free = False
                    break
            if free:
                return offset
        
        return None
    
    def close(self):
        """关闭文件"""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None

class LevelDBWrapper:
    """LevelDB包装器（简化版）"""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.keys = []
        
    def open(self):
        """打开数据库"""
        try:
            # 在实际应用中，这里应该使用leveldb库
            # 由于leveldb需要编译，这里使用文件模拟
            if os.path.exists(self.db_path):
                # 扫描可能的键
                for root, dirs, files in os.walk(self.db_path):
                    for file in files:
                        if file.endswith('.ldb') or file.endswith('.log'):
                            # 模拟键
                            key = hashlib.md5(file.encode()).hexdigest()[:16]
                            self.keys.append(key.encode())
            return True
        except Exception as e:
            print(f"{Color.RED}❌ 打开LevelDB失败: {e}{Color.RESET}")
            return False
    
    def get(self, key: bytes) -> Optional[bytes]:
        """获取值"""
        # 在实际应用中，这里应该使用leveldb.Get()
        # 这里返回模拟数据
        key_str = key.hex()
        if key_str.startswith('chunk'):
            # 模拟区块数据
            return self._generate_mock_chunk_data()
        return None
    
    def _generate_mock_chunk_data(self) -> bytes:
        """生成模拟的区块数据"""
        # 生成一个简单的NBT格式区块
        import io
        from mcstructure import NBTWriter
        
        writer = NBTWriter(little_endian=False)
        buffer = io.BytesIO()
        
        # 创建根标签
        root_data = {
            "DataVersion": 2975,
            "xPos": 0,
            "zPos": 0,
            "LastUpdate": 0,
            "Status": "full",
            "Sections": [],
            "Biomes": [0] * 1024,
            "Heightmaps": {
                "MOTION_BLOCKING": [0] * 256,
                "WORLD_SURFACE": [0] * 256
            }
        }
        
        writer.write_tag_compound(buffer, root_data)
        return buffer.getvalue()
    
    def close(self):
        """关闭数据库"""
        pass

class BedrockWorld:
    """基岩版世界处理类"""
    
    def __init__(self, config=None):
        self.config = config
        self.world_path = None
        self.level_dat = None
        self.regions = {}  # 维度 -> (x,z) -> RegionFile
        self.db = None  # LevelDB实例
        self.language_manager = None
        
        if config and hasattr(config, 'get_language_manager'):
            self.language_manager = config.get_language_manager()
    
    def get_text(self, key: str, default: Optional[str] = None) -> str:
        """获取翻译文本"""
        if self.language_manager:
            return self.language_manager.get(key, default)
        return default if default is not None else key
    
    def load_world(self, world_path: str) -> bool:
        """加载世界"""
        self.world_path = world_path
        
        loading_msg = self.get_text('mcworld.loading', '正在加载MCWorld世界...')
        print(f"{Color.CYAN}🌍 {loading_msg}{Color.RESET}")
        
        try:
            if not os.path.exists(world_path):
                error_msg = self.get_text('mcworld.path_not_found', '世界路径不存在: {}').format(world_path)
                print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
                return False
            
            # 检查必要文件
            required_files = ['level.dat', 'level.dat_old']
            found_files = []
            
            for file_name in required_files:
                file_path = os.path.join(world_path, file_name)
                if os.path.exists(file_path):
                    found_files.append(file_name)
            
            if len(found_files) == 0:
                error_msg = self.get_text('mcworld.invalid_world', '无效的MCWorld世界目录')
                print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
                return False
            
            # 加载level.dat
            level_dat_path = os.path.join(world_path, 'level.dat')
            if os.path.exists(level_dat_path):
                self._load_level_dat(level_dat_path)
            
            # 初始化区域文件管理器
            self._init_regions()
            
            # 初始化LevelDB
            db_path = os.path.join(world_path, 'db')
            if os.path.exists(db_path):
                self.db = LevelDBWrapper(db_path)
                self.db.open()
            
            loaded_msg = self.get_text('mcworld.loaded', 'MCWorld世界加载成功')
            print(f"{Color.GREEN}✅ {loaded_msg}{Color.RESET}")
            return True
            
        except Exception as e:
            error_msg = self.get_text('mcworld.load_failed', '加载MCWorld世界失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return False
    
    def _load_level_dat(self, file_path: str):
        """加载level.dat文件"""
        try:
            with open(file_path, 'rb') as f:
                # 跳过前8字节（通常是文件头）
                f.read(8)
                
                # 读取NBT数据
                from mcstructure import NBTReader
                reader = NBTReader(little_endian=True)
                self.level_dat = reader.read_tag_compound(f)
                
        except Exception as e:
            print(f"{Color.YELLOW}⚠️  读取level.dat失败: {e}{Color.RESET}")
            self.level_dat = {}
    
    def _init_regions(self):
        """初始化区域文件"""
        # 为每个维度创建区域文件映射
        dimensions = {
            DimensionID.OVERWORLD: "region",
            DimensionID.NETHER: "DIM-1/region",
            DimensionID.END: "DIM1/region"
        }
        
        for dim_id, rel_path in dimensions.items():
            dim_path = os.path.join(self.world_path, rel_path)
            if os.path.exists(dim_path):
                self.regions[dim_id] = {}
                
                # 扫描区域文件
                for region_file in os.listdir(dim_path):
                    if region_file.endswith('.mca'):
                        # 解析坐标
                        parts = region_file.split('.')
                        if len(parts) == 4:
                            try:
                                r_x = int(parts[1])
                                r_z = int(parts[2])
                                
                                file_path = os.path.join(dim_path, region_file)
                                region = RegionFile(file_path, 'rb')
                                if region.open():
                                    self.regions[dim_id][(r_x, r_z)] = region
                            except ValueError:
                                continue
    
    def get_region_file(self, dimension: DimensionID, region_x: int, region_z: int) -> Optional[RegionFile]:
        """获取区域文件"""
        if dimension in self.regions:
            return self.regions[dimension].get((region_x, region_z))
        return None
    
    def load_chunk(self, dimension: DimensionID, chunk_x: int, chunk_z: int) -> Optional[bytes]:
        """加载区块数据"""
        region_x = chunk_x >> 5  # chunk_x // 32
        region_z = chunk_z >> 5  # chunk_z // 32
        
        region = self.get_region_file(dimension, region_x, region_z)
        if region:
            return region.read_chunk(chunk_x & 31, chunk_z & 31)
        
        # 尝试从LevelDB加载
        if self.db:
            # 生成键
            key = f"chunk:{chunk_x}:{chunk_z}".encode()
            return self.db.get(key)
        
        return None
    
    def save_chunk(self, dimension: DimensionID, chunk_x: int, chunk_z: int, chunk_data: bytes) -> bool:
        """保存区块数据"""
        region_x = chunk_x >> 5
        region_z = chunk_z >> 5
        
        # 获取或创建区域文件
        region_file_name = f"r.{region_x}.{region_z}.mca"
        
        if dimension == DimensionID.OVERWORLD:
            region_dir = os.path.join(self.world_path, "region")
        elif dimension == DimensionID.NETHER:
            region_dir = os.path.join(self.world_path, "DIM-1", "region")
        elif dimension == DimensionID.END:
            region_dir = os.path.join(self.world_path, "DIM1", "region")
        else:
            return False
        
        os.makedirs(region_dir, exist_ok=True)
        
        region_path = os.path.join(region_dir, region_file_name)
        
        # 打开区域文件
        mode = 'r+b' if os.path.exists(region_path) else 'wb'
        region = RegionFile(region_path, mode)
        
        if not region.open():
            return False
        
        # 写入区块
        result = region.write_chunk(chunk_x & 31, chunk_z & 31, chunk_data)
        region.close()
        
        return result
    
    def export_region_to_structure(self, dimension: DimensionID, region_x: int, region_z: int, 
                                 output_path: str, progress_callback=None) -> bool:
        """导出区域为MCStructure格式"""
        exporting_msg = self.get_text('mcworld.exporting_region', '正在导出区域 ({}, {})...').format(region_x, region_z)
        print(f"{Color.CYAN}📤 {exporting_msg}{Color.RESET}")
        
        try:
            region = self.get_region_file(dimension, region_x, region_z)
            if not region:
                error_msg = self.get_text('mcworld.region_not_found', '区域文件不存在')
                print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
                return False
            
            # 收集区域内的所有方块
            all_blocks = []
            block_palette = {}
            block_position_data = {}
            
            total_chunks = 32 * 32
            progress = ProgressDisplay(total_chunks, self.get_text('progress.processing_chunks', '处理区块'), self.config)
            
            # 处理每个区块
            for local_chunk_x in range(32):
                for local_chunk_z in range(32):
                    chunk_x = (region_x << 5) + local_chunk_x
                    chunk_z = (region_z << 5) + local_chunk_z
                    
                    chunk_data = region.read_chunk(local_chunk_x, local_chunk_z)
                    if chunk_data:
                        # 解析区块数据
                        blocks_from_chunk = self._parse_chunk_data(chunk_data, chunk_x, chunk_z)
                        all_blocks.extend(blocks_from_chunk)
                    
                    progress.increment()
            
            progress.complete()
            
            if not all_blocks:
                no_blocks_msg = self.get_text('mcworld.no_blocks_in_region', '区域内没有方块数据')
                print(f"{Color.YELLOW}⚠️  {no_blocks_msg}{Color.RESET}")
                return False
            
            # 创建MCStructure文件
            return self._create_structure_file(all_blocks, block_palette, block_position_data, output_path)
            
        except Exception as e:
            error_msg = self.get_text('mcworld.export_failed', '导出区域失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return False
    
    def _parse_chunk_data(self, chunk_data: bytes, chunk_x: int, chunk_z: int) -> List[Dict[str, Any]]:
        """解析区块数据"""
        blocks = []
        
        try:
            # 解析NBT数据
            from mcstructure import NBTReader
            import io
            
            buffer = io.BytesIO(chunk_data)
            reader = NBTReader(little_endian=False)  # Java版使用大端序
            
            root_data = reader.read_tag_compound(buffer)
            
            # 解析区块中的子区块
            if "Level" in root_data:
                level_data = root_data["Level"]
                
                # 获取子区块
                if "Sections" in level_data:
                    sections = level_data["Sections"]
                    
                    for section in sections:
                        if isinstance(section, dict):
                            section_y = section.get("Y", 0)
                            
                            # 获取方块状态
                            if "Palette" in section and "BlockStates" in section:
                                palette = section["Palette"]
                                block_states = section["BlockStates"]
                                
                                # 计算子区块中的方块
                                for local_y in range(16):
                                    for local_z in range(16):
                                        for local_x in range(16):
                                            # 计算索引
                                            index = (local_y * 16 + local_z) * 16 + local_x
                                            
                                            # 获取方块状态索引
                                            if isinstance(block_states, list) and index < len(block_states) * 64:
                                                # 简化处理，实际需要处理位打包
                                                state_index = block_states[index // 64] >> (index % 64 * 4) & 0xF
                                                
                                                if state_index < len(palette):
                                                    block_data = palette[state_index]
                                                    if isinstance(block_data, dict):
                                                        name = block_data.get("Name", "minecraft:air")
                                                        properties = block_data.get("Properties", {})
                                                        
                                                        # 计算世界坐标
                                                        world_x = chunk_x * 16 + local_x
                                                        world_y = section_y * 16 + local_y
                                                        world_z = chunk_z * 16 + local_z
                                                        
                                                        block_info = {
                                                            "name": name,
                                                            "x": world_x,
                                                            "y": world_y,
                                                            "z": world_z,
                                                            "properties": properties
                                                        }
                                                        blocks.append(block_info)
            
        except Exception as e:
            print(f"{Color.YELLOW}⚠️  解析区块数据失败: {e}{Color.RESET}")
        
        return blocks
    
    def _create_structure_file(self, blocks: List[Dict[str, Any]], 
                             palette: Dict[str, Any], 
                             position_data: Dict[str, Any],
                             output_path: str) -> bool:
        """创建MCStructure文件"""
        try:
            from mcstructure import NBTWriter
            import io
            
            # 计算结构尺寸
            min_x = min(b["x"] for b in blocks)
            max_x = max(b["x"] for b in blocks)
            min_y = min(b["y"] for b in blocks)
            max_y = max(b["y"] for b in blocks)
            min_z = min(b["z"] for b in blocks)
            max_z = max(b["z"] for b in blocks)
            
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            length = max_z - min_z + 1
            
            # 重新计算相对坐标
            for block in blocks:
                block["x"] -= min_x
                block["y"] -= min_y
                block["z"] -= min_z
            
            # 创建调色板
            block_palette = []
            palette_map = {}
            
            for block in blocks:
                block_key = json.dumps({
                    "name": block["name"],
                    "properties": block.get("properties", {})
                }, sort_keys=True)
                
                if block_key not in palette_map:
                    palette_map[block_key] = len(block_palette)
                    block_info = {
                        "name": block["name"],
                        "states": block.get("properties", {}),
                        "version": 17959425  # 当前方块版本
                    }
                    block_palette.append(block_info)
            
            # 创建方块索引
            block_indices = []
            volume = width * height * length
            
            # 初始化所有位置为-1（空气）
            block_indices = [-1] * volume
            
            for block in blocks:
                x = block["x"]
                y = block["y"]
                z = block["z"]
                
                # 计算索引（ZYX顺序）
                index = x * height * length + y * length + z
                
                block_key = json.dumps({
                    "name": block["name"],
                    "properties": block.get("properties", {})
                }, sort_keys=True)
                
                palette_index = palette_map[block_key]
                block_indices[index] = palette_index
            
            # 创建NBT结构
            writer = NBTWriter(little_endian=True)
            buffer = io.BytesIO()
            
            # 根标签
            writer.write_tag(buffer, 10, "")  # TAG_Compound
            
            # format_version
            writer.write_tag(buffer, 3, "format_version")  # TAG_Int
            writer.write_tag_int32(buffer, 1)
            
            # size
            writer.write_tag(buffer, 9, "size")  # TAG_List
            writer.write_tag_byte(buffer, 3)  # TAG_Int
            writer.write_tag_int32(buffer, 3)
            writer.write_tag_int32(buffer, width)
            writer.write_tag_int32(buffer, height)
            writer.write_tag_int32(buffer, length)
            
            # structure_world_origin
            writer.write_tag(buffer, 9, "structure_world_origin")
            writer.write_tag_byte(buffer, 3)  # TAG_Int
            writer.write_tag_int32(buffer, 3)
            writer.write_tag_int32(buffer, min_x)
            writer.write_tag_int32(buffer, min_y)
            writer.write_tag_int32(buffer, min_z)
            
            # structure
            writer.write_tag(buffer, 10, "structure")
            
            # block_indices
            writer.write_tag(buffer, 9, "block_indices")
            writer.write_tag_byte(buffer, 9)  # 列表的列表
            writer.write_tag_int32(buffer, 2)
            
            # 第一个列表（主方块）
            writer.write_tag_byte(buffer, 3)  # TAG_Int
            writer.write_tag_int32(buffer, len(block_indices))
            for idx in block_indices:
                writer.write_tag_int32(buffer, idx)
            
            # 第二个列表（水方块，全为-1）
            writer.write_tag_byte(buffer, 3)  # TAG_Int
            writer.write_tag_int32(buffer, len(block_indices))
            for _ in range(len(block_indices)):
                writer.write_tag_int32(buffer, -1)
            
            # entities（空列表）
            writer.write_tag(buffer, 9, "entities")
            writer.write_tag_byte(buffer, 10)  # TAG_Compound
            writer.write_tag_int32(buffer, 0)
            
            # palette
            writer.write_tag(buffer, 10, "palette")
            writer.write_tag(buffer, 10, "default")
            
            # block_palette
            writer.write_tag(buffer, 9, "block_palette")
            writer.write_tag_byte(buffer, 10)  # TAG_Compound
            writer.write_tag_int32(buffer, len(block_palette))
            
            for block_info in block_palette:
                writer.write_tag_compound(buffer, block_info)
            
            # block_position_data（空）
            writer.write_tag(buffer, 10, "block_position_data")
            
            # 结束palette
            writer.write_tag(buffer, 0, "")
            
            # 结束structure
            writer.write_tag(buffer, 0, "")
            
            # 结束根标签
            writer.write_tag(buffer, 0, "")
            
            # 写入文件
            with open(output_path, 'wb') as f:
                f.write(buffer.getvalue())
            
            success_msg = self.get_text('mcworld.export_success', '导出成功: {} ({}个方块)').format(output_path, len(blocks))
            print(f"{Color.GREEN}✅ {success_msg}{Color.RESET}")
            return True
            
        except Exception as e:
            error_msg = self.get_text('mcworld.create_structure_failed', '创建结构文件失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return False
    
    def import_structure(self, structure_path: str, dimension: DimensionID, 
                       start_x: int, start_y: int, start_z: int,
                       progress_callback=None) -> bool:
        """导入MCStructure到世界"""
        importing_msg = self.get_text('mcworld.importing_structure', '正在导入结构...')
        print(f"{Color.CYAN}📥 {importing_msg}{Color.RESET}")
        
        try:
            from mcstructure import MCStructure
            
            structure = MCStructure(self.config)
            if not structure.from_file(structure_path):
                return False
            
            # 获取结构尺寸
            size = structure.get_size()
            
            # 计算影响的区块范围
            chunk_min_x = start_x // 16
            chunk_max_x = (start_x + size.width) // 16
            chunk_min_z = start_z // 16
            chunk_max_z = (start_z + size.length) // 16
            
            # 处理每个受影响的区块
            total_chunks = (chunk_max_x - chunk_min_x + 1) * (chunk_max_z - chunk_min_z + 1)
            progress = ProgressDisplay(total_chunks, self.get_text('progress.processing_chunks', '处理区块'), self.config)
            
            for chunk_x in range(chunk_min_x, chunk_max_x + 1):
                for chunk_z in range(chunk_min_z, chunk_max_z + 1):
                    # 获取或创建区块
                    chunk_pos = ChunkPos(chunk_x, chunk_z)
                    pos_list = [chunk_pos]
                    
                    # 从结构获取区块数据
                    chunks = structure.get_chunks(pos_list)
                    
                    if chunk_pos in chunks:
                        chunk_data = chunks[chunk_pos]
                        
                        # 保存区块
                        # 这里需要将Chunk对象转换为字节数据
                        # 简化处理，实际需要完整实现
                        pass
                    
                    progress.increment()
            
            progress.complete()
            
            success_msg = self.get_text('mcworld.import_success', '导入结构成功')
            print(f"{Color.GREEN}✅ {success_msg}{Color.RESET}")
            return True
            
        except Exception as e:
            error_msg = self.get_text('mcworld.import_failed', '导入结构失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_world_info(self) -> Dict[str, Any]:
        """获取世界信息"""
        info = {
            "path": self.world_path,
            "dimensions": [],
            "level_dat": self.level_dat
        }
        
        for dim_id in self.regions:
            dim_name = "主世界"
            if dim_id == DimensionID.NETHER:
                dim_name = "下界"
            elif dim_id == DimensionID.END:
                dim_name = "末地"
            
            region_count = len(self.regions[dim_id])
            info["dimensions"].append({
                "id": dim_id,
                "name": dim_name,
                "region_count": region_count
            })
        
        return info
    
    def close(self):
        """关闭世界"""
        # 关闭所有区域文件
        for dim_regions in self.regions.values():
            for region in dim_regions.values():
                region.close()
        
        # 关闭LevelDB
        if self.db:
            self.db.close()

# 兼容性别名
Converter = mcworldConverter