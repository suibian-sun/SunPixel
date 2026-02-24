import numpy as np
import png
from PIL import Image
import nbtlib
from nbtlib.tag import Byte, Short, Int, Long, Float, Double, String, List, Compound
import os
import time
import math
import json
from pathlib import Path
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
from functools import lru_cache
import re


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


class FastColorMatcher:
    """极致优化的颜色匹配器"""
    def __init__(self, color_to_block):
        self.color_to_block = color_to_block
        
        # 预计算所有目标颜色和对应的方块
        self.target_colors = []  # RGB元组列表
        self.block_mapping = []  # (方块名, 数据值) 列表
        
        for color_str, block_info in color_to_block.items():
            try:
                # 快速解析颜色字符串
                rgb = self._parse_color_fast(color_str)
                if rgb:
                    if isinstance(block_info, list) and len(block_info) >= 2:
                        self.block_mapping.append((block_info[0], block_info[1]))
                    else:
                        self.block_mapping.append(("minecraft:white_concrete", 0))
                    
                    self.target_colors.append(rgb)
            except:
                continue
        
        if not self.target_colors:
            # 默认颜色映射
            self.target_colors = [(255, 255, 255), (0, 0, 0)]
            self.block_mapping = [("minecraft:white_concrete", 0), ("minecraft:black_concrete", 0)]
        
        # 转换为numpy数组并预计算
        self.target_colors_np = np.array(self.target_colors, dtype=np.uint8)
        
        # 预计算颜色查找表（8位量化）
        self._build_color_lut()
    
    def _parse_color_fast(self, color_str):
        """快速解析颜色字符串"""
        if not color_str or not isinstance(color_str, str):
            return None
            
        # 移除括号
        s = color_str.strip()
        if s.startswith('(') and s.endswith(')'):
            s = s[1:-1]
        elif s.startswith('[') and s.endswith(']'):
            s = s[1:-1]
        
        # 分割并取前三个数字
        parts = s.split(',')
        if len(parts) >= 3:
            try:
                r = int(parts[0].strip())
                g = int(parts[1].strip())
                b = int(parts[2].strip())
                return (r, g, b)
            except:
                return None
        return None
    
    def _build_color_lut(self):
        """构建颜色查找表（64x64x64）"""
        print(f"{Color.CYAN}🎨 构建颜色查找表...{Color.RESET}")
        
        # 8位量化到6位（64级）以减少内存使用
        self.lut_size = 64
        self.lut_step = 4  # 256 / 64 = 4
        
        # 创建查找表
        self.color_lut = np.zeros((self.lut_size, self.lut_size, self.lut_size, 2), dtype=np.uint16)
        
        # 填充查找表
        for r_idx in range(self.lut_size):
            r = r_idx * self.lut_step + self.lut_step // 2
            for g_idx in range(self.lut_size):
                g = g_idx * self.lut_step + self.lut_step // 2
                for b_idx in range(self.lut_size):
                    b = b_idx * self.lut_step + self.lut_step // 2
                    
                    # 找到最接近的颜色
                    closest_idx = self._find_closest_idx_fast((r, g, b))
                    self.color_lut[r_idx, g_idx, b_idx] = closest_idx
    
    def _find_closest_idx_fast(self, rgb):
        """快速找到最接近颜色的索引"""
        if not self.target_colors_np.size:
            return (0, 0)
        
        r, g, b = rgb
        target_r = self.target_colors_np[:, 0]
        target_g = self.target_colors_np[:, 1]
        target_b = self.target_colors_np[:, 2]
        
        # 使用曼哈顿距离（比欧氏距离快）
        dist = np.abs(target_r - r) + np.abs(target_g - g) + np.abs(target_b - b)
        idx = np.argmin(dist)
        
        return idx
    
    @lru_cache(maxsize=65536)
    def find_closest_color_cached(self, r, g, b):
        """带缓存的颜色查找"""
        if not self.target_colors_np.size:
            return ("minecraft:white_concrete", 0)
        
        # 使用查找表（如果可用）
        if hasattr(self, 'color_lut'):
            r_idx = min(r // self.lut_step, self.lut_size - 1)
            g_idx = min(g // self.lut_step, self.lut_size - 1)
            b_idx = min(b // self.lut_step, self.lut_size - 1)
            
            block_idx = self.color_lut[r_idx, g_idx, b_idx]
            return self.block_mapping[block_idx]
        
        # 回退到计算
        idx = self._find_closest_idx_fast((r, g, b))
        return self.block_mapping[idx]
    
    def find_closest_color(self, rgb):
        """查找最接近颜色"""
        r, g, b = rgb
        return self.find_closest_color_cached(r, g, b)


class schemConverter:
    """schem格式转换器 - 极致优化版本"""
    def __init__(self, config):
        self.config = config
        self.color_to_block = {}
        self.block_palette = []
        self.block_data = None
        self.block_data_values = None
        self.width = 0
        self.height = 0
        self.depth = 1
        self.pixels = None
        self.original_width = 0
        self.original_height = 0
        
        # CPU核心数
        self.cpu_count = mp.cpu_count()
        print(f"{Color.CYAN}⚡ 检测到 {self.cpu_count} 个CPU核心{Color.RESET}")
        
        self.color_matcher = None
    
    def load_block_mappings_fast(self, selected_blocks):
        """快速加载方块映射"""
        print(f"{Color.CYAN}📦 正在加载方块映射...{Color.RESET}")
        start_time = time.time()
        
        self.color_to_block = {}
        block_dir = Path("block")
        
        if not block_dir.exists():
            print(f"{Color.RED}❌ 错误: block目录不存在!{Color.RESET}")
            self._create_default_mappings()
            self.color_matcher = FastColorMatcher(self.color_to_block)
            return True
        
        # 读取所有JSON文件
        json_files = list(block_dir.glob("*.json"))
        if not json_files:
            print(f"{Color.RED}❌ 错误: block目录中没有JSON文件!{Color.RESET}")
            self._create_default_mappings()
            self.color_matcher = FastColorMatcher(self.color_to_block)
            return True
        
        for block_file in json_files:
            block_name = block_file.stem
            if selected_blocks and block_name not in selected_blocks:
                continue
                
            try:
                with open(block_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for color_key, block_info in data.items():
                    color_str = str(color_key).strip()
                    
                    # 确保是列表格式
                    if not isinstance(block_info, list):
                        if isinstance(block_info, str):
                            block_info = [block_info, 0]
                        else:
                            block_info = ["minecraft:white_concrete", 0]
                    
                    self.color_to_block[color_str] = block_info
                    
            except Exception as e:
                print(f"{Color.YELLOW}⚠️  跳过 {block_file.name}: {e}{Color.RESET}")
                continue
        
        # 如果没有加载到数据，使用默认
        if not self.color_to_block:
            print(f"{Color.YELLOW}⚠️  使用默认颜色映射{Color.RESET}")
            self._create_default_mappings()
        
        # 初始化颜色匹配器
        self.color_matcher = FastColorMatcher(self.color_to_block)
        
        load_time = time.time() - start_time
        print(f"{Color.GREEN}✅ 加载完成: {len(self.color_to_block)} 种颜色映射 ({load_time:.3f}s){Color.RESET}")
        return True
    
    def load_image_ultrafast(self, image_path):
        """极速加载图片"""
        print(f"{Color.CYAN}🖼️  正在加载图片...{Color.RESET}")
        start_time = time.time()
        
        try:
            # 使用PIL快速加载
            with Image.open(image_path) as img:
                # 转换为RGB
                if img.mode == 'RGBA':
                    # 快速RGBA转RGB
                    img_rgb = Image.new('RGB', img.size, (255, 255, 255))
                    img_rgb.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                    img = img_rgb
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 直接转换为numpy数组
                self.pixels = np.array(img, dtype=np.uint8)
                self.original_height, self.original_width = self.pixels.shape[:2]
                
        except Exception as e:
            print(f"{Color.RED}❌ 加载图片失败: {e}{Color.RESET}")
            raise
        
        load_time = time.time() - start_time
        print(f"{Color.GREEN}✅ 图片加载完成: {self.original_width} × {self.original_height} 像素 ({load_time:.3f}s){Color.RESET}")
    
    def set_size(self, width, height):
        """设置尺寸"""
        self.width = max(1, width)
        self.height = max(1, height)
        print(f"{Color.CYAN}📐 设置尺寸: {self.width} × {self.height} 方块{Color.RESET}")
    
    def generate_block_data_ultrafast(self):
        """极速生成方块数据"""
        print(f"{Color.CYAN}🔨 正在生成方块数据...{Color.RESET}")
        start_time = time.time()
        
        # 收集方块名称
        block_names_set = set()
        for block_info in self.color_to_block.values():
            if isinstance(block_info, list) and block_info:
                block_names_set.add(block_info[0])
        
        self.block_palette = list(block_names_set)
        if not self.block_palette:
            self.block_palette = ["minecraft:white_concrete"]
        
        print(f"{Color.CYAN}🎨 调色板: {len(self.block_palette)} 种方块{Color.RESET}")
        
        # 创建映射
        block_name_to_index = {name: idx for idx, name in enumerate(self.block_palette)}
        
        # 预分配内存
        self.block_data = np.zeros((self.depth, self.height, self.width), dtype=np.uint8)
        self.block_data_values = np.zeros((self.depth, self.height, self.width), dtype=np.uint8)
        
        # 计算缩放比例
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        total_pixels = self.width * self.height
        print(f"{Color.CYAN}⚡ 处理 {total_pixels:,} 个像素{Color.RESET}")
        
        # 进度显示
        last_progress_time = time.time()
        processed = 0
        
        # 预计算采样网格
        x_samples = np.arange(self.width) * scale_x
        y_samples = np.arange(self.height) * scale_y
        
        x_indices = x_samples.astype(np.int32)
        y_indices = y_samples.astype(np.int32)
        
        # 获取图片数据
        pixels = self.pixels
        
        # 批量处理 - 使用numpy向量化操作
        batch_size = min(1000, self.height)  # 动态调整批次大小
        
        for y_start in range(0, self.height, batch_size):
            y_end = min(y_start + batch_size, self.height)
            
            # 批量处理Y轴
            y_batch = y_indices[y_start:y_end]
            y_batch_end = np.minimum((y_batch + np.ceil(scale_y)).astype(np.int32), self.original_height)
            
            for x_start in range(0, self.width, batch_size):
                x_end = min(x_start + batch_size, self.width)
                
                # 批量处理X轴
                x_batch = x_indices[x_start:x_end]
                x_batch_end = np.minimum((x_batch + np.ceil(scale_x)).astype(np.int32), self.original_width)
                
                # 使用numpy向量化处理这个批次
                for i, y in enumerate(range(y_start, y_end)):
                    y_src = y_batch[i]
                    y_src_end = y_batch_end[i]
                    
                    if y_src >= y_src_end:
                        continue
                    
                    # 提取整行
                    row_data = pixels[y_src:y_src_end]
                    
                    for j, x in enumerate(range(x_start, x_end)):
                        x_src = x_batch[j]
                        x_src_end = x_batch_end[j]
                        
                        if x_src >= x_src_end:
                            continue
                        
                        # 提取区域
                        region = row_data[:, x_src:x_src_end]
                        
                        if region.size > 0:
                            # 快速计算平均颜色（使用整数运算）
                            avg_color = (
                                int(region[:, :, 0].mean()),
                                int(region[:, :, 1].mean()),
                                int(region[:, :, 2].mean())
                            )
                        else:
                            avg_color = (255, 255, 255)
                        
                        # 查找颜色
                        block_name, block_data = self.color_matcher.find_closest_color(avg_color)
                        
                        # 获取索引
                        block_idx = block_name_to_index.get(block_name, 0)
                        
                        # 直接赋值
                        self.block_data[0, y, x] = block_idx
                        self.block_data_values[0, y, x] = block_data
                
                processed += (x_end - x_start) * (y_end - y_start)
                
                # 进度更新
                current_time = time.time()
                if current_time - last_progress_time > 0.1:  # 每100ms更新一次
                    percent = (processed / total_pixels) * 100
                    bar_length = 30
                    filled = int(bar_length * processed // total_pixels)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    
                    # 计算速度
                    elapsed = current_time - start_time
                    speed = processed / elapsed if elapsed > 0 else 0
                    
                    sys.stdout.write(f'\r📊 处理进度: [{bar}] {processed}/{total_pixels} ({percent:.1f}%) - {speed:.0f}像素/秒')
                    sys.stdout.flush()
                    last_progress_time = current_time
        
        # 完成进度显示
        percent = 100.0
        bar = '█' * 30
        elapsed = time.time() - start_time
        speed = total_pixels / elapsed if elapsed > 0 else 0
        
        sys.stdout.write(f'\r📊 处理进度: [{bar}] {total_pixels}/{total_pixels} ({percent:.1f}%) - {speed:.0f}像素/秒 ✅\n')
        sys.stdout.flush()
        
        print(f"{Color.GREEN}✅ 方块数据生成完成 ({elapsed:.3f}s){Color.RESET}")
    
    def generate_block_data_threaded(self):
        """多线程生成方块数据"""
        print(f"{Color.CYAN}🔨 正在生成方块数据 (多线程模式)...{Color.RESET}")
        start_time = time.time()
        
        # 收集方块名称
        block_names_set = set()
        for block_info in self.color_to_block.values():
            if isinstance(block_info, list) and block_info:
                block_names_set.add(block_info[0])
        
        self.block_palette = list(block_names_set)
        if not self.block_palette:
            self.block_palette = ["minecraft:white_concrete"]
        
        print(f"{Color.CYAN}🎨 调色板: {len(self.block_palette)} 种方块{Color.RESET}")
        
        # 创建映射
        block_name_to_index = {name: idx for idx, name in enumerate(self.block_palette)}
        
        # 预分配内存
        self.block_data = np.zeros((self.depth, self.height, self.width), dtype=np.uint8)
        self.block_data_values = np.zeros((self.depth, self.height, self.width), dtype=np.uint8)
        
        # 计算缩放比例
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        total_pixels = self.width * self.height
        print(f"{Color.CYAN}⚡ 处理 {total_pixels:,} 个像素，使用 {self.cpu_count} 个线程{Color.RESET}")
        
        # 进度相关
        progress_lock = threading.Lock()
        processed_count = 0
        last_update_time = time.time()
        
        def update_progress(count):
            nonlocal processed_count, last_update_time
            with progress_lock:
                processed_count += count
                current_time = time.time()
                
                # 每100ms更新一次显示
                if current_time - last_update_time > 0.1 or processed_count >= total_pixels:
                    percent = (processed_count / total_pixels) * 100
                    bar_length = 30
                    filled = int(bar_length * processed_count // total_pixels)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    
                    # 计算速度
                    elapsed = current_time - start_time
                    speed = processed_count / elapsed if elapsed > 0 else 0
                    eta = (total_pixels - processed_count) / speed if speed > 0 else 0
                    
                    sys.stdout.write(f'\r📊 处理进度: [{bar}] {processed_count}/{total_pixels} ({percent:.1f}%) - {speed:.0f}像素/秒 - ETA: {eta:.1f}s')
                    sys.stdout.flush()
                    last_update_time = current_time
        
        def process_chunk(chunk_rows):
            """处理一个数据块"""
            chunk_results = []
            
            # 预计算这个块的坐标
            y_start, y_end = chunk_rows
            scale_x = self.original_width / self.width
            scale_y = self.original_height / self.height
            
            # 预计算X坐标
            x_samples = np.arange(self.width) * scale_x
            x_indices = x_samples.astype(np.int32)
            x_indices_end = np.minimum((x_indices + np.ceil(scale_x)).astype(np.int32), self.original_width)
            
            # 预计算Y坐标
            y_samples = np.arange(y_start, y_end) * scale_y
            y_indices = y_samples.astype(np.int32)
            y_indices_end = np.minimum((y_indices + np.ceil(scale_y)).astype(np.int32), self.original_height)
            
            pixels = self.pixels
            
            for i, y in enumerate(range(y_start, y_end)):
                y_src = y_indices[i]
                y_src_end = y_indices_end[i]
                
                if y_src >= y_src_end:
                    continue
                
                # 提取整行
                row_data = pixels[y_src:y_src_end]
                
                for x in range(self.width):
                    x_src = x_indices[x]
                    x_src_end = x_indices_end[x]
                    
                    if x_src >= x_src_end:
                        continue
                    
                    # 提取区域
                    region = row_data[:, x_src:x_src_end]
                    
                    if region.size > 0:
                        # 快速计算平均颜色
                        avg_color = (
                            int(region[:, :, 0].mean()),
                            int(region[:, :, 1].mean()),
                            int(region[:, :, 2].mean())
                        )
                    else:
                        avg_color = (255, 255, 255)
                    
                    # 查找颜色
                    block_name, block_data = self.color_matcher.find_closest_color(avg_color)
                    
                    # 获取索引
                    block_idx = block_name_to_index.get(block_name, 0)
                    
                    chunk_results.append((x, y, block_idx, block_data))
            
            update_progress(len(chunk_results))
            return chunk_results
        
        # 将图片分成块
        chunk_size = max(1, self.height // (self.cpu_count * 2))
        chunks = []
        
        for y_start in range(0, self.height, chunk_size):
            y_end = min(y_start + chunk_size, self.height)
            chunks.append((y_start, y_end))
        
        # 使用线程池
        with ThreadPoolExecutor(max_workers=self.cpu_count) as executor:
            futures = []
            
            # 提交所有任务
            for chunk in chunks:
                future = executor.submit(process_chunk, chunk)
                futures.append(future)
            
            # 收集结果
            for future in futures:
                try:
                    chunk_results = future.result(timeout=30)
                    
                    # 更新数据
                    for x, y, block_idx, block_data in chunk_results:
                        self.block_data[0, y, x] = block_idx
                        self.block_data_values[0, y, x] = block_data
                        
                except Exception as e:
                    print(f"{Color.RED}❌ 处理块时出错: {e}{Color.RESET}")
        
        # 完成进度显示
        elapsed = time.time() - start_time
        speed = total_pixels / elapsed if elapsed > 0 else 0
        
        sys.stdout.write(f'\r📊 处理进度: [{"█" * 30}] {total_pixels}/{total_pixels} (100.0%) - {speed:.0f}像素/秒 ✅\n')
        sys.stdout.flush()
        
        print(f"{Color.GREEN}✅ 方块数据生成完成 ({elapsed:.3f}s){Color.RESET}")
    
    def convert(self, input_image, output_schem, width=None, height=None, selected_blocks=None):
        """转换入口函数"""
        if selected_blocks is None:
            selected_blocks = []
            
        print(f"{Color.CYAN}🚀 开始转换流程...{Color.RESET}")
        total_start_time = time.time()
        
        # 加载方块映射
        if not self.load_block_mappings_fast(selected_blocks):
            return None
            
        try:
            # 加载图片
            self.load_image_ultrafast(input_image)
            
            # 设置尺寸
            if width is None or height is None:
                self.set_size(self.original_width, self.original_height)
            else:
                # 计算最佳比例
                orig_ratio = self.original_width / self.original_height
                target_ratio = width / height
                
                if abs(orig_ratio - target_ratio) < 0.05:
                    self.set_size(width, height)
                else:
                    if orig_ratio > target_ratio:
                        best_width = width
                        best_height = int(width / orig_ratio)
                    else:
                        best_height = height
                        best_width = int(height * orig_ratio)
                    
                    print(f"{Color.YELLOW}⚠️  建议尺寸: {best_width}x{best_height} (保持原图比例){Color.RESET}")
                    self.set_size(best_width, best_height)
            
            # 选择生成算法
            total_pixels = self.width * self.height
            
            if total_pixels > 100000 and self.cpu_count > 1:
                print(f"{Color.CYAN}⚡ 使用多线程模式{Color.RESET}")
                self.generate_block_data_threaded()
            else:
                print(f"{Color.CYAN}⚡ 使用单线程极速模式{Color.RESET}")
                self.generate_block_data_ultrafast()
            
            # 保存文件
            result = self.save_schem_fast(output_schem)
            
            total_time = time.time() - total_start_time
            print(f"{Color.GREEN}✨ 总转换时间: {total_time:.2f}秒 ({total_pixels/total_time:.0f}像素/秒){Color.RESET}")
            
            return result
            
        except Exception as e:
            print(f"{Color.RED}❌ 转换过程中发生错误: {e}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_schem_fast(self, output_path):
        """快速保存schem文件"""
        print(f"{Color.CYAN}💾 正在保存schem文件...{Color.RESET}")
        start_time = time.time()
        
        if not output_path.lower().endswith('.schem'):
            output_path += '.schem'
        
        # 创建调色板
        palette_dict = {}
        for idx, block_name in enumerate(self.block_palette):
            palette_dict[block_name] = Int(idx)
        
        # 创建schem结构
        schem_data = Compound()
        schem_data["Version"] = Int(2)
        schem_data["DataVersion"] = Int(3100)
        schem_data["Width"] = Short(self.width)
        schem_data["Height"] = Short(self.depth)
        schem_data["Length"] = Short(self.height)
        schem_data["Offset"] = List[Int]([Int(0), Int(0), Int(0)])
        schem_data["Palette"] = Compound(palette_dict)
        schem_data["BlockData"] = nbtlib.ByteArray(self.block_data.flatten(order='C').tolist())
        schem_data["BlockEntities"] = List[Compound]([])
        
        # 保存文件
        nbt_file = nbtlib.File(schem_data)
        nbt_file.save(output_path, gzipped=True)
        
        save_time = time.time() - start_time
        print(f"{Color.GREEN}✅ schem文件保存完成: {output_path} ({save_time:.3f}s){Color.RESET}")
        return self.width, self.height, self.width * self.height


# 兼容性别名
Converter = schemConverter