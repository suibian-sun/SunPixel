import numpy as np
import png
from PIL import Image
import os
import time
import math
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional, Any

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
    def __init__(self, total, description, config, language):
        self.total = total
        self.description = description
        self.config = config
        self.language = language
        self.current = 0
        self.start_time = time.time()
        self.use_color = config.getboolean('ui', 'colored_output', True)
        self.last_update = 0
        
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

class TypeCheckList(list):
    """类型检查列表"""
    def __init__(self):
        super().__init__()
        self.checker = None
    
    def setChecker(self, checker):
        self.checker = checker
        return self
    
    def append(self, obj):
        if self.checker and not isinstance(obj, self.checker):
            raise Exception(f"类型错误: 期望 {self.checker}, 得到 {type(obj)}")
        super().append(obj)
    
    def extend(self, iterable):
        for obj in iterable:
            self.append(obj)

class TimeBuilder_V1:
    def __init__(self):
        self.blocks: list = TypeCheckList().setChecker(dict)
        self.version = "TimeBuilder"

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            super().__setattr__(name, value)
        elif isinstance(value, type(getattr(self, name))):
            super().__setattr__(name, value)
        else:
            raise Exception("无法修改 %s 属性" % name)

    def __delattr__(self, name):
        raise Exception("无法删除任何属性")

    def error_check(self):
        """验证方块数据的完整性"""
        if not self.blocks:
            raise Exception("方块数据为空")
            
        for block in self.blocks:
            if not isinstance(block, dict):
                raise Exception("方块数据不为dict参数")
            if not isinstance(block.get("name", None), str):
                raise Exception("方块数据缺少或存在错误 name 参数")
            if not isinstance(block.get("aux", None), int):
                raise Exception("方块数据缺少或存在错误 aux 参数")
            if not isinstance(block.get("pos", None), list):
                raise Exception("方块数据缺少或存在错误 pos 参数")
            
            # 验证pos列表中的每个坐标
            for pos in block.get("pos", []):
                if len(pos) < 3:
                    raise Exception("方块坐标数据数量不足")
                if not isinstance(pos[0], int):
                    raise Exception("方块数据缺少或存在错误 x 参数")
                if not isinstance(pos[1], int):
                    raise Exception("方块数据缺少或存在错误 y 参数")
                if not isinstance(pos[2], int):
                    raise Exception("方块数据缺少或存在错误 z 参数")
                    
                # 验证坐标值范围
                if not (-30000000 <= pos[0] <= 30000000):
                    raise Exception(f"X坐标超出范围: {pos[0]}")
                if not (-30000000 <= pos[1] <= 30000000):
                    raise Exception(f"Y坐标超出范围: {pos[1]}")
                if not (-30000000 <= pos[2] <= 30000000):
                    raise Exception(f"Z坐标超出范围: {pos[2]}")

    def to_dict(self) -> dict:
        """转换为字典格式"""
        self.error_check()
        return {
            "version": self.version,
            "block": list(self.blocks)
        }

    def save_as(self, buffer):
        """保存TimeBuilder格式文件"""
        self.error_check()
        json_data = self.to_dict()

        if isinstance(buffer, str):
            # 确保目录存在
            base_path = os.path.realpath(os.path.join(buffer, os.pardir))
            os.makedirs(base_path, exist_ok=True)
            
            # 确保文件扩展名为.json
            if not buffer.lower().endswith('.json'):
                buffer += '.json'
                
            with open(buffer, "w+", encoding="utf-8") as _file:
                json.dump(json_data, _file, separators=(',', ':'))
        else:
            # 文件对象
            json.dump(json_data, buffer, separators=(',', ':'))
            
        return True

    def add_block_entry(self, name: str, aux: int, positions: List[List[int]]):
        """添加方块条目"""
        self.blocks.append({
            "name": name,
            "aux": aux,
            "pos": positions
        })
        return self

    def get_block_count(self) -> int:
        """获取总方块数"""
        total = 0
        for block in self.blocks:
            total += len(block.get("pos", []))
        return total

    def get_unique_blocks(self) -> List[Tuple[str, int]]:
        """获取唯一的方块类型列表"""
        unique_blocks = set()
        for block in self.blocks:
            unique_blocks.add((block["name"], block["aux"]))
        return list(unique_blocks)

    @classmethod
    def from_file(cls, file_path: str) -> 'TimeBuilder_V1':
        """从文件加载TimeBuilder格式"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if data.get("version") != "TimeBuilder":
            raise Exception(f"不支持或未知的版本: {data.get('version')}")
            
        instance = cls()
        
        # 验证并加载方块数据
        for block_entry in data.get("block", []):
            if not isinstance(block_entry, dict):
                continue
                
            name = block_entry.get("name", "")
            aux = block_entry.get("aux", 0)
            positions = block_entry.get("pos", [])
            
            # 确保aux是整数
            if not isinstance(aux, int):
                try:
                    aux = int(aux)
                except (ValueError, TypeError):
                    aux = 0
            
            # 验证并清理位置数据
            valid_positions = []
            for pos in positions:
                if not isinstance(pos, list) or len(pos) < 3:
                    continue
                    
                # 确保坐标是整数
                try:
                    x = int(pos[0]) if len(pos) > 0 else 0
                    y = int(pos[1]) if len(pos) > 1 else 0
                    z = int(pos[2]) if len(pos) > 2 else 0
                    valid_positions.append([x, y, z])
                except (ValueError, TypeError):
                    continue
                    
            if valid_positions:
                instance.add_block_entry(name, aux, valid_positions)
                
        return instance

    def calculate_bounds(self) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """计算结构的边界"""
        min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
        max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
        
        for block in self.blocks:
            for pos in block.get("pos", []):
                if len(pos) >= 3:
                    x, y, z = pos[0], pos[1], pos[2]
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    min_z = min(min_z, z)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
                    max_z = max(max_z, z)
                    
        # 如果没有找到坐标，返回默认值
        if min_x == float('inf'):
            min_x = min_y = min_z = 0
        if max_x == float('-inf'):
            max_x = max_y = max_z = 0
            
        return (int(min_x), int(min_y), int(min_z)), (int(max_x), int(max_y), int(max_z))

    def get_size(self) -> Dict[str, int]:
        """获取结构尺寸"""
        min_coords, max_coords = self.calculate_bounds()
        width = max_coords[0] - min_coords[0] + 1
        height = max_coords[1] - min_coords[1] + 1
        length = max_coords[2] - min_coords[2] + 1
        
        return {
            "width": width,
            "height": height,
            "length": length,
            "min": min_coords,
            "max": max_coords
        }

class TimeBuilderConverter:
    """TimeBuilder格式转换器"""
    def __init__(self, config, language):
        self.config = config
        self.language = language
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
        
    def _t(self, key, *args):
        """翻译文本"""
        text = self.language.get(key, key)
        if args:
            try:
                return text.format(*args)
            except:
                return text
        return text
        
    def load_block_mappings(self, selected_blocks):
        """从block目录加载选中的方块映射"""
        self.color_to_block = {}
        block_dir = Path("block")
        
        if not block_dir.exists():
            print(f"{Color.RED}❌ {self._t('file.block_dir_not_found')}{Color.RESET}")
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
                            
                            # 规范化方块数据，确保aux是整数
                            processed_block_data = {}
                            for color_key, block_info in block_data.items():
                                if isinstance(color_key, str):
                                    if isinstance(block_info, list) and len(block_info) >= 2:
                                        # 确保aux值是整数
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
                            print(f"{Color.GREEN}✅ {self._t('file.block_mappings_loaded', block_name)}{Color.RESET}")
                        else:
                            print(f"{Color.YELLOW}❌ {self._t('file.invalid_json', block_file.name)}{Color.RESET}")
                except Exception as e:
                    print(f"{Color.RED}❌ {self._t('file.load_error', block_file.name, str(e))}{Color.RESET}")
        
        if not self.color_to_block:
            print(f"{Color.RED}❌ {self._t('file.no_mappings_loaded')}{Color.RESET}")
            return False
            
        print(f"{Color.GREEN}✅ {self._t('file.total_mappings_loaded', len(self.color_to_block))}{Color.RESET}")
        return True
        
    def color_distance(self, c1, c2):
        """计算两个颜色之间的感知距离（修复版）"""
        # 确保颜色值为有符号整数
        r1, g1, b1 = [int(x) for x in c1[:3]]
        r2, g2, b2 = [int(x) for x in c2[:3]]
        
        # 计算平均值
        r_mean = (r1 + r2) // 2
        
        # 计算差值
        r_diff = r1 - r2
        g_diff = g1 - g2
        b_diff = b1 - b2
        
        # 使用感知颜色距离公式
        return math.sqrt(
            (2 + r_mean / 256.0) * (r_diff * r_diff) +
            4 * (g_diff * g_diff) +
            (2 + (255 - r_mean) / 256.0) * (b_diff * b_diff)
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
        """加载图片"""
        print(f"{Color.CYAN}🖼️  {self._t('conversion.loading_image')}{Color.RESET}")
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
        
        print(f"{Color.GREEN}✅ {self._t('conversion.image_loaded', self.original_width, self.original_height)}{Color.RESET}")
            
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
        print(f"{Color.CYAN}📐 {self._t('conversion.setting_size', self.width, self.height)}{Color.RESET}")
            
    def process_chunk(self, chunk_info):
        """处理一个像素块"""
        start_y, end_y, scale_x, scale_y = chunk_info
        
        # 用于按方块类型分组
        block_groups = {}
        
        # 预计算颜色查找表
        color_cache = {}
        
        for y in range(start_y, end_y):
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
                        # 使用整数运算提高性能，但确保结果为整数元组
                        avg_color = tuple(np.mean(region, axis=(0, 1)).astype(int))
                
                # 使用缓存提高性能
                color_key = avg_color
                if color_key in color_cache:
                    block_name, block_data = color_cache[color_key]
                else:
                    block_name, block_data = self.find_closest_color(avg_color)
                    color_cache[color_key] = (block_name, block_data)
                
                if block_name:
                    # 创建组合键 (方块名 + 数据值)
                    block_key = f"{block_name}:{block_data}"
                    
                    if block_key not in block_groups:
                        block_groups[block_key] = {
                            "name": block_name,
                            "aux": block_data,
                            "pos": []
                        }
                    
                    # 添加位置 (x, y, z) - 根据TimeBuilder V1格式，图片像素对应(x, 0, z)
                    # 这里y=0表示单层结构，z对应图片的y轴
                    block_groups[block_key]["pos"].append([x, 0, y])
        
        return start_y, end_y, block_groups
    
    def generate_block_data_concurrent(self):
        """并发生成方块数据"""
        print(f"{Color.CYAN}🔨 {self._t('conversion.generating_data')}{Color.RESET}")
        
        # 初始化调色板
        self.block_palette = []
        for block_info in self.color_to_block.values():
            if isinstance(block_info, list) and len(block_info) >= 1:
                block_name = block_info[0]
                if block_name not in self.block_palette:
                    self.block_palette.append(block_name)
                    
        print(f"{Color.CYAN}🎨 {self._t('conversion.palette_initialized', len(self.block_palette))}{Color.RESET}")
        
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        print(f"{Color.CYAN}🔄 {self._t('conversion.processing_pixels')}{Color.RESET}")
        
        # 动态确定最优的并发策略
        total_pixels = self.width * self.height
        
        # 根据图片大小决定是否使用并发
        if total_pixels < 10000:  # 小图片，不使用并发
            print(f"{Color.CYAN}📱 小图片({total_pixels}像素)，使用单线程处理{Color.RESET}")
            
            # 单线程处理
            progress = ProgressDisplay(self.height, self._t('progress.processing_pixels'), self.config, self.language)
            
            # 用于按方块类型分组
            block_groups = {}
            color_cache = {}
            
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
                    
                    # 使用缓存提高性能
                    color_key = avg_color
                    if color_key in color_cache:
                        block_name, block_data = color_cache[color_key]
                    else:
                        block_name, block_data = self.find_closest_color(avg_color)
                        color_cache[color_key] = (block_name, block_data)
                    
                    if block_name:
                        # 创建组合键 (方块名 + 数据值)
                        block_key = f"{block_name}:{block_data}"
                        
                        if block_key not in block_groups:
                            block_groups[block_key] = {
                                "name": block_name,
                                "aux": block_data,
                                "pos": []
                            }
                        
                        # 添加位置 (x, y, z) - 注意TimeBuilder使用Y为高度
                        block_groups[block_key]["pos"].append([x, 0, y])
                
                progress.update(y + 1)
            
            progress.complete()
            return block_groups
            
        else:  # 大图片，使用并发
            # 计算最优的块大小（每块至少包含100行像素）
            min_chunk_size = max(1, min(100, self.height // 4))
            max_workers = min(os.cpu_count() or 4, self.height // min_chunk_size)
            max_workers = max(1, max_workers)  # 确保至少1个worker
            
            # 调整块大小，使每个worker有足够的工作量
            chunk_size = max(min_chunk_size, (self.height + max_workers - 1) // max_workers)
            
            print(f"{Color.CYAN}🔧 使用 {max_workers} 个线程，块大小: {chunk_size} 行{Color.RESET}")
            
            # 创建分块
            chunks = []
            for i in range(0, self.height, chunk_size):
                end_y = min(i + chunk_size, self.height)
                chunks.append((i, end_y, scale_x, scale_y))
            
            # 进度显示
            progress = ProgressDisplay(len(chunks), "处理像素块", self.config, self.language)
            
            # 合并所有分块的方块组
            all_block_groups = {}
            
            # 使用线程池并发处理
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.process_chunk, chunk): i for i, chunk in enumerate(chunks)}
                
                for future in as_completed(futures):
                    try:
                        start_y, end_y, chunk_block_groups = future.result()
                        
                        # 合并方块组
                        for block_key, block_info in chunk_block_groups.items():
                            if block_key not in all_block_groups:
                                all_block_groups[block_key] = {
                                    "name": block_info["name"],
                                    "aux": block_info["aux"],
                                    "pos": []
                                }
                            all_block_groups[block_key]["pos"].extend(block_info["pos"])
                        
                        progress.increment()
                    except Exception as e:
                        print(f"{Color.RED}❌ 处理块时出错: {e}{Color.RESET}")
            
            progress.complete()
            return all_block_groups
        
        print(f"{Color.GREEN}✅ {self._t('conversion.data_generated')}{Color.RESET}")
    
    def generate_block_data(self):
        """生成方块数据（兼容性方法）"""
        return self.generate_block_data_concurrent()

    def convert(self, input_image, output_path, width=None, height=None, selected_blocks=None):
        """转换入口函数"""
        if selected_blocks is None:
            selected_blocks = []
            
        print(f"{Color.CYAN}🚀 {self._t('conversion.starting')}{Color.RESET}")
        
        if not self.load_block_mappings(selected_blocks):
            return None
            
        try:
            self.load_image(input_image)
            
            if width is None or height is None:
                self.set_size(self.original_width, self.original_height)
            else:
                best_width, best_height = self.calculate_best_ratio(width, height)
                
                if best_width != width or best_height != height:
                    print(f"\n{Color.YELLOW}⚠️  {self._t('ui.suggested_size', best_width, best_height, self.original_width, self.original_height)}{Color.RESET}")
                    choice = input(f"{self._t('ui.use_suggested_size')} ").strip().lower()
                    if choice == 'y':
                        self.set_size(best_width, best_height)
                    else:
                        self.set_size(width, height)
                else:
                    self.set_size(width, height)
                
            block_groups = self.generate_block_data()
            return self.save_timebuilder(output_path, block_groups)
        except Exception as e:
            print(f"{Color.RED}❌ {self._t('conversion.failed', str(e))}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_timebuilder(self, output_path, block_groups):
        """保存为TimeBuilder格式文件"""
        print(f"{Color.CYAN}💾 {self._t('conversion.saving_file', self._t('format.timebuilder'))}{Color.RESET}")
        
        if not output_path.lower().endswith('.json'):
            output_path += '.json'
        
        timebuilder = TimeBuilder_V1()
        
        # 将分组后的方块添加到timebuilder对象
        total_blocks = 0
        for block_info in block_groups.values():
            timebuilder.blocks.append(block_info)
            total_blocks += len(block_info["pos"])
        
        timebuilder.save_as(output_path)
        
        # 计算边界信息
        bounds = timebuilder.calculate_bounds()
        size = timebuilder.get_size()
        
        print(f"{Color.GREEN}✅ {self._t('conversion.file_saved', output_path)}{Color.RESET}")
        print(f"{Color.CYAN}📊 包含 {len(block_groups)} 种方块类型，总计 {total_blocks} 个方块{Color.RESET}")
        print(f"{Color.CYAN}📍 边界: 最小 {bounds[0]}, 最大 {bounds[1]}{Color.RESET}")
        print(f"{Color.CYAN}📏 尺寸: {size['width']}x{size['height']}x{size['length']}{Color.RESET}")
        
        return self.width, self.height, total_blocks

# 实用函数
def floor_div(a: int, b: int) -> int:
    """向下取整除法，与Go版本兼容"""
    return a // b

# 兼容性别名
Converter = TimeBuilderConverter