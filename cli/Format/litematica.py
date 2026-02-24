import numpy as np
import png
from PIL import Image
import os
import time
import math
import json
from pathlib import Path
import sys
import threading
import nbtlib
from nbtlib.tag import Byte, Short, Int, Long, Float, Double, String, List, Compound

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

class ProgressDisplay(threading.Thread):
    """实时进度显示线程"""
    def __init__(self, total, description, config):
        super().__init__()
        self.total = total
        self.description = description
        self.config = config
        self.current = 0
        self.running = True
        self.daemon = True
        
    def update(self, value):
        """更新进度"""
        self.current = value
        
    def stop(self):
        """停止进度显示"""
        self.running = False
        
    def run(self):
        """运行进度显示"""
        use_color = self.config.getboolean('ui', 'colored_output', True)
        
        while self.running and self.current < self.total:
            progress = (self.current / self.total) * 100
            bar_length = 30
            filled_length = int(bar_length * self.current // self.total)
            
            if use_color:
                bar = f'{Color.GREEN}█{Color.RESET}' * filled_length + f'{Color.GRAY}░{Color.RESET}' * (bar_length - filled_length)
            else:
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            sys.stdout.write(f'\r📊 {self.description}: [{bar}] {self.current}/{self.total} ({progress:.1f}%)')
            sys.stdout.flush()
            time.sleep(0.1)
        
        if self.current >= self.total:
            progress = 100.0
            bar_length = 30
            if use_color:
                bar = f'{Color.GREEN}█{Color.RESET}' * bar_length
            else:
                bar = '█' * bar_length
            sys.stdout.write(f'\r📊 {self.description}: [{bar}] {self.current}/{self.total} ({progress:.1f}%) ✅\n')
            sys.stdout.flush()

class LitematicaConverter:
    """Litematica格式转换器"""
    def __init__(self, config):
        self.config = config
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
        
    def load_block_mappings(self, selected_blocks):
        """从block目录加载选中的方块映射"""
        self.color_to_block = {}
        block_dir = Path("block")
        
        if not block_dir.exists():
            print(f"{Color.RED}❌ 错误: block目录不存在!{Color.RESET}")
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
                            
                            processed_block_data = {}
                            for color_key, block_info in block_data.items():
                                if isinstance(color_key, str):
                                    processed_block_data[color_key] = block_info
                                else:
                                    processed_block_data[str(color_key)] = block_info
                            
                            self.color_to_block.update(processed_block_data)
                            print(f"{Color.GREEN}✅ 已加载: {block_name}{Color.RESET}")
                        else:
                            print(f"{Color.YELLOW}❌ 文件 {block_file} 中没有有效的JSON内容{Color.RESET}")
                except Exception as e:
                    print(f"{Color.RED}❌ 加载 {block_file} 时出错: {e}{Color.RESET}")
        
        if not self.color_to_block:
            print(f"{Color.RED}❌ 错误: 没有加载任何方块映射!{Color.RESET}")
            return False
            
        print(f"{Color.GREEN}✅ 总共加载 {len(self.color_to_block)} 种颜色映射{Color.RESET}")
        return True
        
    def color_distance(self, c1, c2):
        """计算两个颜色之间的感知距离"""
        r1, g1, b1 = c1
        r2, g2, b2 = c2
        r_mean = (r1 + r2) / 2
        
        r_diff = r1 - r2
        g_diff = g1 - g2
        b_diff = b1 - b2
        
        return math.sqrt(
            (2 + r_mean/256) * (r_diff**2) +
            4 * (g_diff**2) +
            (2 + (255 - r_mean)/256) * (b_diff**2)
        )
        
    def find_closest_color(self, color):
        """找到最接近的颜色映射"""
        r, g, b = color[:3]
        closest_color = None
        min_distance = float('inf')
        
        for target_color_str in self.color_to_block:
            try:
                if target_color_str.startswith('(') and target_color_str.endswith(')'):
                    color_str = target_color_str[1:-1]
                    color_values = [int(x.strip()) for x in color_str.split(',')]
                    target_color = tuple(color_values[:3])
                else:
                    color_values = [int(x.strip()) for x in target_color_str.split(',')]
                    target_color = tuple(color_values[:3])
                
                distance = self.color_distance((r, g, b), target_color)
                if distance < min_distance:
                    min_distance = distance
                    closest_color = target_color_str
            except Exception:
                continue
                
        if closest_color:
            block_info = self.color_to_block[closest_color]
            if isinstance(block_info, list) and len(block_info) >= 2:
                return block_info[0], block_info[1]
            else:
                return "minecraft:white_concrete", 0
        else:
            return "minecraft:white_concrete", 0
    
    def load_image(self, image_path):
        """加载图片，支持PNG和JPG格式"""
        print(f"{Color.CYAN}🖼️  正在加载图片...{Color.RESET}")
        ext = os.path.splitext(image_path)[1].lower()
        
        if ext == '.png':
            reader = png.Reader(filename=image_path)
            width, height, pixels, metadata = reader.asDirect()
            
            image_data = []
            for row in pixels:
                image_data.append(row)
            
            if metadata['alpha']:
                self.pixels = np.array(image_data, dtype=np.uint8).reshape(height, width, 4)[:, :, :3]
            else:
                self.pixels = np.array(image_data, dtype=np.uint8).reshape(height, width, 3)
                
            self.original_width = width
            self.original_height = height
            
        elif ext in ('.jpg', '.jpeg'):
            img = Image.open(image_path)
            img = img.convert('RGB')
            self.original_width, self.original_height = img.size
            self.pixels = np.array(img)
            
        else:
            raise ValueError(f"不支持的图片格式: {ext}")
        
        print(f"{Color.GREEN}✅ 图片加载完成: {self.original_width} × {self.original_height} 像素{Color.RESET}")
            
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
        print(f"{Color.CYAN}📐 设置生成尺寸: {self.width} × {self.height} 方块{Color.RESET}")
            
    def generate_block_data(self):
        """生成方块数据"""
        print(f"{Color.CYAN}🔨 正在生成方块数据...{Color.RESET}")
        
        self.block_palette = list(set([block[0] for block in self.color_to_block.values()]))
        print(f"{Color.CYAN}🎨 初始化调色板: {len(self.block_palette)} 种方块{Color.RESET}")
        
        self.block_data = np.zeros((self.depth, self.height, self.width), dtype=int)
        self.block_data_values = np.zeros((self.depth, self.height, self.width), dtype=int)
        
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        print(f"{Color.CYAN}🔄 正在处理像素数据...{Color.RESET}")
        total_pixels = self.width * self.height
        processed_pixels = 0
        
        progress_thread = ProgressDisplay(total_pixels, "处理像素", self.config)
        progress_thread.start()
        
        for y in range(self.height):
            for x in range(self.width):
                src_x = int(x * scale_x)
                src_y = int(y * scale_y)
                
                region = self.pixels[
                    int(src_y):min(int((y+1)*scale_y), self.original_height),
                    int(src_x):min(int((x+1)*scale_x), self.original_width)
                ]
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
                
                processed_pixels += 1
                progress_thread.update(processed_pixels)
        
        progress_thread.stop()
        progress_thread.join()
        
        print(f"{Color.GREEN}✅ 方块数据生成完成{Color.RESET}")

    def convert(self, input_image, output_path, width=None, height=None, selected_blocks=None):
        """转换入口函数"""
        if selected_blocks is None:
            selected_blocks = []
            
        print(f"{Color.CYAN}🚀 开始转换流程...{Color.RESET}")
        
        if not self.load_block_mappings(selected_blocks):
            return None
            
        try:
            self.load_image(input_image)
            
            if width is None or height is None:
                self.set_size(self.original_width, self.original_height)
            else:
                best_width, best_height = self.calculate_best_ratio(width, height)
                
                if best_width != width or best_height != height:
                    print(f"\n{Color.YELLOW}⚠️  建议使用保持比例的最佳尺寸: {best_width}x{best_height} (原图比例 {self.original_width}:{self.original_height}){Color.RESET}")
                    choice = input("是否使用建议尺寸? (y/n): ").strip().lower()
                    if choice == 'y':
                        self.set_size(best_width, best_height)
                    else:
                        self.set_size(width, height)
                else:
                    self.set_size(width, height)
                
            self.generate_block_data()
            return self.save_litematic(output_path)
        except Exception as e:
            print(f"{Color.RED}❌ 转换过程中发生错误: {e}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_litematic(self, output_path):
        """保存为Litematica格式文件"""
        print(f"{Color.CYAN}💾 正在保存litematic文件...{Color.RESET}")
        
        # 修复BUG：确保后缀名是.litematic而不是.litematica
        if output_path.lower().endswith('.litematica'):
            output_path = output_path[:-1]  # 移除多余的 'a'
        elif not output_path.lower().endswith('.litematic'):
            output_path += '.litematic'
        
        # 根据LitematicaToSchem转换器的解析逻辑，创建正确的Litematica格式
        # 这是Litematica v5格式，与LitematicaToSchem转换器兼容
        litematica_data = Compound({
            "Version": Int(5),
            "MinecraftDataVersion": Int(3100),
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
                "region_0": Compound({
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
                    "BlockStatePalette": List[Compound](),
                    "BlockStates": nbtlib.LongArray([]),
                    "TileEntities": List[Compound]([])
                })
            })
        })
        
        # 添加方块状态调色板
        region_data = litematica_data["Regions"]["region_0"]
        palette = region_data["BlockStatePalette"]
        
        for block_name in self.block_palette:
            block_state = Compound({
                "Name": String(block_name)
            })
            palette.append(block_state)
        
        # 生成方块索引数据
        bits_per_entry = max((len(self.block_palette) - 1).bit_length(), 4)
        mask = (1 << bits_per_entry) - 1
        
        print(f"{Color.CYAN}🔢 位每条目: {bits_per_entry}位，调色板大小: {len(self.block_palette)}{Color.RESET}")
        
        # 生成方块状态索引
        block_indices = []
        for y in range(self.height):
            for x in range(self.width):
                block_index = self.block_data[0, y, x]
                block_indices.append(block_index)
        
        # 将索引打包到64位Long数组中
        block_states = []
        buffer = 0
        bits_in_buffer = 0
        
        for index in block_indices:
            buffer |= (index & mask) << bits_in_buffer
            bits_in_buffer += bits_per_entry
            
            while bits_in_buffer >= 64:
                # 取低64位
                long_value = buffer & ((1 << 64) - 1)
                # 转换为有符号64位整数
                if long_value >= (1 << 63):
                    long_value -= (1 << 64)
                block_states.append(Long(long_value))
                
                # 移除已处理的64位
                buffer >>= 64
                bits_in_buffer -= 64
        
        # 处理剩余位
        if bits_in_buffer > 0:
            long_value = buffer & ((1 << 64) - 1)
            if long_value >= (1 << 63):
                long_value -= (1 << 64)
            block_states.append(Long(long_value))
        
        # 设置BlockStates和BitsPerEntry
        region_data["BlockStates"] = nbtlib.LongArray(block_states)
        region_data["BitsPerEntry"] = Int(bits_per_entry)
        
        # 保存NBT文件
        nbt_file = nbtlib.File(litematica_data)
        nbt_file.save(output_path, gzipped=True)
        
        print(f"{Color.GREEN}✅ litematic文件保存完成: {output_path}{Color.RESET}")
        print(f"{Color.CYAN}📊 文件信息: {len(block_states)}个Long, {len(block_indices)}个方块索引{Color.RESET}")
        
        return self.width, self.height, self.width * self.height

# 兼容性别名
Converter = LitematicaConverter