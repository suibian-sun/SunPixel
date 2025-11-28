import numpy as np
import png  # 使用pypng库处理PNG
from PIL import Image  # 使用PIL处理JPG
import nbtlib
from nbtlib.tag import Byte, Short, Int, Long, Float, Double, String, List, Compound
import os
import time
import math
import json
from pathlib import Path
import datetime
import urllib.request
import urllib.error
import re
import sys
import threading

class ImageToSchem:
    def __init__(self):
        self.color_to_block = {}
        self.block_palette = []
        self.block_data = []
        self.width = 0
        self.height = 0
        self.depth = 1
        
    def load_block_mappings(self, selected_blocks):
        """从block目录加载选中的方块映射"""
        self.color_to_block = {}
        block_dir = Path("block")
        
        if not block_dir.exists():
            print("❌ 错误: block目录不存在!")
            return False
            
        for block_file in block_dir.glob("*.json"):
            block_name = block_file.stem
            if block_name in selected_blocks:
                try:
                    with open(block_file, 'r', encoding='utf-8') as f:
                        # 读取文件内容并过滤注释行
                        lines = f.readlines()
                        json_lines = []
                        for line in lines:
                            # 跳过以#开头的注释行
                            if not line.strip().startswith('#'):
                                json_lines.append(line)
                        
                        # 解析JSON
                        if json_lines:  # 确保有JSON内容
                            block_data = json.loads(''.join(json_lines))
                            
                            # 修复：正确处理颜色键的格式
                            processed_block_data = {}
                            for color_key, block_info in block_data.items():
                                # 确保颜色键是字符串格式
                                if isinstance(color_key, str):
                                    processed_block_data[color_key] = block_info
                                else:
                                    # 如果颜色键不是字符串，转换为字符串
                                    processed_block_data[str(color_key)] = block_info
                            
                            self.color_to_block.update(processed_block_data)
                            print(f"✅ 已加载: {block_name}")
                        else:
                            print(f"❌ 文件 {block_file} 中没有有效的JSON内容")
                except Exception as e:
                    print(f"❌ 加载 {block_file} 时出错: {e}")
        
        if not self.color_to_block:
            print("❌ 错误: 没有加载任何方块映射!")
            return False
            
        print(f"✅ 总共加载 {len(self.color_to_block)} 种颜色映射")
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
            # 将字符串格式的颜色转换为元组
            try:
                # 处理 "(r, g, b)" 格式的字符串
                if target_color_str.startswith('(') and target_color_str.endswith(')'):
                    color_str = target_color_str[1:-1]  # 去掉括号
                    color_values = [int(x.strip()) for x in color_str.split(',')]
                    target_color = tuple(color_values[:3])  # 只取RGB三个值
                else:
                    # 如果是其他格式，尝试直接处理
                    color_values = [int(x.strip()) for x in target_color_str.split(',')]
                    target_color = tuple(color_values[:3])
                
                # 使用感知颜色距离算法
                distance = self.color_distance((r, g, b), target_color)
                if distance < min_distance:
                    min_distance = distance
                    closest_color = target_color_str
            except Exception as e:
                # 如果颜色解析失败，跳过这个颜色
                continue
                
        if closest_color:
            block_info = self.color_to_block[closest_color]
            # 确保返回的是 (block_name, block_data) 格式
            if isinstance(block_info, list) and len(block_info) >= 2:
                return block_info[0], block_info[1]
            else:
                # 如果格式不正确，返回默认值
                return "minecraft:white_concrete", 0
        else:
            return "minecraft:white_concrete", 0
    
    def load_image(self, image_path):
        """加载图片，支持PNG和JPG格式"""
        print("🖼️  正在加载图片...")
        # 检查文件扩展名
        ext = os.path.splitext(image_path)[1].lower()
        
        if ext == '.png':
            # 使用pypng处理PNG
            reader = png.Reader(filename=image_path)
            width, height, pixels, metadata = reader.asDirect()
            
            # 将像素数据转换为numpy数组
            image_data = []
            for row in pixels:
                image_data.append(row)
            
            # 根据通道数处理数据
            if metadata['alpha']:
                # RGBA格式，忽略alpha通道
                self.pixels = np.array(image_data, dtype=np.uint8).reshape(height, width, 4)[:, :, :3]
            else:
                # RGB格式
                self.pixels = np.array(image_data, dtype=np.uint8).reshape(height, width, 3)
                
            self.original_width = width
            self.original_height = height
            
        elif ext in ('.jpg', '.jpeg'):
            # 使用PIL处理JPG
            img = Image.open(image_path)
            img = img.convert('RGB')
            self.original_width, self.original_height = img.size
            
            # 将图像转换为numpy数组
            self.pixels = np.array(img)
            
        else:
            raise ValueError(f"不支持的图片格式: {ext}")
        
        print(f"✅ 图片加载完成: {self.original_width} × {self.original_height} 像素")
            
    def calculate_best_ratio(self, target_width, target_height):
        """计算最佳保持比例的尺寸"""
        orig_ratio = self.original_width / self.original_height
        target_ratio = target_width / target_height
        
        # 如果目标比例接近原始比例，直接返回
        if abs(orig_ratio - target_ratio) < 0.05:
            return target_width, target_height
        
        # 计算保持比例的最佳尺寸
        if orig_ratio > target_ratio:
            # 宽度是限制因素
            best_width = target_width
            best_height = int(target_width / orig_ratio)
        else:
            # 高度是限制因素
            best_height = target_height
            best_width = int(target_height * orig_ratio)
            
        return best_width, best_height
    
    def set_size(self, width, height):
        """设置生成结构的尺寸"""
        self.width = max(1, width)
        self.height = max(1, height)
        print(f"📐 设置生成尺寸: {self.width} × {self.height} 方块")
            
    def generate_schem(self):
        """生成schem数据结构"""
        print("🔨 正在生成schem数据结构...")
        
        # 初始化方块调色板
        self.block_palette = list(set([block[0] for block in self.color_to_block.values()]))
        print(f"🎨 初始化调色板: {len(self.block_palette)} 种方块")
        
        # 创建方块数据数组 (二维数组: height × width)
        self.block_data = np.zeros((self.depth, self.height, self.width), dtype=int)
        self.block_data_values = np.zeros((self.depth, self.height, self.width), dtype=int)
        
        # 计算缩放比例
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        print("🔄 正在处理像素数据...")
        total_pixels = self.width * self.height
        processed_pixels = 0
        
        # 创建进度显示线程
        progress_thread = ProgressDisplay(total_pixels, "处理像素")
        progress_thread.start()
        
        # 填充方块数据
        for y in range(self.height):
            for x in range(self.width):
                # 计算原始图片中对应的区域
                src_x = int(x * scale_x)
                src_y = int(y * scale_y)
                
                # 获取该区域的平均颜色
                region = self.pixels[
                    int(src_y):min(int((y+1)*scale_y), self.original_height),
                    int(src_x):min(int((x+1)*scale_x), self.original_width)
                ]
                if region.size == 0:
                    avg_color = (255, 255, 255)  # 默认白色
                else:
                    avg_color = tuple(np.mean(region, axis=(0, 1)).astype(int))
                
                block_name, block_data = self.find_closest_color(avg_color)
                if block_name in self.block_palette:
                    block_index = self.block_palette.index(block_name)
                else:
                    # 如果方块不在调色板中，使用第一个方块
                    block_index = 0
                
                # 单层结构，只在z=0位置放置方块
                self.block_data[0, y, x] = block_index
                self.block_data_values[0, y, x] = block_data
                
                processed_pixels += 1
                progress_thread.update(processed_pixels)
        
        # 停止进度显示
        progress_thread.stop()
        progress_thread.join()
        
        print("✅ schem数据结构生成完成")
        
    def save_schem(self, output_path):
        """保存为Sponge格式的.schem文件"""
        print("💾 正在保存schem文件...")
        
        # 确保输出文件后缀正确
        if not output_path.lower().endswith('.schem'):
            output_path += '.schem'
        
        # 创建NBT数据结构 - 去除元数据
        schematic = Compound({
            "Version": Int(2),
            "DataVersion": Int(3100),  
            "Width": Short(self.width),
            "Height": Short(self.depth),
            "Length": Short(self.height),
            "Offset": List[Int]([Int(0), Int(0), Int(0)]),
            
            # 调色板
            "Palette": Compound({
                block_name: Int(idx) 
                for idx, block_name in enumerate(self.block_palette)
            }),
            
            # 方块数据
            "BlockData": nbtlib.ByteArray(
                self.block_data.flatten(order='C').tolist()
            ),
            
            # 方块实体数据
            "BlockEntities": List[Compound]([])
        })
        
        # 保存为.schem文件
        nbt_file = nbtlib.File(schematic)
        nbt_file.save(output_path, gzipped=True)
        
        print(f"✅ schem文件保存完成: {output_path}")
        # 返回转换统计信息
        return self.width, self.height, self.width * self.height
        
    def convert(self, input_image, output_schem, width=None, height=None, selected_blocks=None):
        """转换入口函数"""
        if selected_blocks is None:
            selected_blocks = []
            
        print("🚀 开始转换流程...")
        # 加载方块映射
        if not self.load_block_mappings(selected_blocks):
            return None
            
        try:
            self.load_image(input_image)
            
            # 如果没有指定尺寸，则使用原始图片尺寸
            if width is None or height is None:
                self.set_size(self.original_width, self.original_height)
            else:
                # 计算并建议最佳比例
                best_width, best_height = self.calculate_best_ratio(width, height)
                
                # 如果建议的尺寸与用户输入不同，询问用户
                if best_width != width or best_height != height:
                    print(f"\n⚠️  建议使用保持比例的最佳尺寸: {best_width}x{best_height} (原图比例 {self.original_width}:{self.original_height})")
                    choice = input("是否使用建议尺寸? (y/n): ").strip().lower()
                    if choice == 'y':
                        self.set_size(best_width, best_height)
                    else:
                        self.set_size(width, height)
                else:
                    self.set_size(width, height)
                
            self.generate_schem()
            return self.save_schem(output_schem)
        except Exception as e:
            print(f"❌ 转换过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return None


class ProgressDisplay(threading.Thread):
    """实时进度显示线程"""
    def __init__(self, total, description="处理"):
        super().__init__()
        self.total = total
        self.description = description
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
        while self.running and self.current < self.total:
            progress = (self.current / self.total) * 100
            bar_length = 30
            filled_length = int(bar_length * self.current // self.total)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            sys.stdout.write(f'\r📊 {self.description}: [{bar}] {self.current}/{self.total} ({progress:.1f}%)')
            sys.stdout.flush()
            time.sleep(0.1)
        
        # 显示最终进度
        if self.current >= self.total:
            progress = 100.0
            bar = '█' * bar_length
            sys.stdout.write(f'\r📊 {self.description}: [{bar}] {self.current}/{self.total} ({progress:.1f}%) ✅\n')
            sys.stdout.flush()


def get_gradient_colors(num_colors):
    """生成渐变颜色序列"""
    # 定义12种渐变颜色（从蓝色到紫色到粉色）
    gradient_colors = [
        '\033[38;5;27m',   # 深蓝
        '\033[38;5;33m',   # 蓝色
        '\033[38;5;39m',   # 亮蓝
        '\033[38;5;45m',   # 青蓝
        '\033[38;5;51m',   # 青色
        '\033[38;5;50m',   # 蓝绿
        '\033[38;5;49m',   # 绿青
        '\033[38;5;48m',   # 青色
        '\033[38;5;129m',  # 紫色
        '\033[38;5;165m',  # 亮紫
        '\033[38;5;201m',  # 粉紫
        '\033[38;5;207m',  # 粉色
        '\033[38;5;213m',  # 亮粉
        '\033[38;5;219m',  # 浅粉
    ]
    
    # 根据需要的颜色数量生成渐变序列
    if num_colors <= len(gradient_colors):
        return gradient_colors[:num_colors]
    
    # 如果需要更多颜色，在现有颜色间插值
    result = []
    for i in range(num_colors):
        pos = i / (num_colors - 1) * (len(gradient_colors) - 1)
        idx = int(pos)
        result.append(gradient_colors[idx])
    
    return result


def display_logo():
    """显示渐变颜色程序logo"""
    # 定义logo的每一行
    logo_lines = [
        "╔═════════════════════════════════════════════╗",
        "║  ███████╗██╗   ██╗███╗   ██║                ║",
        "║  ██╔════╝██║   ██║████╗  ██║                ║",
        "║  ███████╗██║   ██║██╔██╗ ██║                ║",
        "║  ╚════██║██║   ██║██║╚██╗██║                ║",
        "║  ███████║╚██████╔╝██║ ╚████║                ║",
        "║  ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝                ║",
        "║           ██████╗ ██╗██╗  ██╗███████╗██     ║",
        "║           ██╔══██╗██║╚██╗██╔╝██╔════╝██     ║",
        "║           ██████╔╝██║ ╚███╔╝ █████╗  ██     ║",
        "║           ██╔═══╝ ██║ ██╔██╗ ██╔══╝  ██     ║",
        "║           ██║     ██║██╔╝ ██╗███████╗██╗    ║",
        "║           ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝╚═╝    ║",
        "╚═════════════════════════════════════════════╝"
    ]
    
    # 生成渐变颜色
    gradient = get_gradient_colors(len(logo_lines))
    reset_color = '\033[0m'
    
    # 打印渐变logo
    print()
    for i, line in enumerate(logo_lines):
        print(f"{gradient[i]}{line}{reset_color}")
    
    # 打印开源信息（使用渐变颜色）
    info_lines = [
        "┌───────────────────────────────────────────┐",
        "│         Open source - SunPixel            │",
        "│ https://github.com/suibian-sun/SunPixel   │",
        "└───────────────────────────────────────────┘",
        "Authors: suibian-sun"
    ]
    
    info_gradient = get_gradient_colors(len(info_lines))
    print()
    for i, line in enumerate(info_lines):
        print(f"{info_gradient[i]}{line}{reset_color}")
    print()


def extract_date_from_content(content):
    date_pattern = r'\b(\d{4}-\d{1,2}-\d{1,2})\b'
    matches = re.findall(date_pattern, content)
    
    if matches:
        return matches[0]
        
    return datetime.datetime.now().strftime("%Y-%m-%d")


def get_latest_announcement():
    announcement_url = "https://raw.githubusercontent.com/suibian-sun/SunPixel/refs/heads/main/app/Changelog/new.md"
    
    try:
        with urllib.request.urlopen(announcement_url, timeout=10) as response:
            content = response.read().decode('utf-8').strip()
        
        # 从内容中提取日期
        date_str = extract_date_from_content(content)
        return date_str, content
        
    except urllib.error.URLError as e:
        print(f"⚠️  无法获取最新公告: {e}")
        return None
    except Exception as e:
        print(f"⚠️  获取公告时出错: {e}")
        return None


def format_announcement_content(content):
    """格式化公告内容，在标题和内容之间添加空行"""
    lines = content.split('\n')
    formatted_lines = []
    
    for i, line in enumerate(lines):
        formatted_lines.append(line)
        if "更新内容如下" in line and i + 1 < len(lines) and lines[i + 1].strip():
            formatted_lines.append("")
    
    return '\n'.join(formatted_lines)


def format_announcement_box(date_str, content):
    """格式化公告显示框，自动调整边框宽度"""
    formatted_content = format_announcement_content(content)
    lines = formatted_content.split('\n')
    max_line_length = max(len(line) for line in lines if line.strip())
    
    # 计算边框宽度（最长行长度 + 4个字符的边距）
    box_width = max(60, max_line_length + 4)  # 最小宽度为60
    
    # 构建边框
    top_border = "╔" + "═" * (box_width - 2) + "╗"
    middle_border = "╠" + "═" * (box_width - 2) + "╣"
    bottom_border = "╚" + "═" * (box_width - 2) + "╝"
    
    # 构建格式化内容
    formatted_lines = []
    
    # 添加标题行
    title_line = f"║ 📅 发布日期: {date_str}"
    formatted_lines.append(title_line.ljust(box_width - 1) + "║")
    
    # 添加中间边框
    formatted_lines.append(middle_border)
    
    # 添加内容行
    for line in lines:
        if line.strip():  # 只显示非空行
            # 处理长文本换行
            while len(line) > box_width - 4:
                segment = line[:box_width - 4]
                formatted_line = f"║ {segment}"
                formatted_lines.append(formatted_line.ljust(box_width - 1) + "║")
                line = line[box_width - 4:]
            
            if line.strip():  # 确保行不为空
                formatted_line = f"║ {line}"
                formatted_lines.append(formatted_line.ljust(box_width - 1) + "║")
        else:
            # 空行也保留，用于间距
            formatted_lines.append(f"║{' ' * (box_width - 2)}║")
    
    # 组合所有部分
    formatted_content = [top_border] + formatted_lines + [bottom_border]
    
    return formatted_content


def display_announcement():
    """显示最新公告"""
    announcement = get_latest_announcement()
    
    if announcement:
        date_str, content = announcement
        formatted_announcement = format_announcement_box(date_str, content)
        
        print("\n📢 最新公告")
        for line in formatted_announcement:
            print(line)
    else:
        print("\n📢 暂无公告或无法获取公告")


def get_block_display_name(block_file):
    """从JSON文件的第一行注释中获取方块类型的中文名称"""
    try:
        with open(block_file, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if first_line.startswith('# '):
                return first_line[2:] 
    except:
        pass
    return block_file.stem 


def get_available_blocks():
    """获取可用的方块类型及其显示名称"""
    block_dir = Path("block")
    if not block_dir.exists():
        block_dir.mkdir(exist_ok=True)
        create_default_block_files()
        
    blocks_info = {}
    for block_file in block_dir.glob("*.json"):
        display_name = get_block_display_name(block_file)
        blocks_info[block_file.stem] = display_name
    
    return blocks_info


def select_blocks():
    """让用户选择要使用的方块类型"""
    blocks_info = get_available_blocks()
    available_blocks = list(blocks_info.keys())
    
    if not available_blocks:
        print("❌ 没有找到任何方块映射文件!")
        return []
        
    print("\n📦 可用的方块类型:")
    print("-" * 50)
    
    for i, block in enumerate(available_blocks, 1):
        chinese_name = blocks_info[block]
        print(f"  {i}. {block} ({chinese_name})")
    
    print(f"  {len(available_blocks) + 1}. 全选")
    print(f"  {len(available_blocks) + 2}. 取消全选")
    print("-" * 50)
    
    selected = set()
    
    while True:
        choice = input("\n请选择要使用的方块类型(输入编号，多个用逗号分隔，回车确认): ").strip()
        
        if not choice:
            if not selected:
                print("⚠️  未选择任何方块，将使用默认方块")
                return ["wool", "concrete"]  # 默认选择羊毛和混凝土
            break
            
        try:
            choices = [c.strip() for c in choice.split(',')]
            for c in choices:
                if c.isdigit():
                    idx = int(c)
                    if 1 <= idx <= len(available_blocks):
                        selected.add(available_blocks[idx-1])
                    elif idx == len(available_blocks) + 1:
                        # 全选
                        selected = set(available_blocks)
                        print("✅ 已选择所有方块类型")
                        break
                    elif idx == len(available_blocks) + 2:
                        # 取消全选
                        selected.clear()
                        print("✅ 已取消所有选择")
                        break
                    else:
                        print(f"❌ 无效的选择: {c}")
                else:
                    if c in available_blocks:
                        selected.add(c)
                    else:
                        print(f"❌ 无效的方块类型: {c}")
            
            if selected:
                # 显示选中的方块的中文名称
                selected_names = []
                for block in sorted(selected):
                    chinese_name = blocks_info[block]
                    selected_names.append(f"{block}({chinese_name})")
                print(f"✅ 已选择: {', '.join(selected_names)}")
                break
                
        except ValueError:
            print("❌ 请输入有效的数字")
    
    return list(selected)


def get_user_input():
    """获取用户输入"""
    print("\n" + "="*50)
    
    # 获取输入文件路径
    while True:
        input_path = input("\n📁 请输入图片路径 (PNG或JPG): ").strip()
        if not input_path:
            print("❌ 路径不能为空")
            continue
            
        if not os.path.exists(input_path):
            print(f"❌ 错误: 文件 '{input_path}' 不存在")
            continue
            
        ext = os.path.splitext(input_path)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg'):
            print("❌ 错误: 只支持PNG和JPG格式的图片")
            continue
            
        try:
            if ext == '.png':
                with open(input_path, 'rb') as f:
                    reader = png.Reader(file=f)
                    width, height, _, _ = reader.read()
            else:
                img = Image.open(input_path)
                width, height = img.size
                
            if width == 0 or height == 0:
                print("❌ 错误: 图片尺寸无效")
                continue
            break
        except Exception as e:
            print(f"❌ 无法打开文件: {e}，请重新输入")
    
    # 选择方块类型
    selected_blocks = select_blocks()
    
    # 设置输出目录和文件名
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    default_name = Path(input_path).stem + ".schem"
    output_path = input(f"\n💾 输出文件名 (回车使用 '{default_name}'): ").strip()
    
    if not output_path:
        output_path = default_name
    elif not output_path.lower().endswith('.schem'):
        output_path += '.schem'
    
    output_file = output_dir / output_path
    
    # 获取生成尺寸
    while True:
        size_input = input("\n📐 请输入生成尺寸(格式: 宽x高，例如 64x64，留空则使用原图尺寸): ").strip()
        if not size_input:
            width, height = None, None
            break
        
        try:
            if 'x' in size_input:
                width, height = map(int, size_input.lower().split('x'))
            elif '×' in size_input:
                width, height = map(int, size_input.lower().split('×'))
            else:
                print("❌ 请输入有效的尺寸格式，例如 64x64")
                continue
                
            if width <= 0 or height <= 0:
                print("❌ 尺寸必须大于0")
                continue
            break
        except ValueError:
            print("❌ 请输入有效的尺寸格式，例如 64x64")
    
    return input_path, str(output_file), width, height, selected_blocks


def verify_schem_file(file_path):
    """验证schem文件内容并修复可能的错误"""
    print("\n🔍 正在验证生成的schem文件...")
    
    try:
        # 加载schem文件
        nbt_file = nbtlib.load(file_path, gzipped=True)
        
        # 检查必要的字段
        required_fields = ["Version", "DataVersion", "Width", "Height", "Length", "Palette", "BlockData"]
        missing_fields = [field for field in required_fields if field not in nbt_file]
        
        if missing_fields:
            print(f"❌ 文件缺少必要字段: {', '.join(missing_fields)}")
            return False, "文件结构不完整"
        
        # 验证尺寸数据
        width = nbt_file["Width"]
        height = nbt_file["Height"]
        length = nbt_file["Length"]
        
        if width <= 0 or height <= 0 or length <= 0:
            print("❌ 文件尺寸数据无效")
            return False, "尺寸数据无效"
        
        # 验证调色板
        palette = nbt_file["Palette"]
        if not palette:
            print("❌ 调色板为空")
            return False, "调色板为空"
        
        # 验证方块数据
        block_data = nbt_file["BlockData"]
        expected_size = width * height * length
        
        if len(block_data) != expected_size:
            print(f"❌ 方块数据长度不匹配: 期望 {expected_size}, 实际 {len(block_data)}")
            return False, "方块数据长度不匹配"
        
        # 检查方块数据中的值是否在调色板范围内
        palette_size = len(palette)
        out_of_range_blocks = [block_id for block_id in block_data if block_id >= palette_size]
        
        if out_of_range_blocks:
            print(f"❌ 发现 {len(out_of_range_blocks)} 个超出调色板范围的方块ID")
            return False, "方块ID超出调色板范围"
        
        print("✅ schem文件验证通过")
        return True, "文件验证通过"
        
    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        return False, f"验证错误: {str(e)}"


def fix_schem_file(file_path, issue):
    """根据问题修复schem文件"""
    print(f"\n🔧 正在尝试修复schem文件: {issue}")
    
    try:
        # 加载原始文件
        nbt_file = nbtlib.load(file_path, gzipped=True)
        
        fix_description = ""
        
        # 根据具体问题应用修复
        if "方块数据长度不匹配" in issue:
            # 重新生成正确的方块数据
            width = nbt_file["Width"]
            height = nbt_file["Height"]
            length = nbt_file["Length"]
            expected_size = width * height * length
            
            # 创建新的方块数据（全部设为0）
            new_block_data = nbtlib.ByteArray([0] * expected_size)
            nbt_file["BlockData"] = new_block_data
            
            fix_description = f"重置方块数据为默认值，长度: {expected_size}"
            
        elif "方块ID超出调色板范围" in issue:
            # 将超出范围的方块ID设为0
            palette_size = len(nbt_file["Palette"])
            block_data = nbt_file["BlockData"]
            
            fixed_blocks = 0
            for i in range(len(block_data)):
                if block_data[i] >= palette_size:
                    block_data[i] = 0
                    fixed_blocks += 1
            
            fix_description = f"修复了 {fixed_blocks} 个超出调色板范围的方块ID"
            
        else:
            # 通用修复：确保所有必要字段都存在
            if "Version" not in nbt_file:
                nbt_file["Version"] = Int(2)
            if "DataVersion" not in nbt_file:
                nbt_file["DataVersion"] = Int(3100)
            
            fix_description = "添加了缺失的必要字段"
        
        # 保存修复后的文件
        backup_path = file_path.replace('.schem', '_backup.schem')
        os.rename(file_path, backup_path)
        nbt_file.save(file_path, gzipped=True)
        
        print(f"✅ 文件修复完成: {fix_description}")
        print(f"📁 原始文件已备份为: {backup_path}")
        
        return True, fix_description, backup_path
        
    except Exception as e:
        print(f"❌ 修复过程中发生错误: {e}")
        return False, f"修复失败: {str(e)}", None


def ask_auto_verification():
    while True:
        choice = input("\n是否启用自动验证? (y/n, 回车默认为y): ").strip().lower()
        
        if not choice or choice == 'y' or choice == 'yes':
            print("✅ 已启用自动验证")
            return True
        elif choice == 'n' or choice == 'no':
            print("⚠️  已禁用自动验证")
            return False
        else:
            print("❌ 请输入 y 或 N")

def create_default_block_files():
    """创建默认的方块映射文件"""
    block_dir = Path("block")
    block_dir.mkdir(exist_ok=True)
    
    # 羊毛方块
    wool_data = {
        "(255, 255, 255)": ["minecraft:white_wool", 0],
        "(255, 165, 0)": ["minecraft:orange_wool", 0],
        "(255, 69, 0)": ["minecraft:red_wool", 0],
        "(255, 192, 203)": ["minecraft:pink_wool", 0],
        "(128, 0, 128)": ["minecraft:purple_wool", 0],
        "(0, 0, 255)": ["minecraft:blue_wool", 0],
        "(0, 128, 0)": ["minecraft:green_wool", 0],
        "(255, 255, 0)": ["minecraft:yellow_wool", 0],
        "(165, 42, 42)": ["minecraft:brown_wool", 0],
        "(128, 128, 128)": ["minecraft:gray_wool", 0],
        "(0, 0, 0)": ["minecraft:black_wool", 0]
    }
    
    with open(block_dir / "wool.json", 'w', encoding='utf-8') as f:
        f.write("# 羊毛方块\n")
        json.dump(wool_data, f, indent=2, ensure_ascii=False)
    
    # 混凝土方块
    concrete_data = {
        "(255, 255, 255)": ["minecraft:white_concrete", 0],
        "(255, 165, 0)": ["minecraft:orange_concrete", 0],
        "(255, 69, 0)": ["minecraft:red_concrete", 0],
        "(255, 192, 203)": ["minecraft:pink_concrete", 0],
        "(128, 0, 128)": ["minecraft:purple_concrete", 0],
        "(0, 0, 255)": ["minecraft:blue_concrete", 0],
        "(0, 128, 0)": ["minecraft:green_concrete", 0],
        "(255, 255, 0)": ["minecraft:yellow_concrete", 0],
        "(165, 42, 42)": ["minecraft:brown_concrete", 0],
        "(128, 128, 128)": ["minecraft:gray_concrete", 0],
        "(0, 0, 0)": ["minecraft:black_concrete", 0]
    }
    
    with open(block_dir / "concrete.json", 'w', encoding='utf-8') as f:
        f.write("# 混凝土方块\n")
        json.dump(concrete_data, f, indent=2, ensure_ascii=False)
    
    print("✅ 已创建默认方块映射文件")

# 主程序
if __name__ == "__main__":
    try:
        # 显示彩色logo
        display_logo()
        
        # 显示最新公告
        display_announcement()
        
        # 询问是否启用自动验证
        enable_verification = ask_auto_verification()
        
        # 获取用户输入
        input_image, output_schem, width, height, selected_blocks = get_user_input()
        
        # 创建转换器并执行转换
        converter = ImageToSchem()
        print("\n🔄 开始转换...")
        start_time = time.time()
        
        # 执行转换并获取统计信息
        result = converter.convert(input_image, output_schem, width, height, selected_blocks)
        
        # 修改这里：检查返回值类型
        if result is not None:
            # 如果转换成功，result应该是一个包含三个值的元组
            schem_width, schem_height, block_count = result
            elapsed = time.time() - start_time
            
            # 显示转换统计信息
            print(f"\n✅ 转换成功完成! 耗时: {elapsed:.2f}秒")
            print("="*50)
            print(f"📐 生成结构尺寸: {schem_width} × {schem_height} 方块")
            print(f"🧱 总方块数量: {block_count} 个")
            print(f"💾 输出文件: {os.path.abspath(output_schem)}")
            
            # 显示使用的方块类型中文名
            blocks_info = get_available_blocks()
            selected_names = []
            for block in selected_blocks:
                chinese_name = blocks_info.get(block, block)
                selected_names.append(f"{block}({chinese_name})")
            print(f"🎨 使用的方块类型: {', '.join(selected_names)}")
            print("="*50)
            
            # 如果启用了自动验证，进行文件验证和修复
            if enable_verification:
                # 验证文件
                is_valid, message = verify_schem_file(output_schem)
                
                if not is_valid:
                    print(f"\n⚠️  文件验证发现问题: {message}")
                    
                    # 询问用户是否要修复
                    fix_choice = input("是否尝试自动修复? (y/n, 回车默认为y): ").strip().lower()
                    if not fix_choice or fix_choice == 'y' or fix_choice == 'yes':
                        fix_start_time = time.time()
                        fix_success, fix_message, backup_path = fix_schem_file(output_schem, message)
                        
                        if fix_success:
                            fix_elapsed = time.time() - fix_start_time
                            print(f"\n✅ 自动验证并修复成功完成! 耗时: {fix_elapsed:.2f}秒")
                            print("="*50)
                            print(f"📐 生成结构尺寸: {schem_width} × {schem_height} 方块")
                            print(f"🧱 总方块数量: {block_count} 个")
                            print(f"💾 原输出文件: {backup_path}")
                            print(f"💾 修复后文件: {os.path.abspath(output_schem)}")
                            print(f"🔧 修复内容: {fix_message}")
                            
                            # 显示使用的方块类型中文名
                            print(f"🎨 使用的方块类型: {', '.join(selected_names)}")
                            print("="*50)
                            
                            # 验证修复后的文件
                            print("\n🔍 验证修复后的文件...")
                            is_valid_after_fix, final_message = verify_schem_file(output_schem)
                            
                            if is_valid_after_fix:
                                print("✅ 修复后文件验证通过")
                            else:
                                print(f"❌ 修复后文件仍然存在问题: {final_message}")
                        else:
                            print(f"❌ 修复失败: {fix_message}")
                    else:
                        print("⚠️  用户选择不进行修复")
                else:
                    print("✅ 文件验证通过，无需修复")
            
        else:
            print("\n❌ 转换失败!")
            
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n按Enter键退出...")