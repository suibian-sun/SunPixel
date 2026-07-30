import json
import os
import time
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union
import sys

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

class FuHong:
    """FuHong V1 结构文件对象"""
    def __init__(self):
        self.blocks: list = TypeCheckList().setChecker(dict)
        self.name = ""
        self.author = ""
        self.description = ""
        self.version = "1.0"

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            super().__setattr__(name, value)
        elif isinstance(value, type(getattr(self, name))):
            super().__setattr__(name, value)
        else:
            raise Exception(f"无法修改 {name} 属性")

    def __delattr__(self, name):
        raise Exception("无法删除任何属性")

    def error_check(self):
        """检查数据有效性"""
        for block in self.blocks:
            # 检查 name 字段
            if not isinstance(block.get("name", None), str):
                raise Exception("方块数据缺少或存在错误的 name 参数")
            
            # 处理 aux 字段
            aux_value = block.get("aux", 0)
            if aux_value is not None:
                if not isinstance(aux_value, int):
                    try:
                        block["aux"] = int(aux_value)
                    except (ValueError, TypeError):
                        block["aux"] = 0
            else:
                block["aux"] = 0
            
            # 处理 x 坐标（支持单个值或数组）
            x_value = block.get("x", 0)
            if not isinstance(x_value, (int, list)):
                raise Exception("方块数据存在错误的 x 参数")
            
            # 处理 y 坐标（支持单个值或数组）
            y_value = block.get("y", 0)
            if not isinstance(y_value, (int, list)):
                raise Exception("方块数据存在错误的 y 参数")
            
            # 处理 z 坐标（支持单个值或数组）
            z_value = block.get("z", 0)
            if not isinstance(z_value, (int, list)):
                raise Exception("方块数据存在错误的 z 参数")

    def save_as(self, buffer):
        """保存为 FuHong V1 格式文件"""
        self.error_check()

        # 构建完整的 FuHong V1 结构
        structure_data = {
            "format": "FuHongV1",
            "version": self.version,
            "name": self.name,
            "author": self.author,
            "description": self.description,
            "blocks": list(self.blocks)
        }

        if isinstance(buffer, str):
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(buffer)), exist_ok=True)
            _file = open(buffer, "w+", encoding="utf-8")
        else:
            _file = buffer

        json.dump(structure_data, _file, indent=2, ensure_ascii=False)
        
        if isinstance(buffer, str):
            _file.close()

class FuHongConverter:
    """FuHong格式转换器"""
    def __init__(self, config):
        self.config = config
        self.color_to_block = {}
        self.block_palette = []
        self.original_width = 0
        self.original_height = 0
        self.width = 0
        self.height = 0
        self.depth = 1
        self.pixels = None
        self.language_manager = config.get_language_manager() if hasattr(config, 'get_language_manager') else None
        
    def get_text(self, key, default=None):
        """获取翻译文本"""
        if self.language_manager:
            return self.language_manager.get(key, default)
        return default if default is not None else key
        
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
                                if isinstance(block_info, list) and len(block_info) >= 2:
                                    # 确保aux值是整数
                                    block_name = block_info[0]
                                    aux_value = block_info[1]
                                    try:
                                        aux_int = int(aux_value)
                                    except (ValueError, TypeError):
                                        aux_int = 0
                                    
                                    # 处理颜色键
                                    color_str = str(color_key)
                                    if color_str.startswith('(') and color_str.endswith(')'):
                                        color_str = color_str[1:-1]
                                    processed_block_data[color_str] = [block_name, aux_int]
                            
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
        
    def load_image(self, image_path):
        """加载图片"""
        loading_msg = self.get_text('conversion.loading_image', '正在加载图片...')
        print(f"{Color.CYAN}🖼️  {loading_msg}{Color.RESET}")
       
        try:
            from PIL import Image
            img = Image.open(image_path)
            img = img.convert('RGB')
            self.original_width, self.original_height = img.size
            self.pixels = img.load()
            
            loaded_msg = self.get_text('conversion.image_loaded', '图片加载完成: {} × {} 像素').format(
                self.original_width, self.original_height)
            print(f"{Color.GREEN}✅ {loaded_msg}{Color.RESET}")
            return True
        except ImportError:
            error_msg = self.get_text('error.pil_not_installed', '请安装Pillow库: pip install Pillow')
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            return False
        except Exception as e:
            error_msg = self.get_text('error.image_load_failed', '加载图片失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            return False
    
    def set_size(self, width, height):
        """设置生成结构的尺寸"""
        self.width = max(1, width)
        self.height = max(1, height)
        size_msg = self.get_text('conversion.setting_size', '设置生成尺寸: {} × {} 方块').format(self.width, self.height)
        print(f"{Color.CYAN}📐 {size_msg}{Color.RESET}")
    
    def color_distance(self, c1, c2):
        """计算两个颜色之间的感知距离"""
        r1, g1, b1 = c1
        r2, g2, b2 = c2
        r_mean = (r1 + r2) // 2
        
        r_diff = r1 - r2
        g_diff = g1 - g2
        b_diff = b1 - b2
        
        return math.sqrt(
            (2 + r_mean//256) * (r_diff*r_diff) +
            4 * (g_diff*g_diff) +
            (2 + (255 - r_mean)//256) * (b_diff*b_diff)
        )
    
    def find_closest_color(self, color):
        """找到最接近的颜色映射"""
        r, g, b = color
        closest_color = None
        min_distance = float('inf')
        
        for color_str, block_info in self.color_to_block.items():
            try:
                # 解析颜色字符串
                if ',' in color_str:
                    color_values = [int(x.strip()) for x in color_str.split(',')]
                    target_color = tuple(color_values[:3])
                else:
                    continue
                    
                distance = self.color_distance((r, g, b), target_color)
                if distance < min_distance:
                    min_distance = distance
                    closest_color = color_str
            except Exception:
                continue
        
        if closest_color and closest_color in self.color_to_block:
            block_info = self.color_to_block[closest_color]
            if isinstance(block_info, list) and len(block_info) >= 2:
                block_name = block_info[0]
                aux_value = block_info[1]
                try:
                    aux_int = int(aux_value)
                except (ValueError, TypeError):
                    aux_int = 0
                return block_name, aux_int
        
        return "minecraft:white_concrete", 0
    
    def generate_block_data(self):
        """生成方块数据"""
        generating_msg = self.get_text('conversion.generating_data', '正在生成方块数据...')
        print(f"{Color.CYAN}🔨 {generating_msg}{Color.RESET}")
        
        blocks = []
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        progress = ProgressDisplay(self.height, self.get_text('progress.processing_pixels', '处理像素行'), self.config)
        
        for y in range(self.height):
            src_y = int(y * scale_y)
            for x in range(self.width):
                src_x = int(x * scale_x)
                
                # 获取像素颜色
                if hasattr(self.pixels, '__getitem__'):
                    try:
                        color = self.pixels[src_x, src_y]
                        if isinstance(color, int):
                            # 单通道图像
                            color = (color, color, color)
                        elif len(color) == 4:
                            # RGBA图像，忽略Alpha通道
                            color = color[:3]
                    except:
                        color = (255, 255, 255)
                else:
                    color = (255, 255, 255)
                
                # 查找对应的方块
                block_name, block_data = self.find_closest_color(color)
                
                # 创建方块数据（使用FuHong V1格式）
                block = {
                    "name": block_name,
                    "aux": block_data,
                    "x": x,  # FuHong V1格式支持数组
                    "y": 0,  # 单层结构
                    "z": y   # FuHong V1格式支持数组
                }
                blocks.append(block)
            
            progress.update(y + 1)
        
        progress.complete()
        
        completed_msg = self.get_text('conversion.data_generated', '方块数据生成完成')
        print(f"{Color.GREEN}✅ {completed_msg}{Color.RESET}")
        
        return blocks
    
    def convert(self, input_image, output_path, width=None, height=None, selected_blocks=None,
                structure_name="", author="", description=""):
        """转换入口函数"""
        if selected_blocks is None:
            selected_blocks = []
            
        starting_msg = self.get_text('conversion.starting', '开始转换流程...')
        print(f"{Color.CYAN}🚀 {starting_msg}{Color.RESET}")
        
        if not self.load_block_mappings(selected_blocks):
            return None
        
        if not self.load_image(input_image):
            return None
        
        # 设置尺寸
        if width is None or height is None:
            self.set_size(self.original_width, self.original_height)
        else:
            self.set_size(width, height)
        
        # 生成方块数据
        blocks = self.generate_block_data()
        
        # 保存为FuHong格式
        return self.save_fuhong(output_path, blocks, structure_name, author, description)
    
    def save_fuhong(self, output_path, blocks, structure_name="", author="", description=""):
        """保存为FuHong V1格式文件"""
        saving_msg = self.get_text('conversion.saving_file', '正在保存FuHong文件...').format(
            self.get_text('format.fuhong', 'FuHong'))
        print(f"{Color.CYAN}💾 {saving_msg}{Color.RESET}")
        
        if not output_path.lower().endswith('.json'):
            output_path += '.json'
        
        # 创建FuHong对象
        fuhong = FuHong()
        fuhong.name = structure_name or "Generated Structure"
        fuhong.author = author or "Unknown"
        fuhong.description = description or f"Converted from image, size: {self.width}x{self.height}"
        
        # 添加方块数据
        total_blocks = len(blocks)
        progress = ProgressDisplay(total_blocks, self.get_text('message.saving', '保存方块'), self.config)
        
        batch_size = 1000
        for i in range(0, total_blocks, batch_size):
            batch = blocks[i:i+batch_size]
            fuhong.blocks.extend(batch)
            progress.update(min(i+batch_size, total_blocks))
        
        progress.complete()
        
        # 保存文件
        fuhong.save_as(output_path)
        
        saved_msg = self.get_text('conversion.file_saved', 'FuHong文件保存完成: {}').format(output_path)
        print(f"{Color.GREEN}✅ {saved_msg}{Color.RESET}")
        
        return self.width, self.height, total_blocks

# 兼容性别名
Converter = FuHongConverter