from flask import Flask, request, jsonify, render_template, send_file, Response, redirect, url_for
import numpy as np
import png
from PIL import Image
import nbtlib
from nbtlib.tag import Byte, Short, Int, Long, Float, Double, String, List, Compound
import os
import math
import json
from pathlib import Path
import tempfile
import io
import base64
import logging
from datetime import datetime
import threading
import time
import uuid
import shutil
import mimetypes
from werkzeug.utils import safe_join
import subprocess
import sys
import requests
from urllib.parse import urlparse

app = Flask(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 存储转换结果
conversion_results = {}

# 临时文件存储目录
TEMP_DIR = Path("temp_downloads")
TEMP_DIR.mkdir(exist_ok=True)

# 加载配置文件
def load_config():
    config_path = Path("config.json")
    default_config = {
        "version": "V-1.3.1",
        "language": "zh_CN",
        "output_directory": "./output",
        "default_format": "schem",
        "max_image_size": 512,
        "web_server": {
            "host": "0.0.0.0",
            "port": 5000,
            "debug": False
        }
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}")
    
    return default_config

CONFIG = load_config()

class ConversionProgress:
    """转换进度管理类"""
    def __init__(self, task_id):
        self.task_id = task_id
        self.progress = 0
        self.message = ""
        self.is_running = False
        self.current_stage = ""
        self.logs = []
        self.filename = ""
        self.create_time = time.time()
        self.file_path = None
        self.download_count = 0
        self.format_type = ""
        self.selected_blocks = []
        self.dimensions = (0, 0)
        
    def update(self, progress, message, stage=""):
        self.progress = progress
        self.message = message
        if stage:
            self.current_stage = stage
            
    def log(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        
    def set_result(self, file_path, filename, format_type="", selected_blocks=None, dimensions=None):
        """设置转换结果"""
        self.file_path = file_path
        self.filename = filename
        self.format_type = format_type
        self.selected_blocks = selected_blocks or []
        self.dimensions = dimensions or (0, 0)
        
    def reset(self):
        self.progress = 0
        self.message = ""
        self.is_running = False
        self.current_stage = ""
        self.logs = []
        self.file_path = None
        self.filename = ""
        self.download_count = 0
        self.format_type = ""
        self.selected_blocks = []
        self.dimensions = (0, 0)


# 存储历史记录
history_records = []

# 存储市场项目
market_items = []

def add_to_history(task_id, original_filename, username="匿名用户"):
    """将转换记录添加到历史记录"""
    if task_id not in conversion_results:
        return False
    
    progress = conversion_results[task_id]
    
    if not progress.file_path or not Path(progress.file_path).exists():
        return False
    
    history_item = {
        'id': task_id,
        'original_filename': original_filename,
        'filename': progress.filename,
        'file_path': str(progress.file_path),
        'format_type': progress.format_type,
        'selected_blocks': progress.selected_blocks,
        'dimensions': progress.dimensions,
        'create_time': datetime.fromtimestamp(progress.create_time).strftime('%Y-%m-%d %H:%M:%S'),
        'username': username,
        'download_count': progress.download_count
    }
    
    history_records.append(history_item)
    return True

class WebImageToStructure:
    def __init__(self, progress_manager, config):
        self.color_to_block = {}
        self.block_palette = []
        self.block_data = []
        self.width = 0
        self.height = 0
        self.depth = 1
        self.progress = progress_manager
        self.config = config
        self.output_dir = Path(config.get("output_directory", "./output"))
        
    def log(self, message):
        """添加日志消息"""
        self.progress.log(message)
        
    def update_progress(self, progress_value, message, stage=""):
        """更新进度"""
        self.progress.update(progress_value, message, stage)
        self.log(message)
        
    def load_block_mappings(self, selected_blocks):
        """从block目录加载选中的方块映射"""
        self.update_progress(10, "🔄 正在加载方块映射...", "加载方块映射")
        self.color_to_block = {}
        block_dir = Path("block")
        
        if not block_dir.exists():
            self.log("❌ 错误: block目录不存在!")
            return False
            
        block_files = list(block_dir.glob("*.json"))
        total_files = len(block_files)
        loaded_files = 0
        
        for block_file in block_files:
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
                            self.log(f"✅ 已加载: {block_name}")
                        else:
                            self.log(f"❌ 文件 {block_file} 中没有有效的JSON内容")
                except Exception as e:
                    self.log(f"❌ 加载 {block_file} 时出错: {e}")
            
            loaded_files += 1
            progress_value = 10 + (loaded_files / total_files) * 20
            self.update_progress(progress_value, f"📦 加载方块映射... ({loaded_files}/{total_files})")
        
        if not self.color_to_block:
            self.log("❌ 错误: 没有加载任何方块映射!")
            return False
            
        self.log(f"✅ 总共加载 {len(self.color_to_block)} 种颜色映射")
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
    
    def load_image_from_bytes(self, image_bytes, ext):
        """从字节数据加载图片"""
        self.update_progress(35, "🖼️ 正在加载图片...", "加载图片")
        if ext.lower() == '.png':
            reader = png.Reader(bytes=image_bytes)
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
            
        elif ext.lower() in ('.jpg', '.jpeg'):
            img = Image.open(io.BytesIO(image_bytes))
            img = img.convert('RGB')
            self.original_width, self.original_height = img.size
            self.pixels = np.array(img)
            
        else:
            raise ValueError(f"不支持的图片格式: {ext}")
        
        self.log(f"✅ 图片加载完成: {self.original_width} × {self.original_height} 像素")
        self.update_progress(40, f"✅ 图片加载完成: {self.original_width} × {self.original_height} 像素")
            
    def set_size(self, width, height):
        """设置生成结构的尺寸"""
        self.width = max(1, width)
        self.height = max(1, height)
        self.log(f"📐 设置生成尺寸: {self.width} × {self.height} 方块")
            
    def generate_structure(self, format_type):
        """生成结构数据"""
        self.update_progress(45, f"🔨 正在生成{format_type.upper()}结构数据...", "生成结构")
        
        self.block_palette = list(set([block[0] for block in self.color_to_block.values()]))
        self.log(f"🎨 初始化调色板: {len(self.block_palette)} 种方块")
        self.update_progress(50, f"🎨 初始化调色板: {len(self.block_palette)} 种方块")
        
        self.block_data = np.zeros((self.depth, self.height, self.width), dtype=int)
        self.block_data_values = np.zeros((self.depth, self.height, self.width), dtype=int)
        
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        self.update_progress(55, "🔄 正在处理像素数据...", "处理像素")
        total_pixels = self.width * self.height
        processed_pixels = 0
        
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
                if processed_pixels % 100 == 0 or processed_pixels == total_pixels:
                    progress_percent = 55 + (processed_pixels / total_pixels) * 35
                    progress_pct = processed_pixels/total_pixels*100
                    self.update_progress(
                        progress_percent, 
                        f"📊 处理像素: {processed_pixels}/{total_pixels} ({progress_pct:.1f}%)"
                    )
        
        self.log(f"✅ {format_type.upper()}数据结构生成完成")
        self.update_progress(90, f"✅ {format_type.upper()}数据结构生成完成")
        
    def save_to_file(self, format_type, filename_base):
        """保存结构文件"""
        self.update_progress(90, f"💾 正在保存{format_type.upper()}文件...", "保存文件")
        
        if format_type == 'schem':
            return self._save_schem_file(filename_base)
        elif format_type == 'json':
            return self._save_json_file(filename_base)
        elif format_type == 'litematic':
            return self._save_litematic_file(filename_base)
        else:
            raise ValueError(f"不支持的格式: {format_type}")
            
    def _save_schem_file(self, filename_base):
        """保存schem文件"""
        schematic = Compound({
            "Version": Int(2),
            "DataVersion": Int(3100),  
            "Width": Short(self.width),
            "Height": Short(self.depth),
            "Length": Short(self.height),
            "Offset": List[Int]([Int(0), Int(0), Int(0)]),
            "Palette": Compound({
                block_name: Int(idx) 
                for idx, block_name in enumerate(self.block_palette)
            }),
            "BlockData": nbtlib.ByteArray(
                self.block_data.flatten(order='C').tolist()
            ),
            "BlockEntities": List[Compound]([])
        })
        
        filename = f"{filename_base}.schem"
        filepath = TEMP_DIR / filename
        
        nbt_file = nbtlib.File(schematic)
        nbt_file.save(str(filepath), gzipped=True)
        
        self.log("✅ schem文件保存完成")
        self.update_progress(95, "✅ schem文件保存完成")
        return filepath, filename
        
    def _save_json_file(self, filename_base):
        """保存JSON文件（RunAway格式）"""
        json_data = {
            "name": filename_base,
            "author": "SunPixel",
            "version": "1.0",
            "size": {
                "width": int(self.width),
                "height": int(self.depth),
                "length": int(self.height)
            },
            "blocks": []
        }
        
        for y in range(self.height):
            for x in range(self.width):
                block_index = int(self.block_data[0, y, x])
                if block_index < len(self.block_palette):
                    block_name = self.block_palette[block_index]
                    block_data = int(self.block_data_values[0, y, x])
                    
                    json_data["blocks"].append({
                        "x": int(x),
                        "y": 0,
                        "z": int(y),
                        "block": block_name,
                        "data": block_data
                    })
        
        filename = f"{filename_base}.json"
        filepath = TEMP_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        self.log("✅ JSON文件保存完成")
        self.update_progress(95, "✅ JSON文件保存完成")
        return filepath, filename
        
    def _save_litematic_file(self, filename_base):
        """保存litematic文件"""
        litematic_data = {
            "Version": 5,
            "Metadata": {
                "EnclosingSize": {
                    "x": int(self.width),
                    "y": int(self.depth),
                    "z": int(self.height)
                },
                "Name": filename_base,
                "Author": "SunPixel",
                "Description": f"Generated by SunPixel from image",
                "RegionCount": 1
            },
            "Regions": {
                "structure": {
                    "Position": {"x": 0, "y": 0, "z": 0},
                    "Size": {"x": int(self.width), "y": int(self.depth), "z": int(self.height)},
                    "BlockStatePalette": [
                        {"Name": block_name, "Properties": {}} 
                        for block_name in self.block_palette
                    ],
                    "BlockStates": self.block_data.flatten(order='C').astype(int).tolist()
                }
            }
        }
        
        filename = f"{filename_base}.litematic"
        filepath = TEMP_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(litematic_data, f, indent=2, ensure_ascii=False)
        
        self.log("✅ litematic文件保存完成")
        self.update_progress(95, "✅ litematic文件保存完成")
        return filepath, filename
        
    def convert(self, image_bytes, ext, width, height, selected_blocks, format_type, filename_base):
        """转换入口函数"""
        self.progress.reset()
        self.progress.is_running = True
        
        self.log(f"🚀 开始转换流程 (格式: {format_type.upper()})...")
        self.update_progress(5, f"🚀 开始转换流程 (格式: {format_type.upper()})...", "初始化")
        
        if not self.load_block_mappings(selected_blocks):
            self.progress.is_running = False
            return False
            
        try:
            self.load_image_from_bytes(image_bytes, ext)
            
            if width is None or height is None:
                self.set_size(self.original_width, self.original_height)
            else:
                self.set_size(width, height)
                
            self.generate_structure(format_type)
            filepath, filename = self.save_to_file(format_type, filename_base)
            
            self.log(f"✅ 转换成功完成!")
            self.log(f"📐 生成结构尺寸: {self.width} × {self.height} 方块")
            self.log(f"🧱 总方块数量: {self.width * self.height} 个")
            self.log(f"🎨 使用的方块类型: {', '.join(selected_blocks)}")
            self.log(f"📁 输出文件: {filename}")
            
            self.update_progress(100, "🎉 转换成功完成!", "完成")
            
            self.progress.set_result(filepath, filename)
            
            time.sleep(0.5)
            self.progress.is_running = False
            
            return True
        except Exception as e:
            error_msg = f"❌ 转换过程中发生错误: {e}"
            self.log(error_msg)
            import traceback
            self.log(f"📋 错误详情: {traceback.format_exc()}")
            self.update_progress(0, error_msg, "错误")
            self.progress.is_running = False
            return False


def get_available_blocks():
    """获取可用的方块类型"""
    block_dir = Path("block")
    if not block_dir.exists():
        block_dir.mkdir(exist_ok=True)
        create_default_block_files()
    
    blocks = []
    for block_file in block_dir.glob("*.json"):
        blocks.append(block_file.stem)
    
    return blocks

def create_default_block_files():
    """创建默认的方块映射文件"""
    block_dir = Path("block")
    block_dir.mkdir(exist_ok=True)
    
    wool_colors = {
        "white": ("minecraft:white_wool", 0),
        "orange": ("minecraft:orange_wool", 1),
        "magenta": ("minecraft:magenta_wool", 2),
        "light_blue": ("minecraft:light_blue_wool", 3),
        "yellow": ("minecraft:yellow_wool", 4),
        "lime": ("minecraft:lime_wool", 5),
        "pink": ("minecraft:pink_wool", 6),
        "gray": ("minecraft:gray_wool", 7),
        "light_gray": ("minecraft:light_gray_wool", 8),
        "cyan": ("minecraft:cyan_wool", 9),
        "purple": ("minecraft:purple_wool", 10),
        "blue": ("minecraft:blue_wool", 11),
        "brown": ("minecraft:brown_wool", 12),
        "green": ("minecraft:green_wool", 13),
        "red": ("minecraft:red_wool", 14),
        "black": ("minecraft:black_wool", 15)
    }
    
    rgb_map = {
        "white": (255, 255, 255),
        "orange": (255, 165, 0),
        "magenta": (255, 0, 255),
        "light_blue": (173, 216, 230),
        "yellow": (255, 255, 0),
        "lime": (0, 255, 0),
        "pink": (255, 192, 203),
        "gray": (128, 128, 128),
        "light_gray": (211, 211, 211),
        "cyan": (0, 255, 255),
        "purple": (128, 0, 128),
        "blue": (0, 0, 255),
        "brown": (139, 69, 19),
        "green": (0, 128, 0),
        "red": (255, 0, 0),
        "black": (0, 0, 0)
    }
    
    wool_mapping = {}
    for color_name, (block, data) in wool_colors.items():
        if color_name in rgb_map:
            rgb = rgb_map[color_name]
            wool_mapping[f"{rgb[0]},{rgb[1]},{rgb[2]}"] = [block, data]
    
    with open(block_dir / "wool.json", 'w', encoding='utf-8') as f:
        json.dump(wool_mapping, f, indent=2, ensure_ascii=False)
    
    concrete_mapping = {}
    for color_name, (block_base, data) in wool_colors.items():
        block_name = block_base.replace("_wool", "_concrete")
        if color_name in rgb_map:
            rgb = rgb_map[color_name]
            concrete_mapping[f"{rgb[0]},{rgb[1]},{rgb[2]}"] = [block_name, data]
    
    with open(block_dir / "concrete.json", 'w', encoding='utf-8') as f:
        json.dump(concrete_mapping, f, indent=2, ensure_ascii=False)

def convert_image_thread(task_id, image_bytes, ext, width, height, selected_blocks, format_type, filename, username="匿名用户"):
    """在单独线程中执行图片转换"""
    progress_manager = conversion_results[task_id]
    converter = WebImageToStructure(progress_manager, CONFIG)
    success = converter.convert(image_bytes, ext, width, height, selected_blocks, format_type, filename)
    
    if success:
        progress_manager.set_result(
            progress_manager.file_path, 
            progress_manager.filename,
            format_type=format_type,
            selected_blocks=selected_blocks,
            dimensions=(width, height)
        )
        add_to_history(task_id, filename, username)
    else:
        progress_manager.log("❌ 转换失败")


# ============ 新增：特殊API快速转换功能 ============

def download_image_from_url(url):
    """从URL下载图片"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 从URL或Content-Type确定文件扩展名
        content_type = response.headers.get('content-type', '')
        parsed_url = urlparse(url)
        path_ext = os.path.splitext(parsed_url.path)[1].lower()
        
        if path_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            ext = path_ext
        elif 'png' in content_type:
            ext = '.png'
        elif 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        else:
            ext = '.png'  # 默认扩展名
        
        return response.content, ext
    except Exception as e:
        logger.error(f"下载图片失败: {e}")
        raise Exception(f"无法从URL下载图片: {str(e)}")

def parse_blocks_param(blocks_str):
    """解析方块参数"""
    if not blocks_str:
        return ['wool', 'concrete']
    
    # 支持逗号分隔的格式
    blocks = blocks_str.split(',')
    available_blocks = get_available_blocks()
    
    # 只保留可用的方块类型
    valid_blocks = []
    for block in blocks:
        block = block.strip()
        if block in available_blocks:
            valid_blocks.append(block)
    
    # 如果没有有效的方块类型，返回默认
    if not valid_blocks:
        valid_blocks = ['wool', 'concrete']
    
    return valid_blocks

@app.route('/api/quick-convert')
def quick_convert():
    """
    快速转换API - 通过URL参数直接转换图片
    参数:
        url: 图片URL (必需)
        width: 宽度 (可选，默认自动)
        height: 高度 (可选，默认自动)
        blocks: 方块类型，逗号分隔 (可选，默认 wool,concrete)
        format: 输出格式 (可选，默认 schem)
        username: 用户名 (可选，默认 匿名用户)
        redirect: 是否重定向到下载 (可选，默认 false)
    """
    try:
        # 获取参数
        image_url = request.args.get('url')
        if not image_url:
            return jsonify({
                'error': '缺少必要参数: url',
                'message': '请提供图片URL',
                'example': '/api/quick-convert?url=https://example.com/image.png&width=64&height=64&blocks=wool,concrete&format=schem'
            }), 400
        
        width = request.args.get('width', type=int)
        height = request.args.get('height', type=int)
        blocks_str = request.args.get('blocks', '')
        format_type = request.args.get('format', 'schem')
        username = request.args.get('username', 'API用户')
        redirect_download = request.args.get('redirect', 'false').lower() == 'true'
        auto_download = request.args.get('auto', 'false').lower() == 'true'
        
        # 验证格式
        if format_type not in ['schem', 'json', 'litematic']:
            return jsonify({'error': f'不支持的格式类型: {format_type}'}), 400
        
        # 验证尺寸
        max_size = CONFIG.get('max_image_size', 512)
        if width and (width > max_size * 2 or width < 1):
            return jsonify({'error': f'宽度必须在1-{max_size * 2}之间'}), 400
        if height and (height > max_size * 2 or height < 1):
            return jsonify({'error': f'高度必须在1-{max_size * 2}之间'}), 400
        
        # 下载图片
        logger.info(f"正在从URL下载图片: {image_url}")
        image_bytes, ext = download_image_from_url(image_url)
        
        # 解析方块类型
        selected_blocks = parse_blocks_param(blocks_str)
        
        # 生成文件名
        parsed_url = urlparse(image_url)
        original_filename = Path(parsed_url.path).stem or 'image'
        filename_base = f"{original_filename}_{int(time.time())}"
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建进度管理器
        progress_manager = ConversionProgress(task_id)
        conversion_results[task_id] = progress_manager
        
        # 直接在请求线程中执行转换（因为是快速API）
        convert_image_thread(
            task_id, image_bytes, ext, width, height, 
            selected_blocks, format_type, filename_base, username
        )
        
        # 等待转换完成
        max_wait_time = 30  # 最大等待30秒
        start_time = time.time()
        
        while conversion_results[task_id].is_running:
            time.sleep(0.1)
            if time.time() - start_time > max_wait_time:
                return jsonify({
                    'task_id': task_id,
                    'status': 'processing',
                    'message': '转换仍在进行中，请稍后查询进度',
                    'progress_url': f'/api/progress/{task_id}',
                    'download_url': f'/api/download/{task_id}'
                }), 202
        
        # 检查转换结果
        if task_id not in conversion_results:
            return jsonify({'error': '转换失败，任务不存在'}), 500
        
        progress = conversion_results[task_id]
        
        if not progress.file_path or not Path(progress.file_path).exists():
            error_msg = progress.logs[-1] if progress.logs else '转换失败'
            return jsonify({'error': error_msg}), 500
        
        # 自动下载模式 - 直接返回文件
        if auto_download:
            return send_file(
                progress.file_path,
                as_attachment=True,
                download_name=progress.filename,
                mimetype='application/octet-stream'
            )
        
        # 重定向到下载
        if redirect_download:
            return redirect(url_for('download_file', task_id=task_id))
        
        # 返回JSON结果
        return jsonify({
            'success': True,
            'task_id': task_id,
            'filename': progress.filename,
            'format': format_type,
            'dimensions': {
                'width': progress.dimensions[0] if progress.dimensions else width,
                'height': progress.dimensions[1] if progress.dimensions else height
            },
            'blocks_used': selected_blocks,
            'download_url': f'/api/download/{task_id}',
            'progress_url': f'/api/progress/{task_id}',
            'direct_download_url': f'/api/download/{task_id}',
            'file_size': Path(progress.file_path).stat().st_size if progress.file_path else 0
        })
        
    except Exception as e:
        error_msg = f"快速转换失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/quick-convert-batch')
def quick_convert_batch():
    """
    批量快速转换API - 通过多个URL参数同时转换多张图片
    参数:
        urls: 图片URL列表，逗号分隔 (必需)
        width: 宽度 (可选)
        height: 高度 (可选)
        blocks: 方块类型 (可选)
        format: 输出格式 (可选)
    """
    try:
        urls_str = request.args.get('urls')
        if not urls_str:
            return jsonify({'error': '缺少必要参数: urls'}), 400
        
        urls = urls_str.split(',')
        if len(urls) > 10:
            return jsonify({'error': '批量转换最多支持10个URL'}), 400
        
        width = request.args.get('width', type=int)
        height = request.args.get('height', type=int)
        blocks_str = request.args.get('blocks', '')
        format_type = request.args.get('format', 'schem')
        username = request.args.get('username', 'API批量用户')
        
        selected_blocks = parse_blocks_param(blocks_str)
        
        batch_results = []
        batch_tasks = []
        
        for i, url in enumerate(urls):
            url = url.strip()
            try:
                # 下载图片
                image_bytes, ext = download_image_from_url(url)
                
                # 生成文件名
                parsed_url = urlparse(url)
                original_filename = Path(parsed_url.path).stem or f'image_{i+1}'
                filename_base = f"{original_filename}_{int(time.time())}_{i}"
                
                # 生成任务ID
                task_id = str(uuid.uuid4())
                
                # 创建进度管理器
                progress_manager = ConversionProgress(task_id)
                conversion_results[task_id] = progress_manager
                
                # 启动转换线程
                thread = threading.Thread(
                    target=convert_image_thread,
                    args=(task_id, image_bytes, ext, width, height, 
                          selected_blocks, format_type, filename_base, username)
                )
                thread.daemon = True
                thread.start()
                
                batch_tasks.append({
                    'task_id': task_id,
                    'url': url,
                    'filename': filename_base
                })
                
                batch_results.append({
                    'index': i,
                    'url': url,
                    'status': 'processing',
                    'task_id': task_id,
                    'download_url': f'/api/download/{task_id}',
                    'progress_url': f'/api/progress/{task_id}'
                })
                
            except Exception as e:
                batch_results.append({
                    'index': i,
                    'url': url,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'total': len(urls),
            'processing': len(batch_tasks),
            'results': batch_results,
            'message': f'已启动{len(batch_tasks)}个转换任务'
        })
        
    except Exception as e:
        error_msg = f"批量转换失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/quick-convert/<task_id>/status')
def quick_convert_status(task_id):
    """获取快速转换任务状态"""
    if task_id not in conversion_results:
        return jsonify({'error': '任务不存在'}), 404
    
    progress = conversion_results[task_id]
    
    return jsonify({
        'task_id': task_id,
        'status': 'completed' if not progress.is_running else 'processing',
        'progress': progress.progress,
        'message': progress.message,
        'filename': progress.filename,
        'download_url': f'/api/download/{task_id}',
        'has_file': progress.file_path is not None and Path(progress.file_path).exists()
    })

@app.route('/api/quick-convert-example')
def quick_convert_example():
    """快速转换API使用示例"""
    examples = {
        'description': 'SunPixel 快速转换API使用说明',
        'version': CONFIG['version'],
        'endpoints': {
            'quick_convert': {
                'url': '/api/quick-convert',
                'method': 'GET',
                'description': '通过URL快速转换图片为Minecraft结构',
                'parameters': [
                    {
                        'name': 'url',
                        'required': True,
                        'description': '图片URL地址',
                        'example': 'https://example.com/image.png'
                    },
                    {
                        'name': 'width',
                        'required': False,
                        'description': '输出宽度（方块数）',
                        'example': 64
                    },
                    {
                        'name': 'height',
                        'required': False,
                        'description': '输出高度（方块数）',
                        'example': 64
                    },
                    {
                        'name': 'blocks',
                        'required': False,
                        'description': '方块类型，逗号分隔',
                        'example': 'wool,concrete'
                    },
                    {
                        'name': 'format',
                        'required': False,
                        'description': '输出格式 (schem/json/litematic)',
                        'example': 'schem'
                    },
                    {
                        'name': 'username',
                        'required': False,
                        'description': '用户名',
                        'example': 'SunPixelUser'
                    },
                    {
                        'name': 'auto',
                        'required': False,
                        'description': '自动下载 (true/false)',
                        'example': 'false'
                    },
                    {
                        'name': 'redirect',
                        'required': False,
                        'description': '重定向到下载 (true/false)',
                        'example': 'false'
                    }
                ]
            },
            'batch_convert': {
                'url': '/api/quick-convert-batch',
                'method': 'GET',
                'description': '批量转换多个URL',
                'parameters': [
                    {
                        'name': 'urls',
                        'required': True,
                        'description': '图片URL列表，逗号分隔',
                        'example': 'https://example.com/1.png,https://example.com/2.png'
                    }
                ]
            }
        },
        'usage_examples': [
            {
                'name': '基础使用',
                'url': '/api/quick-convert?url=https://example.com/image.png'
            },
            {
                'name': '指定尺寸',
                'url': '/api/quick-convert?url=https://example.com/image.png&width=128&height=128'
            },
            {
                'name': '指定格式和方块',
                'url': '/api/quick-convert?url=https://example.com/image.png&format=litematic&blocks=wool,concrete'
            },
            {
                'name': '自动下载',
                'url': '/api/quick-convert?url=https://example.com/image.png&auto=true'
            },
            {
                'name': '批量转换',
                'url': '/api/quick-convert-batch?urls=https://example.com/1.png,https://example.com/2.png&width=64'
            }
        ],
        'response_example': {
            'success': True,
            'task_id': '550e8400-e29b-41d4-a716-446655440000',
            'filename': 'image_1234567890.schem',
            'format': 'schem',
            'dimensions': {'width': 64, 'height': 64},
            'download_url': '/api/download/550e8400-e29b-41d4-a716-446655440000'
        },
        'available_blocks': get_available_blocks(),
        'supported_formats': ['schem', 'json', 'litematic']
    }
    
    return jsonify(examples)

# ============ 原有路由保持不变 ============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/changelog')
def changelog():
    return render_template('changelog.html')

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/market')
def market():
    return render_template('market.html')

@app.route('/manual')
def manual():
    return render_template('manual.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    from flask import send_from_directory
    return send_from_directory('assets', filename)

@app.route('/api/blocks')
def get_blocks():
    blocks = get_available_blocks()
    return jsonify(blocks)

@app.route('/api/changelog')
def get_changelog():
    import os
    from datetime import datetime
    
    changelog_dir = Path("Changelog")
    if not changelog_dir.exists():
        return jsonify([])
    
    changelogs = []
    for file_path in changelog_dir.glob("*.md"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            date_str = file_path.stem
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
                
            changelogs.append({
                "date": date_str,
                "content": content,
                "timestamp": date_obj.timestamp()
            })
        except Exception as e:
            print(f"读取更新记录文件 {file_path} 失败: {e}")
            continue
    
    changelogs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    for log in changelogs:
        del log["timestamp"]
    
    return jsonify(changelogs)

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    if task_id not in conversion_results:
        return jsonify({'error': '任务不存在'}), 404
    
    progress = conversion_results[task_id]
    return jsonify({
        'progress': progress.progress,
        'message': progress.message,
        'stage': progress.current_stage,
        'is_running': progress.is_running,
        'logs': progress.logs[-20:],
        'filename': progress.filename,
    })

@app.route('/api/convert', methods=['POST'])
def convert_image():
    try:
        if 'image' not in request.files:
            return jsonify({'error': '没有上传图片'}), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        width = request.form.get('width', type=int)
        height = request.form.get('height', type=int)
        selected_blocks = request.form.getlist('blocks[]')
        format_type = request.form.get('format', 'schem')
        
        if not selected_blocks:
            selected_blocks = ['wool', 'concrete']
        
        if format_type not in ['schem', 'json', 'litematic']:
            return jsonify({'error': '不支持的格式类型'}), 400
        
        image_bytes = image_file.read()
        ext = os.path.splitext(image_file.filename)[1]
        
        if ext.lower() not in ['.png', '.jpg', '.jpeg']:
            return jsonify({'error': '不支持的图片格式'}), 400
        
        username = request.form.get('username', '匿名用户')
        
        task_id = str(uuid.uuid4())
        filename_base = Path(image_file.filename).stem
        
        progress_manager = ConversionProgress(task_id)
        conversion_results[task_id] = progress_manager
        
        thread = threading.Thread(
            target=convert_image_thread,
            args=(task_id, image_bytes, ext, width, height, selected_blocks, format_type, filename_base, username)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '转换已开始'
        })
        
    except Exception as e:
        error_msg = f"服务器错误: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/download/<task_id>')
def download_file(task_id):
    if task_id in conversion_results:
        progress = conversion_results[task_id]
        
        if not progress.file_path or not Path(progress.file_path).exists():
            return jsonify({'error': '文件未就绪或已过期'}), 404
        
        try:
            file_path = Path(progress.file_path)
            if not file_path.is_file():
                return jsonify({'error': '文件不存在'}), 404
            
            safe_filename = progress.filename.replace('..', '').replace('/', '').replace('\\', '')
            
            progress.download_count += 1
            
            response = send_file(
                str(file_path),
                as_attachment=True,
                download_name=safe_filename,
                mimetype='application/octet-stream'
            )
            
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            
            return response
            
        except Exception as e:
            error_msg = f'下载失败: {str(e)}'
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500
    
    else:
        for history_item in history_records:
            if history_item['id'] == task_id:
                if not Path(history_item['file_path']).exists():
                    return jsonify({'error': '历史文件不存在'}), 404
                
                try:
                    safe_filename = history_item['filename'].replace('..', '').replace('/', '').replace('\\', '')
                    
                    for item in history_records:
                        if item['id'] == task_id:
                            item['download_count'] = item.get('download_count', 0) + 1
                            break
                    
                    return send_file(
                        history_item['file_path'],
                        as_attachment=True,
                        download_name=safe_filename
                    )
                    
                except Exception as e:
                    error_msg = f'下载历史文件失败: {str(e)}'
                    logger.error(error_msg)
                    return jsonify({'error': error_msg}), 500
        
        return jsonify({'error': '文件不存在'}), 404

@app.route('/api/history', methods=['GET'])
def get_history():
    try:
        return jsonify(history_records)
    except Exception as e:
        error_msg = f"获取历史记录失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/history/<task_id>', methods=['DELETE'])
def delete_history_item(task_id):
    try:
        global history_records
        history_records = [item for item in history_records if item['id'] != task_id]
        
        return jsonify({
            'success': True,
            'message': '历史记录项已删除'
        })
    except Exception as e:
        error_msg = f"删除历史记录失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/history/<task_id>/upload_to_market', methods=['POST'])
def upload_history_to_market(task_id):
    try:
        history_item = None
        for item in history_records:
            if item['id'] == task_id:
                history_item = item
                break
        
        if not history_item:
            return jsonify({'error': '历史记录项不存在'}), 404
        
        if not Path(history_item['file_path']).exists():
            return jsonify({'error': '文件不存在'}), 404
        
        with open(history_item['file_path'], 'rb') as f:
            file_content = f.read()
        
        title = request.form.get('title', history_item['filename'])
        description = request.form.get('description', f"由 {history_item['username']} 上传的结构文件")
        author = request.form.get('author', history_item['username'])
        
        file_ext = Path(history_item['file_path']).suffix
        market_filename = f"{uuid.uuid4()}{file_ext}"
        market_filepath = TEMP_DIR / market_filename
        
        with open(market_filepath, 'wb') as f:
            f.write(file_content)
        
        market_item = {
            'id': str(uuid.uuid4()),
            'title': title,
            'description': description,
            'author': author,
            'filename': Path(market_filepath).name,
            'file_path': str(market_filepath),
            'upload_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'download_count': 0,
            'favorites': 0,
            'tags': []
        }
        
        market_items.append(market_item)
        
        return jsonify({
            'success': True,
            'message': '文件已成功上传到市场',
            'file_id': market_item['id']
        })
        
    except Exception as e:
        error_msg = f"上传到市场失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/market', methods=['GET'])
def get_market_items():
    try:
        simplified_items = []
        for item in market_items:
            simplified_item = {
                'id': item['id'],
                'title': item['title'],
                'description': item['description'],
                'author': item['author'],
                'filename': item['filename'],
                'upload_time': item['upload_time'],
                'download_count': item['download_count'],
                'favorites': item['favorites']
            }
            simplified_items.append(simplified_item)
        
        return jsonify(simplified_items)
    except Exception as e:
        error_msg = f"获取市场项目失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/market/upload', methods=['POST'])
def upload_direct_to_market():
    try:
        author = request.form.get('author')
        if not author:
            return jsonify({'error': '需要提供作者信息'}), 400
        
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        title = request.form.get('title', f'作品_{int(time.time())}')
        description = request.form.get('description', '通过SunPixel上传的结构文件')
        
        file_ext = Path(file.filename).suffix
        market_filename = f"{uuid.uuid4()}{file_ext}"
        market_filepath = TEMP_DIR / market_filename
        
        file.save(str(market_filepath))
        
        market_item = {
            'id': str(uuid.uuid4()),
            'title': title,
            'description': description,
            'author': author,
            'filename': Path(market_filepath).name,
            'file_path': str(market_filepath),
            'upload_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'download_count': 0,
            'favorites': 0,
            'tags': []
        }
        
        market_items.append(market_item)
        
        return jsonify({
            'success': True,
            'message': '文件已成功上传到市场',
            'file_id': market_item['id']
        })
        
    except Exception as e:
        error_msg = f"上传到市场失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/market/<item_id>/download', methods=['GET'])
def download_market_item(item_id):
    try:
        market_item = None
        for item in market_items:
            if item['id'] == item_id:
                market_item = item
                break
        
        if not market_item:
            return jsonify({'error': '市场项目不存在'}), 404
        
        if not Path(market_item['file_path']).exists():
            return jsonify({'error': '文件不存在'}), 404
        
        for item in market_items:
            if item['id'] == item_id:
                item['download_count'] += 1
                break
        
        return send_file(
            market_item['file_path'],
            as_attachment=True,
            download_name=market_item['filename']
        )
        
    except Exception as e:
        error_msg = f"下载失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/market/<item_id>/favorite', methods=['POST'])
def favorite_market_item(item_id):
    try:
        market_item = None
        for item in market_items:
            if item['id'] == item_id:
                market_item = item
                break
        
        if not market_item:
            return jsonify({'error': '市场项目不存在'}), 404
        
        for item in market_items:
            if item['id'] == item_id:
                item['favorites'] += 1
                break
        
        return jsonify({
            'success': True,
            'message': '项目已收藏',
            'favorites': market_item['favorites'] if market_item else 0
        })
        
    except Exception as e:
        error_msg = f"收藏失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/user/<username>', methods=['GET'])
def get_user_stats(username):
    try:
        user_items = [item for item in market_items if item['author'] == username]
        total_uploads = len(user_items)
        total_downloads = sum(item['download_count'] for item in user_items)
        total_favorites = sum(item['favorites'] for item in user_items)
        
        user_projects = []
        for item in user_items:
            user_projects.append({
                'id': item['id'],
                'title': item['title'],
                'description': item['description'],
                'filename': item['filename'],
                'upload_time': item['upload_time'],
                'download_count': item['download_count'],
                'favorites': item['favorites']
            })
        
        user_stats = {
            'username': username,
            'total_uploads': total_uploads,
            'total_downloads': total_downloads,
            'total_favorites': total_favorites,
            'projects': user_projects
        }
        
        return jsonify(user_stats)
        
    except Exception as e:
        error_msg = f"获取用户统计数据失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/upload_to_market', methods=['POST'])
def upload_to_market():
    try:
        author = request.form.get('author')
        if not author:
            return jsonify({'error': '需要提供作者信息'}), 400
        
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        title = request.form.get('title', f'作品_{int(time.time())}')
        description = request.form.get('description', '通过SunPixel转换的结构文件')
        
        file_ext = Path(file.filename).suffix
        market_filename = f"{uuid.uuid4()}{file_ext}"
        market_filepath = TEMP_DIR / market_filename
        
        file.save(str(market_filepath))
        
        return jsonify({
            'success': True,
            'message': '文件已成功上传到市场',
            'file_id': market_filename
        })
        
    except Exception as e:
        error_msg = f"上传到市场失败: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

def cleanup_temp_files():
    """清理旧的临时文件"""
    current_time = time.time()
    
    expired_tasks = []
    for task_id, progress in conversion_results.items():
        if not progress.is_running and current_time - progress.create_time > 3600:
            expired_tasks.append(task_id)
            
            if progress.file_path and Path(progress.file_path).exists():
                try:
                    Path(progress.file_path).unlink()
                except Exception:
                    pass
    
    for task_id in expired_tasks:
        if task_id in conversion_results:
            del conversion_results[task_id]
    
    if TEMP_DIR.exists():
        for file in TEMP_DIR.iterdir():
            if file.is_file():
                file_age = current_time - file.stat().st_mtime
                if file_age > 3600:
                    try:
                        file.unlink()
                    except Exception:
                        pass

if __name__ == '__main__':
    # 确保block目录存在
    block_dir = Path("block")
    if not block_dir.exists():
        create_default_block_files()
        print("✅ 已创建默认方块映射文件")
    
    # 确保requests库已安装
    try:
        import requests
    except ImportError:
        print("⚠️ 需要安装requests库来支持URL图片下载")
        print("💡 请运行: pip install requests")
        sys.exit(1)
    
    print("🚀 SunPixel Web服务器启动中...")
    print(f"📝 版本: {CONFIG['version']}")
    print(f"🌐 访问 http://127.0.0.1:{CONFIG['web_server']['port']} 使用Web界面")
    print("⚡ 快速转换API已启用!")
    print("📖 查看API使用说明: http://127.0.0.1:{}/api/quick-convert-example".format(CONFIG['web_server']['port']))
    
    app.run(
        debug=CONFIG['web_server'].get('debug', False),
        host=CONFIG['web_server'].get('host', '0.0.0.0'),
        port=CONFIG['web_server'].get('port', 5000)
    )