from flask import Flask, request, jsonify, render_template, send_file, Response
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
        self.file_path = None  # 存储文件路径
        self.download_count = 0  # 记录下载次数
        
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
        
    def set_result(self, file_path, filename):
        """设置转换结果"""
        self.file_path = file_path
        self.filename = filename
        
    def reset(self):
        self.progress = 0
        self.message = ""
        self.is_running = False
        self.current_stage = ""
        self.logs = []
        self.file_path = None
        self.filename = ""
        self.download_count = 0

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
        
        # 初始化方块调色板
        self.block_palette = list(set([block[0] for block in self.color_to_block.values()]))
        self.log(f"🎨 初始化调色板: {len(self.block_palette)} 种方块")
        self.update_progress(50, f"🎨 初始化调色板: {len(self.block_palette)} 种方块")
        
        # 创建方块数据数组
        self.block_data = np.zeros((self.depth, self.height, self.width), dtype=int)
        self.block_data_values = np.zeros((self.depth, self.height, self.width), dtype=int)
        
        # 计算缩放比例
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        self.update_progress(55, "🔄 正在处理像素数据...", "处理像素")
        total_pixels = self.width * self.height
        processed_pixels = 0
        
        # 填充方块数据
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
        
        # 根据格式创建不同的文件
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
        # 创建NBT数据结构
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
        
        # 保存到临时文件
        filename = f"{filename_base}.schem"
        filepath = TEMP_DIR / filename
        
        nbt_file = nbtlib.File(schematic)
        nbt_file.save(str(filepath), gzipped=True)
        
        self.log("✅ schem文件保存完成")
        self.update_progress(95, "✅ schem文件保存完成")
        return filepath, filename
        
    def _save_json_file(self, filename_base):
        """保存JSON文件（RunAway格式）"""
        # 创建JSON结构数据
        json_data = {
            "name": filename_base,
            "author": "SunPixel",
            "version": "1.0",
            "size": {
                "width": int(self.width),  # 转换为Python int
                "height": int(self.depth),
                "length": int(self.height)
            },
            "blocks": []
        }
        
        # 添加方块数据
        for y in range(self.height):
            for x in range(self.width):
                block_index = int(self.block_data[0, y, x])  # 转换为Python int
                if block_index < len(self.block_palette):
                    block_name = self.block_palette[block_index]
                    block_data = int(self.block_data_values[0, y, x])  # 转换为Python int
                    
                    json_data["blocks"].append({
                        "x": int(x),
                        "y": 0,
                        "z": int(y),
                        "block": block_name,
                        "data": block_data
                    })
        
        # 保存到临时文件
        filename = f"{filename_base}.json"
        filepath = TEMP_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        self.log("✅ JSON文件保存完成")
        self.update_progress(95, "✅ JSON文件保存完成")
        return filepath, filename
        
    def _save_litematic_file(self, filename_base):
        """保存litematic文件"""
        # 创建Litematica的简化版本
        # 注意：这是简化的实现，完整实现需要更多数据结构
        
        litematic_data = {
            "Version": 5,
            "Metadata": {
                "EnclosingSize": {
                    "x": int(self.width),  # 转换为Python int
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
                    "Size": {"x": int(self.width), "y": int(self.depth), "z": int(self.height)},  # 转换为Python int
                    "BlockStatePalette": [
                        {"Name": block_name, "Properties": {}} 
                        for block_name in self.block_palette
                    ],
                    "BlockStates": self.block_data.flatten(order='C').astype(int).tolist()  # 转换为Python list
                }
            }
        }
        
        # 保存到临时文件
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
            
            # 添加成功日志
            self.log(f"✅ 转换成功完成!")
            self.log(f"📐 生成结构尺寸: {self.width} × {self.height} 方块")
            self.log(f"🧱 总方块数量: {self.width * self.height} 个")
            self.log(f"🎨 使用的方块类型: {', '.join(selected_blocks)}")
            self.log(f"📁 输出文件: {filename}")
            
            self.update_progress(100, "🎉 转换成功完成!", "完成")
            
            # 设置结果
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
        # 创建默认方块文件
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
    
    # 羊毛颜色映射
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
    
    wool_mapping = {}
    for color_name, (block, data) in wool_colors.items():
        # 创建RGB颜色值
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
        
        if color_name in rgb_map:
            rgb = rgb_map[color_name]
            wool_mapping[f"{rgb[0]},{rgb[1]},{rgb[2]}"] = [block, data]
    
    with open(block_dir / "wool.json", 'w', encoding='utf-8') as f:
        json.dump(wool_mapping, f, indent=2, ensure_ascii=False)
    
    # 混凝土颜色映射
    concrete_mapping = {}
    for color_name, (block_base, data) in wool_colors.items():
        block_name = block_base.replace("_wool", "_concrete")
        if color_name in rgb_map:
            rgb = rgb_map[color_name]
            concrete_mapping[f"{rgb[0]},{rgb[1]},{rgb[2]}"] = [block_name, data]
    
    with open(block_dir / "concrete.json", 'w', encoding='utf-8') as f:
        json.dump(concrete_mapping, f, indent=2, ensure_ascii=False)

def convert_image_thread(task_id, image_bytes, ext, width, height, selected_blocks, format_type, filename):
    """在单独线程中执行图片转换"""
    progress_manager = conversion_results[task_id]
    converter = WebImageToStructure(progress_manager, CONFIG)
    success = converter.convert(image_bytes, ext, width, height, selected_blocks, format_type, filename)
    
    if not success:
        progress_manager.log("❌ 转换失败")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/blocks')
def get_blocks():
    blocks = get_available_blocks()
    return jsonify(blocks)

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """获取转换进度"""
    if task_id not in conversion_results:
        return jsonify({'error': '任务不存在'}), 404
    
    progress = conversion_results[task_id]
    return jsonify({
        'progress': progress.progress,
        'message': progress.message,
        'stage': progress.current_stage,
        'is_running': progress.is_running,
        'logs': progress.logs[-20:],  # 返回最近20条日志
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
        
        # 获取参数
        width = request.form.get('width', type=int)
        height = request.form.get('height', type=int)
        selected_blocks = request.form.getlist('blocks[]')
        format_type = request.form.get('format', 'schem')
        
        if not selected_blocks:
            selected_blocks = ['wool', 'concrete']
        
        # 验证格式
        if format_type not in ['schem', 'json', 'litematic']:
            return jsonify({'error': '不支持的格式类型'}), 400
        
        # 读取图片数据
        image_bytes = image_file.read()
        ext = os.path.splitext(image_file.filename)[1]
        
        # 检查文件格式
        if ext.lower() not in ['.png', '.jpg', '.jpeg']:
            return jsonify({
                'error': '不支持的图片格式'
            }), 400
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        filename_base = Path(image_file.filename).stem
        
        # 创建进度管理器
        progress_manager = ConversionProgress(task_id)
        conversion_results[task_id] = progress_manager
        
        # 在单独线程中执行转换
        thread = threading.Thread(
            target=convert_image_thread,
            args=(task_id, image_bytes, ext, width, height, selected_blocks, format_type, filename_base)
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
    """下载转换结果文件"""
    if task_id not in conversion_results:
        return jsonify({'error': '文件不存在'}), 404
    
    progress = conversion_results[task_id]
    
    if not progress.file_path or not Path(progress.file_path).exists():
        return jsonify({'error': '文件未就绪或已过期'}), 404
    
    try:
        # 防止重复下载
        if progress.download_count >= 1:
            logger.warning(f"任务 {task_id} 已被下载 {progress.download_count} 次，阻止重复下载")
            # 直接删除文件，返回错误
            try:
                if Path(progress.file_path).exists():
                    Path(progress.file_path).unlink()
                if task_id in conversion_results:
                    del conversion_results[task_id]
            except Exception as e:
                logger.error(f"清理文件失败: {e}")
            
            return jsonify({'error': '文件已被下载过，请重新转换'}), 403
        
        # 确保文件路径安全
        file_path = Path(progress.file_path)
        if not file_path.is_file():
            return jsonify({'error': '文件不存在'}), 404
        
        # 清理文件名
        safe_filename = progress.filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # 增加下载计数
        progress.download_count += 1
        
        # 发送文件
        response = send_file(
            str(file_path),
            as_attachment=True,
            download_name=safe_filename,
            mimetype='application/octet-stream'
        )
        
        # 设置缓存控制头
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        # 删除临时文件
        def cleanup():
            try:
                if file_path.exists():
                    file_path.unlink()
                if task_id in conversion_results:
                    del conversion_results[task_id]
            except Exception as e:
                logger.error(f"清理文件失败: {e}")
        
        # 延迟清理
        threading.Timer(10.0, cleanup).start()
        
        return response
        
    except Exception as e:
        error_msg = f'下载失败: {str(e)}'
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

def cleanup_temp_files():
    """清理旧的临时文件"""
    current_time = time.time()
    
    # 清理转换结果
    expired_tasks = []
    for task_id, progress in conversion_results.items():
        if not progress.is_running and current_time - progress.create_time > 3600:
            expired_tasks.append(task_id)
            
            # 清理文件
            if progress.file_path and Path(progress.file_path).exists():
                try:
                    Path(progress.file_path).unlink()
                except Exception:
                    pass
    
    for task_id in expired_tasks:
        if task_id in conversion_results:
            del conversion_results[task_id]
    
    # 清理临时目录中的旧文件
    if TEMP_DIR.exists():
        for file in TEMP_DIR.iterdir():
            if file.is_file():
                file_age = current_time - file.stat().st_mtime
                if file_age > 3600:  # 超过1小时的文件
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
    
    print("🚀 SunPixel Web服务器启动中...")
    print(f"📝 版本: {CONFIG['version']}")
    print(f"🌐 访问 http://127.0.0.1:{CONFIG['web_server']['port']} 使用Web界面")
    
    app.run(
        debug=CONFIG['web_server'].get('debug', False),
        host=CONFIG['web_server'].get('host', '0.0.0.0'),
        port=CONFIG['web_server'].get('port', 5000)
    )