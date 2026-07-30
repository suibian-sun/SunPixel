import numpy as np
import png
from PIL import Image
import os
import time
import math
import json
import gzip
import struct
from pathlib import Path
import sys
import threading
import nbtlib
from nbtlib.tag import Byte, Short, Int, Long, Float, Double, String, List, Compound
from nbtlib import List as NBTList  # 导入nbtlib的List类
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
from typing import Dict, List as TypingList, Tuple, Optional, Any, BinaryIO

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

class ProgressDisplay:
    """简化的进度显示类"""
    def __init__(self, total, description, config):
        self.total = total
        self.description = description
        self.config = config
        self.current = 0
        self.start_time = time.time()
        self.use_color = config.getboolean('ui', 'colored_output', True)
        self.last_update = 0
        self.language_manager = config.get_language_manager() if hasattr(config, 'get_language_manager') else None
        
    def get_text(self, key, default=None):
        """获取翻译文本"""
        if self.language_manager:
            return self.language_manager.get(key, default)
        return default if default is not None else key
        
    def update(self, value):
        """更新进度并显示（减少显示频率）"""
        self.current = value
        current_time = time.time()
        
        # 限制更新频率：每秒最多更新4次
        if current_time - self.last_update >= 0.25 or value >= self.total:
            self.last_update = current_time
            self._display()
            
    def increment(self, value=1):
        """增加进度"""
        self.update(self.current + value)
        
    def complete(self):
        """完成进度显示"""
        self.current = self.total
        self._display()
        print()  # 换行
        
    def _display(self):
        """显示进度条"""
        progress = min(100.0, (self.current / self.total) * 100)
        bar_length = 30
        filled_length = int(bar_length * self.current // self.total)
        
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

class LitematicaBitArray:
    """Litematica 位数组实现"""
    def __init__(self, data: TypingList[int], size: int, bits_per_entry: int):
        self.data = data
        self.size = size
        self.bits_per_entry = bits_per_entry
        self.mask = (1 << bits_per_entry) - 1
    
    def get(self, index: int) -> int:
        """从位数组中获取指定索引的值"""
        if index < 0 or index >= self.size:
            return 0
        
        start_offset = index * self.bits_per_entry
        start_array_index = start_offset >> 6  # 除以64
        end_array_index = ((index + 1) * self.bits_per_entry - 1) >> 6
        start_bit_offset = start_offset & 0x3F  # 模64
        
        if start_array_index == end_array_index:
            # 数据在同一个long中
            return (self.data[start_array_index] >> start_bit_offset) & self.mask
        else:
            # 数据跨越两个long
            end_offset = 64 - start_bit_offset
            val = (self.data[start_array_index] >> start_bit_offset) | (self.data[end_array_index] << end_offset)
            return val & self.mask

class StreamingLSBBitReader:
    """流式LSB位读取器"""
    def __init__(self, reader: BinaryIO, num_longs: int):
        self.reader = reader
        self.remain = num_longs  # 剩余可读的long数
        self.curr = 0
        self.bits_left = 0  # curr中尚未消费的位数
    
    def read_long(self) -> bool:
        """读取一个64位整数"""
        if self.remain <= 0:
            self.curr = 0
            self.bits_left = 0
            return False
        
        try:
            data = self.reader.read(8)
            if len(data) < 8:
                return False
            self.curr = struct.unpack('>Q', data)[0]
            self.bits_left = 64
            self.remain -= 1
            return True
        except:
            return False
    
    def next(self, n: int) -> int:
        """读取n位数据"""
        if n == 0:
            return 0
        
        val = 0
        have = 0
        
        while have < n:
            if self.bits_left == 0:
                if not self.read_long():
                    break
            
            need = n - have
            if self.bits_left >= need:
                mask = (1 << need) - 1
                chunk = self.curr & mask
                val |= chunk << have
                self.curr >>= need
                self.bits_left -= need
                have += need
            else:
                # 消费所有剩余位
                mask = (1 << self.bits_left) - 1
                chunk = self.curr & mask
                val |= chunk << have
                have += self.bits_left
                self.curr = 0
                self.bits_left = 0
        
        return val

class LitematicRegionIterator:
    """Litematic区域迭代器"""
    def __init__(self, world, start_block_pos, end_block_pos, start_sub_chunk_pos,
                 sub_chunk_x_num, sub_chunk_y_num, sub_chunk_z_num, chunk_count):
        self.world = world
        self.start_block_pos = start_block_pos
        self.end_block_pos = end_block_pos
        self.start_sub_chunk_pos = start_sub_chunk_pos
        self.sub_chunk_x_num = sub_chunk_x_num
        self.sub_chunk_y_num = sub_chunk_y_num
        self.sub_chunk_z_num = sub_chunk_z_num
        self.chunk_count = chunk_count
    
    def for_each(self, layer_done=None, process=None):
        """遍历所有方块并处理"""
        if process is None:
            return
        
        start_block_pos_x, start_block_pos_y, start_block_pos_z = self.start_block_pos
        end_block_pos_x, end_block_pos_y, end_block_pos_z = self.end_block_pos
        start_sub_chunk_pos_x, start_sub_chunk_pos_y, start_sub_chunk_pos_z = self.start_sub_chunk_pos
        
        for sub_chunk_y in range(self.sub_chunk_y_num):
            world_sub_chunk_pos_y = start_sub_chunk_pos_y + sub_chunk_y
            sub_chunk_world_y_start = world_sub_chunk_pos_y * 16
            sub_chunk_world_y_end = sub_chunk_world_y_start + 15
            effective_world_y_start = max(sub_chunk_world_y_start, start_block_pos_y)
            effective_world_y_end = min(sub_chunk_world_y_end, end_block_pos_y)
            
            if effective_world_y_start > effective_world_y_end:
                if layer_done:
                    layer_done()
                continue
            
            sub_chunks = {}
            for local_y in range(effective_world_y_start - sub_chunk_world_y_start, 
                                effective_world_y_end - sub_chunk_world_y_start + 1):
                for sub_chunk_z in range(self.sub_chunk_z_num):
                    world_sub_chunk_pos_z = start_sub_chunk_pos_z + sub_chunk_z
                    sub_chunk_world_z_start = world_sub_chunk_pos_z * 16
                    sub_chunk_world_z_end = sub_chunk_world_z_start + 15
                    effective_world_z_start = max(sub_chunk_world_z_start, start_block_pos_z)
                    effective_world_z_end = min(sub_chunk_world_z_end, end_block_pos_z)
                    
                    if effective_world_z_start > effective_world_z_end:
                        continue
                    
                    for local_z in range(effective_world_z_start - sub_chunk_world_z_start,
                                        effective_world_z_end - sub_chunk_world_z_start + 1):
                        for sub_chunk_x in range(self.sub_chunk_x_num):
                            world_sub_chunk_pos_x = start_sub_chunk_pos_x + sub_chunk_x
                            sub_chunk_world_x_start = world_sub_chunk_pos_x * 16
                            sub_chunk_world_x_end = sub_chunk_world_x_start + 15
                            effective_world_x_start = max(sub_chunk_world_x_start, start_block_pos_x)
                            effective_world_x_end = min(sub_chunk_world_x_end, end_block_pos_x)
                            
                            if effective_world_x_start > effective_world_x_end:
                                continue
                            
                            world_sub_chunk_pos = (world_sub_chunk_pos_x, world_sub_chunk_pos_y, world_sub_chunk_pos_z)
                            
                            if world_sub_chunk_pos not in sub_chunks:
                                # 这里需要根据实际情况加载子区块
                                # sub_chunk = self.world.load_sub_chunk(world_sub_chunk_pos)
                                # if sub_chunk is None:
                                #     sub_chunk = create_air_sub_chunk()
                                # sub_chunks[world_sub_chunk_pos] = sub_chunk
                                pass  # 简化实现
                            
                            # sub_chunk = sub_chunks[world_sub_chunk_pos]
                            for local_x in range(effective_world_x_start - sub_chunk_world_x_start,
                                               effective_world_x_end - sub_chunk_world_x_start + 1):
                                # block_runtime_id = sub_chunk.get_block(local_x, local_y, local_z, 0)
                                # process(block_runtime_id)
                                pass  # 简化实现
            
            if layer_done:
                layer_done()

class LitematicBlockStateWriter:
    """Litematic方块状态写入器"""
    def __init__(self, bits_per_block: int, write_long_func):
        if bits_per_block < 1:
            bits_per_block = 1
        
        self.bits_per_block = bits_per_block
        self.mask = (1 << bits_per_block) - 1
        self.current = 0
        self.bits_filled = 0
        self.long_count = 0
        self.write_long = write_long_func
    
    def write_index(self, index: int) -> bool:
        """写入一个方块索引"""
        value = index & self.mask
        remaining = self.bits_per_block
        
        while remaining > 0:
            available = 64 - self.bits_filled
            if available == 0:
                if not self.flush():
                    return False
                available = 64
            
            if remaining <= available:
                chunk = value & ((1 << remaining) - 1)
                self.current |= chunk << self.bits_filled
                self.bits_filled += remaining
                remaining = 0
                
                if self.bits_filled == 64:
                    if not self.flush():
                        return False
            else:
                chunk = value & ((1 << available) - 1)
                self.current |= chunk << self.bits_filled
                value >>= available
                remaining -= available
                if not self.flush():
                    return False
        
        return True
    
    def flush(self) -> bool:
        """刷新缓冲区"""
        if self.bits_filled == 0 and self.current == 0:
            return True
        
        try:
            self.write_long(self.current)
            self.long_count += 1
            self.current = 0
            self.bits_filled = 0
            return True
        except:
            return False
    
    def finish(self, expected_longs: int) -> bool:
        """完成写入，检查长度"""
        if self.bits_filled > 0:
            if not self.flush():
                return False
        
        if self.long_count != expected_longs:
            print(f"BlockStates 长度不匹配: 期望 {expected_longs}, 实际 {self.long_count}")
            return False
        
        return True

class Litematic:
    """Litematic结构类"""
    def __init__(self, config=None):
        self.config = config
        self.file_path = None
        self.size = {'width': 0, 'height': 0, 'length': 0}
        self.original_size = {'width': 0, 'height': 0, 'length': 0}
        self.offset_pos = {'x': 0, 'y': 0, 'z': 0}
        
        self.version = 0
        self.data_version = 0
        self.sub_version = 0
        self.metadata = {}
        self.origin = {'x': 0, 'y': 0, 'z': 0}
        self.entity_nbt = []
        self.block_nbt = []
        
        self.palette = {}  # 调色板：索引 -> RuntimeID
        self.block_states_offset = 0  # BlockStates在gzip流中的偏移位置
        
        # 用于图像转换的属性
        self.color_to_block = {}
        self.block_palette = []
        self.block_data = []
        self.block_data_values = []
        self.width = 0
        self.height = 0
        self.depth = 1
        self.pixels = None
        self.original_width = 0
        self.original_height = 0
        
        self.language_manager = config.get_language_manager() if hasattr(config, 'get_language_manager') else None
    
    def get_text(self, key, default=None):
        """获取翻译文本"""
        if self.language_manager:
            return self.language_manager.get(key, default)
        return default if default is not None else key
    
    def from_file(self, file_path: str) -> bool:
        """从文件加载Litematic结构"""
        try:
            self.file_path = file_path
            
            with open(file_path, 'rb') as f:
                with gzip.GzipFile(fileobj=f) as gzip_file:
                    # 读取NBT数据
                    nbt_data = nbtlib.load(gzip_file)
                    
                    # 读取版本信息
                    self.version = int(nbt_data.get('Version', 0))
                    self.data_version = int(nbt_data.get('MinecraftDataVersion', 0))
                    self.sub_version = int(nbt_data.get('SubVersion', 0))
                    
                    # 读取元数据
                    metadata_tag = nbt_data.get('Metadata')
                    if metadata_tag:
                        self.metadata = dict(metadata_tag)
                    
                    # 读取区域信息（只取第一个区域）
                    regions_tag = nbt_data.get('Regions')
                    if regions_tag and len(regions_tag) > 0:
                        # 获取第一个区域
                        first_region_name = list(regions_tag.keys())[0]
                        region = regions_tag[first_region_name]
                        
                        # 读取位置和尺寸
                        position_tag = region.get('Position')
                        if position_tag:
                            self.origin['x'] = int(position_tag.get('x', 0))
                            self.origin['y'] = int(position_tag.get('y', 0))
                            self.origin['z'] = int(position_tag.get('z', 0))
                        
                        size_tag = region.get('Size')
                        if size_tag:
                            self.size['width'] = abs(int(size_tag.get('x', 0)))
                            self.size['height'] = abs(int(size_tag.get('y', 0)))
                            self.size['length'] = abs(int(size_tag.get('z', 0)))
                            self.original_size = self.size.copy()
                        
                        # 读取调色板
                        palette_tag = region.get('BlockStatePalette')
                        if palette_tag:
                            for i, block_state in enumerate(palette_tag):
                                if isinstance(block_state, Compound):
                                    block_name = str(block_state.get('Name', ''))
                                    properties = {}
                                    
                                    props_tag = block_state.get('Properties')
                                    if props_tag:
                                        properties = dict(props_tag)
                                    
                                    # 这里需要将Java方块名转换为RuntimeID
                                    # 简化实现，只存储方块名
                                    runtime_id = self.block_name_to_runtime_id(block_name, properties)
                                    self.palette[i] = runtime_id
                        
                        # 读取实体和方块实体
                        entities_tag = region.get('Entities')
                        if entities_tag:
                            self.entity_nbt = [dict(entity) for entity in entities_tag]
                        
                        tile_entities_tag = region.get('TileEntities')
                        if tile_entities_tag:
                            self.block_nbt = [dict(tile_entity) for tile_entity in tile_entities_tag]
                        
                        # 记录BlockStates偏移（在Python中我们不直接记录偏移）
                        if 'BlockStates' in region:
                            # 在Python版本中，我们直接存储BlockStates数据
                            pass
            
            return True
        except Exception as e:
            print(f"{Color.RED}❌ 加载Litematic文件失败: {e}{Color.RESET}")
            return False
    
    def block_name_to_runtime_id(self, block_name: str, properties: Dict) -> int:
        """将方块名和属性转换为RuntimeID（简化实现）"""
        # 这里应该调用实际的转换逻辑
        # 简化实现：返回一个伪RuntimeID
        return hash(f"{block_name}:{json.dumps(properties)}") & 0xFFFFFFFF
    
    def get_palette(self) -> Dict[int, int]:
        """获取调色板"""
        return self.palette
    
    def get_offset_pos(self) -> Dict:
        """获取偏移位置"""
        return self.offset_pos
    
    def set_offset_pos(self, offset: Dict):
        """设置偏移位置"""
        self.offset_pos = offset.copy()
        self.size['width'] = self.original_size['width'] + abs(offset.get('x', 0))
        self.size['length'] = self.original_size['length'] + abs(offset.get('z', 0))
        self.size['height'] = self.original_size['height'] + abs(offset.get('y', 0))
    
    def get_size(self) -> Dict:
        """获取尺寸"""
        return self.size.copy()
    
    def get_volume(self) -> int:
        """获取体积"""
        return self.size['width'] * self.size['height'] * self.size['length']
    
    def load_block_mappings(self, selected_blocks):
        """从block目录加载选中的方块映射"""
        self.color_to_block = {}
        block_dir = Path("block")
        
        if not block_dir.exists():
            error_msg = self.get_text('file.block_dir_not_found', '错误: block目录不存在!')
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            return False
            
        for block_file in block_dir.glob("*.json"):
            block_name = block_file.stem
            if block_name in selected_blocks:
                try:
                    with open(block_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        json_lines = []
                        for line in lines:
                            if not line.strip().startswith('#'):
                                json_lines.append(line)
                        
                        if json_lines:
                            block_data = json.loads(''.join(json_lines))
                            
                            # 规范化方块数据
                            processed_block_data = {}
                            for color_key, block_info in block_data.items():
                                if isinstance(color_key, str):
                                    if isinstance(block_info, list) and len(block_info) >= 2:
                                        block_name = block_info[0]
                                        aux_value = block_info[1]
                                        try:
                                            aux_int = int(aux_value)
                                        except (ValueError, TypeError):
                                            aux_int = 0
                                        processed_block_data[color_key] = [block_name, aux_int]
                                    else:
                                        processed_block_data[color_key] = ["minecraft:white_concrete", 0]
                                else:
                                    color_str = str(color_key)
                                    if isinstance(block_info, list) and len(block_info) >= 2:
                                        block_name = block_info[0]
                                        aux_value = block_info[1]
                                        try:
                                            aux_int = int(aux_value)
                                        except (ValueError, TypeError):
                                            aux_int = 0
                                        processed_block_data[color_str] = [block_name, aux_int]
                                    else:
                                        processed_block_data[color_str] = ["minecraft:white_concrete", 0]
                            
                            self.color_to_block.update(processed_block_data)
                            loaded_msg = self.get_text('file.block_mappings_loaded', '已加载: {}').format(block_name)
                            print(f"{Color.GREEN}✅ {loaded_msg}{Color.RESET}")
                        else:
                            error_msg = self.get_text('file.invalid_json', '文件 {} 中没有有效的JSON内容').format(block_file)
                            print(f"{Color.YELLOW}❌ {error_msg}{Color.RESET}")
                except Exception as e:
                    error_msg = self.get_text('file.load_error', '加载 {} 时出错: {}').format(block_file, e)
                    print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
        
        if not self.color_to_block:
            error_msg = self.get_text('file.no_mappings_loaded', '错误: 没有加载任何方块映射!')
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            return False
            
        loaded_count = self.get_text('file.total_mappings_loaded', '总共加载 {} 种颜色映射').format(len(self.color_to_block))
        print(f"{Color.GREEN}✅ {loaded_count}{Color.RESET}")
        return True
    
    def color_distance(self, c1, c2):
        """计算两个颜色之间的感知距离"""
        r1, g1, b1 = c1
        r2, g2, b2 = c2
        r_mean = (r1 + r2) // 2
        
        r_diff = r1 - r2
        g_diff = g1 - g2
        b_diff = b1 - b2
        
        # 使用整数运算提高性能
        return math.sqrt(
            (2 + r_mean//256) * (r_diff*r_diff) +
            4 * (g_diff*g_diff) +
            (2 + (255 - r_mean)//256) * (b_diff*b_diff)
        )
    
    def find_closest_color(self, color):
        """找到最接近的颜色映射"""
        r, g, b = color[:3]
        closest_color = None
        min_distance = float('inf')
        
        # 预计算目标颜色
        target_colors = []
        for target_color_str in self.color_to_block.keys():
            try:
                if target_color_str.startswith('(') and target_color_str.endswith(')'):
                    color_str = target_color_str[1:-1]
                    color_values = [int(x.strip()) for x in color_str.split(',')]
                    target_color = tuple(color_values[:3])
                else:
                    color_values = [int(x.strip()) for x in target_color_str.split(',')]
                    target_color = tuple(color_values[:3])
                target_colors.append((target_color_str, target_color))
            except Exception:
                continue
        
        # 批量处理查找
        for target_color_str, target_color in target_colors:
            distance = self.color_distance((r, g, b), target_color)
            if distance < min_distance:
                min_distance = distance
                closest_color = target_color_str
                
        if closest_color:
            block_info = self.color_to_block[closest_color]
            if isinstance(block_info, list) and len(block_info) >= 2:
                block_name = block_info[0]
                aux_value = block_info[1]
                
                # 确保aux是整数
                try:
                    aux_int = int(aux_value)
                except (ValueError, TypeError):
                    aux_int = 0
                    
                return block_name, aux_int
        
        return "minecraft:white_concrete", 0
    
    def load_image(self, image_path):
        """加载图片，支持PNG和JPG格式"""
        loading_msg = self.get_text('conversion.loading_image', '正在加载图片...')
        print(f"{Color.CYAN}🖼️  {loading_msg}{Color.RESET}")
        ext = os.path.splitext(image_path)[1].lower()
        
        if ext == '.png':
            reader = png.Reader(filename=image_path)
            width, height, pixels, metadata = reader.asDirect()
            
            # 使用更高效的加载方式
            image_data = np.vstack(list(pixels))
            
            if metadata['alpha']:
                self.pixels = image_data.reshape(height, width, 4)[:, :, :3]
            else:
                self.pixels = image_data.reshape(height, width, 3)
                
            self.original_width = width
            self.original_height = height
            
        elif ext in ('.jpg', '.jpeg'):
            img = Image.open(image_path)
            img = img.convert('RGB')
            self.original_width, self.original_height = img.size
            self.pixels = np.array(img)
            
        else:
            raise ValueError(f"不支持的图片格式: {ext}")
        
        loaded_msg = self.get_text('conversion.image_loaded', '图片加载完成: {} × {} 像素').format(self.original_width, self.original_height)
        print(f"{Color.GREEN}✅ {loaded_msg}{Color.RESET}")
    
    def calculate_best_ratio(self, target_width, target_height):
        """计算最佳保持比例的尺寸"""
        orig_ratio = self.original_width / self.original_height
        target_ratio = target_width / target_height
        
        if abs(orig_ratio - target_ratio) < 0.05:
            return target_width, target_height
        
        if orig_ratio > target_ratio:
            best_width = target_width
            best_height = int(target_width / orig_ratio)
        else:
            best_height = target_height
            best_width = int(target_height * orig_ratio)
            
        return best_width, best_height
    
    def set_size(self, width, height):
        """设置生成结构的尺寸"""
        self.width = max(1, width)
        self.height = max(1, height)
        size_msg = self.get_text('conversion.setting_size', '设置生成尺寸: {} × {} 方块').format(self.width, self.height)
        print(f"{Color.CYAN}📐 {size_msg}{Color.RESET}")
    
    def process_chunk(self, chunk_info):
        """处理一个像素块"""
        start_y, end_y, scale_x, scale_y = chunk_info
        chunk_data = []
        chunk_values = []
        
        # 预计算颜色查找表
        color_cache = {}
        
        for y in range(start_y, end_y):
            row_data = []
            row_values = []
            src_y_base = int(y * scale_y)
            
            for x in range(self.width):
                src_x = int(x * scale_x)
                
                # 计算区域平均颜色（优化边界检查）
                y_end = min(int((y+1)*scale_y), self.original_height)
                x_end = min(int((x+1)*scale_x), self.original_width)
                
                if x_end <= src_x or y_end <= src_y_base:
                    avg_color = (255, 255, 255)
                else:
                    region = self.pixels[src_y_base:y_end, src_x:x_end]
                    if region.size == 0:
                        avg_color = (255, 255, 255)
                    else:
                        # 使用整数运算提高性能
                        avg_color = tuple(np.mean(region, axis=(0, 1)).astype(int))
                
                # 使用缓存提高性能
                color_key = avg_color
                if color_key in color_cache:
                    block_name, block_data = color_cache[color_key]
                else:
                    block_name, block_data = self.find_closest_color(avg_color)
                    color_cache[color_key] = (block_name, block_data)
                
                if block_name in self.block_palette:
                    block_index = self.block_palette.index(block_name)
                else:
                    block_index = 0
                
                row_data.append(block_index)
                row_values.append(block_data)
            
            chunk_data.append(row_data)
            chunk_values.append(row_values)
        
        return start_y, end_y, chunk_data, chunk_values
    
    def generate_block_data_concurrent(self):
        """并发生成方块数据"""
        generating_msg = self.get_text('conversion.generating_data', '正在生成方块数据（并发处理）...')
        print(f"{Color.CYAN}🔨 {generating_msg}{Color.RESET}")
        
        # 初始化调色板
        self.block_palette = []
        for block_info in self.color_to_block.values():
            if isinstance(block_info, list) and len(block_info) >= 1:
                block_name = block_info[0]
                if block_name not in self.block_palette:
                    self.block_palette.append(block_name)
                    
        palette_msg = self.get_text('conversion.palette_initialized', '初始化调色板: {} 种方块').format(len(self.block_palette))
        print(f"{Color.CYAN}🎨 {palette_msg}{Color.RESET}")
        
        # 初始化数据数组
        self.block_data = np.zeros((self.depth, self.height, self.width), dtype=np.uint8)
        self.block_data_values = np.zeros((self.depth, self.height, self.width), dtype=np.uint8)
        
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        processing_msg = self.get_text('conversion.processing_pixels', '正在处理像素数据（并发处理）...')
        print(f"{Color.CYAN}🔄 {processing_msg}{Color.RESET}")
        
        # 动态确定最优的并发策略
        total_pixels = self.width * self.height
        
        # 根据图片大小决定是否使用并发
        if total_pixels < 10000:  # 小图片，不使用并发
            small_msg = self.get_text('stats.small_image', '小图片({}像素)，使用单线程处理').format(total_pixels)
            print(f"{Color.CYAN}📱 {small_msg}{Color.RESET}")
            
            # 单线程处理
            progress = ProgressDisplay(self.height, self.get_text('progress.processing_pixels', '处理像素行'), self.config)
            
            for y in range(self.height):
                src_y = int(y * scale_y)
                y_end = min(int((y+1)*scale_y), self.original_height)
                
                for x in range(self.width):
                    src_x = int(x * scale_x)
                    x_end = min(int((x+1)*scale_x), self.original_width)
                    
                    if x_end <= src_x or y_end <= src_y:
                        avg_color = (255, 255, 255)
                    else:
                        region = self.pixels[src_y:y_end, src_x:x_end]
                        if region.size == 0:
                            avg_color = (255, 255, 255)
                        else:
                            avg_color = tuple(np.mean(region, axis=(0, 1)).astype(int))
                    
                    block_name, block_data = self.find_closest_color(avg_color)
                    if block_name in self.block_palette:
                        block_index = self.block_palette.index(block_name)
                    else:
                        block_index = 0
                    
                    self.block_data[0, y, x] = block_index
                    self.block_data_values[0, y, x] = block_data
                
                progress.update(y + 1)
            
            progress.complete()
            
        else:  # 大图片，使用并发
            # 计算最优的块大小（每块至少包含100行像素）
            min_chunk_size = max(1, min(100, self.height // 4))
            max_workers = min(os.cpu_count() or 4, self.height // min_chunk_size)
            max_workers = max(1, max_workers)  # 确保至少1个worker
            
            # 调整块大小，使每个worker有足够的工作量
            chunk_size = max(min_chunk_size, (self.height + max_workers - 1) // max_workers)
            
            threads_msg = self.get_text('stats.using_threads', '使用 {} 个线程，块大小: {} 行').format(max_workers, chunk_size)
            print(f"{Color.CYAN}🔧 {threads_msg}{Color.RESET}")
            
            # 创建分块
            chunks = []
            for i in range(0, self.height, chunk_size):
                end_y = min(i + chunk_size, self.height)
                chunks.append((i, end_y, scale_x, scale_y))
            
            # 进度显示
            progress = ProgressDisplay(len(chunks), self.get_text('conversion.processing_pixels', '处理像素块'), self.config)
            
            # 使用线程池并发处理
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.process_chunk, chunk): i for i, chunk in enumerate(chunks)}
                
                for future in as_completed(futures):
                    try:
                        start_y, end_y, chunk_data, chunk_values = future.result()
                        # 将结果填充到数组中
                        for y_idx, y in enumerate(range(start_y, end_y)):
                            self.block_data[0, y, :] = chunk_data[y_idx]
                            self.block_data_values[0, y, :] = chunk_values[y_idx]
                        
                        progress.increment()
                    except Exception as e:
                        error_msg = self.get_text('error.chunk_processing_failed', '处理块时出错: {}').format(e)
                        print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            
            progress.complete()
        
        completed_msg = self.get_text('conversion.data_generated', '方块数据生成完成')
        print(f"{Color.GREEN}✅ {completed_msg}{Color.RESET}")
    
    def generate_block_data(self):
        """生成方块数据"""
        return self.generate_block_data_concurrent()
    
    def pack_bits_to_long_array_safe(self, indices, bits_per_entry):
        """安全的位打包函数，完全避免大整数运算"""
        mask = (1 << bits_per_entry) - 1
        block_states = []
        
        # 使用固定大小的64位缓冲区
        buffer = 0
        bits_in_buffer = 0
        
        for i, index in enumerate(indices):
            index_value = index & mask
            
            # 将值添加到缓冲区
            buffer = buffer | (index_value << bits_in_buffer)
            bits_in_buffer += bits_per_entry
            
            # 当缓冲区满64位时，写入一个Long值
            if bits_in_buffer >= 64:
                # 提取低64位
                low_64 = buffer & 0xFFFFFFFFFFFFFFFF
                
                # 转换为有符号64位整数
                if low_64 >= (1 << 63):
                    signed_value = low_64 - (1 << 64)
                else:
                    signed_value = low_64
                
                # 添加到列表
                block_states.append(Long(int(signed_value)))
                
                # 移除已写入的位
                buffer = buffer >> 64
                bits_in_buffer -= 64
        
        # 处理剩余的位
        if bits_in_buffer > 0:
            low_64 = buffer & 0xFFFFFFFFFFFFFFFF
            if low_64 >= (1 << 63):
                signed_value = low_64 - (1 << 64)
            else:
                signed_value = low_64
            block_states.append(Long(int(signed_value)))
        
        return block_states
    
    def pack_bits_to_long_array_safe_alternative(self, indices, bits_per_entry):
        """另一种安全方法：使用小整数逐步构建"""
        mask = (1 << bits_per_entry) - 1
        block_states = []
        
        # 计算需要多少个64位整数
        total_bits = len(indices) * bits_per_entry
        num_longs = (total_bits + 63) // 64
        
        # 预先分配数组
        for _ in range(num_longs):
            block_states.append(Long(0))
        
        # 直接填充每个位置
        for i, index in enumerate(indices):
            index_value = index & mask
            bit_pos = i * bits_per_entry
            long_index = bit_pos // 64
            bit_offset = bit_pos % 64
            
            # 如果值跨越两个long
            if bit_offset + bits_per_entry > 64:
                # 第一部分在当前long
                bits_in_current = 64 - bit_offset
                current_part = index_value & ((1 << bits_in_current) - 1)
                
                # 更新当前long
                current_val = int(block_states[long_index])
                current_val |= (current_part << bit_offset)
                block_states[long_index] = Long(current_val)
                
                # 第二部分在下一个long
                next_part = index_value >> bits_in_current
                next_val = int(block_states[long_index + 1])
                next_val |= next_part
                block_states[long_index + 1] = Long(next_val)
            else:
                # 值完全在当前long内
                current_val = int(block_states[long_index])
                current_val |= (index_value << bit_offset)
                block_states[long_index] = Long(current_val)
        
        return block_states
    
    def pack_bits_to_long_array_optimized(self, indices, bits_per_entry):
        """优化的位打包方法，避免大整数运算"""
        mask = (1 << bits_per_entry) - 1
        block_states = []
        
        # 预先计算需要多少个Long
        total_bits = len(indices) * bits_per_entry
        num_longs = (total_bits + 63) // 64
        
        # 使用数组存储部分结果
        long_bits = [0] * num_longs
        
        for i, index in enumerate(indices):
            index_value = index & mask
            bit_pos = i * bits_per_entry
            long_idx = bit_pos // 64
            bit_offset = bit_pos % 64
            
            # 将值分割成多个部分，每个部分不超过64位
            remaining_bits = bits_per_entry
            value = index_value
            
            while remaining_bits > 0:
                bits_in_this_long = min(remaining_bits, 64 - bit_offset)
                
                # 提取当前部分
                part_mask = (1 << bits_in_this_long) - 1
                part = value & part_mask
                
                # 添加到当前Long
                long_bits[long_idx] |= (part << bit_offset)
                
                # 更新状态
                value >>= bits_in_this_long
                remaining_bits -= bits_in_this_long
                bit_offset = 0
                long_idx += 1
        
        # 转换为Long对象
        for val in long_bits:
            # 处理有符号64位整数
            if val >= (1 << 63):
                signed_val = val - (1 << 64)
            else:
                signed_val = val
            block_states.append(Long(int(signed_val)))
        
        return block_states
    
    def save_litematic(self, output_path):
        """保存为Litematica格式文件"""
        saving_msg = self.get_text('conversion.saving_file', '正在保存litematic文件...').format(self.get_text('format.litematic', 'Litematica'))
        print(f"{Color.CYAN}💾 {saving_msg}{Color.RESET}")
        
        # 修复BUG：确保后缀名是.litematic而不是.litematica
        if output_path.lower().endswith('.litematica'):
            output_path = output_path[:-1]  # 移除多余的 'a'
        elif not output_path.lower().endswith('.litematic'):
            output_path += '.litematic'
        
        # 创建Litematica v6格式
        # 使用nbtlib的List类而不是typing.List
        litematica_data = Compound({
            "Version": Int(6),  # Go版本使用Version 6
            "MinecraftDataVersion": Int(3100),  # 数据版本
            "SubVersion": Int(1),  # 子版本
            "Metadata": Compound({
                "Author": String("SunPixel"),
                "Description": String("Generated by SunPixel"),
                "Name": String(Path(output_path).stem),
                "EnclosingSize": Compound({
                    "x": Int(self.width),
                    "y": Int(self.depth),
                    "z": Int(self.height)
                }),
                "RegionCount": Int(1),
                "TimeCreated": Long(int(time.time() * 1000)),
                "TimeModified": Long(int(time.time() * 1000)),
                "TotalBlocks": Int(self.width * self.height * self.depth),
                "TotalVolume": Int(self.width * self.height * self.depth)
            }),
            "Regions": Compound({
                "region": Compound({  # Go版本使用"region"作为区域名
                    "Position": Compound({
                        "x": Int(0),
                        "y": Int(0),
                        "z": Int(0)
                    }),
                    "Size": Compound({
                        "x": Int(self.width),
                        "y": Int(self.depth),
                        "z": Int(self.height)
                    }),
                    "BlockStatePalette": NBTList[Compound](),  # 使用nbtlib的List类
                    "BlockStates": nbtlib.LongArray([]),
                    "Entities": NBTList[Compound]([]),  # 使用nbtlib的List类
                    "TileEntities": NBTList[Compound]([])  # 使用nbtlib的List类
                })
            })
        })
        
        # 添加方块状态调色板
        region_data = litematica_data["Regions"]["region"]
        palette = region_data["BlockStatePalette"]
        
        for block_name in self.block_palette:
            block_state = Compound({
                "Name": String(block_name)
            })
            palette.append(block_state)
        
        # 生成方块索引数据
        palette_size = len(self.block_palette)
        bits_per_entry = max((palette_size - 1).bit_length(), 4)  # 最小4位
        
        bits_msg = self.get_text('stats.bits_per_entry', '位每条目: {}位，调色板大小: {}').format(bits_per_entry, palette_size)
        print(f"{Color.CYAN}🔢 {bits_msg}{Color.RESET}")
        
        # 生成方块状态索引（按z,y,x顺序）
        block_indices = []
        for y in range(self.height):
            for x in range(self.width):
                block_index = self.block_data[0, y, x]
                block_indices.append(block_index)
        
        packing_msg = self.get_text('stats.packing_blocks', '正在打包 {} 个方块索引...').format(len(block_indices))
        print(f"{Color.CYAN}📊 {packing_msg}{Color.RESET}")
        
        # 使用优化的位打包函数，完全避免大整数运算
        try:
            block_states = self.pack_bits_to_long_array_optimized(block_indices, bits_per_entry)
        except OverflowError:
            print(f"{Color.YELLOW}⚠️  使用备选打包方法...{Color.RESET}")
            block_states = self.pack_bits_to_long_array_safe_alternative(block_indices, bits_per_entry)
        
        # 设置BlockStates（Go版本不存储BitsPerEntry）
        region_data["BlockStates"] = nbtlib.LongArray(block_states)
        
        # 保存NBT文件
        nbt_file = nbtlib.File(litematica_data)
        nbt_file.save(output_path, gzipped=True)
        
        saved_msg = self.get_text('conversion.file_saved', 'litematic文件保存完成: {}').format(output_path)
        print(f"{Color.GREEN}✅ {saved_msg}{Color.RESET}")
        
        info_msg = self.get_text('stats.file_info', '文件信息: {}个Long, {}个方块索引').format(len(block_states), len(block_indices))
        print(f"{Color.CYAN}📊 {info_msg}{Color.RESET}")
        
        return self.width, self.height, self.width * self.height
    
    def convert(self, input_image, output_path, width=None, height=None, selected_blocks=None):
        """转换入口函数"""
        if selected_blocks is None:
            selected_blocks = []
            
        starting_msg = self.get_text('conversion.starting', '开始转换流程...')
        print(f"{Color.CYAN}🚀 {starting_msg}{Color.RESET}")
        
        if not self.load_block_mappings(selected_blocks):
            return None
            
        try:
            self.load_image(input_image)
            
            if width is None or height is None:
                self.set_size(self.original_width, self.original_height)
            else:
                best_width, best_height = self.calculate_best_ratio(width, height)
                
                if best_width != width or best_height != height:
                    suggested_msg = self.get_text('ui.suggested_size', '建议使用保持比例的最佳尺寸: {}x{} (原图比例 {}:{})').format(
                        best_width, best_height, self.original_width, self.original_height)
                    print(f"\n{Color.YELLOW}⚠️  {suggested_msg}{Color.RESET}")
                    use_suggested = self.get_text('ui.use_suggested_size', '是否使用建议尺寸? (y/n): ')
                    choice = input(use_suggested).strip().lower()
                    if choice == 'y':
                        self.set_size(best_width, best_height)
                    else:
                        self.set_size(width, height)
                else:
                    self.set_size(width, height)
                
            self.generate_block_data()
            
            # 验证数据
            non_air_blocks = np.sum(self.block_data != 0)
            stats_msg = self.get_text('stats.structure_size', '数据统计:\n  总方块数: {}\n  非空气方块数: {}\n  空气方块数: {}')
            print(f"{Color.CYAN}📊 {stats_msg.format(self.width * self.height, non_air_blocks, self.width * self.height - non_air_blocks)}{Color.RESET}")
            
            return self.save_litematic(output_path)
            
        except Exception as e:
            error_msg = self.get_text('conversion.failed', '转换过程中发生错误: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return None

# 兼容性别名
Converter = Litematic
LitematicaConverter = Litematic