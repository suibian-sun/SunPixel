#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#name[名称]:Minecraft像素画生成器

import numpy as np
import png  # 使用pypng库处理PNG
from PIL import Image  # 使用PIL处理JPG
import nbtlib
from nbtlib.tag import Byte, Short, Int, Long, Float, Double, String, List, Compound
import os
import time
import math

class ImageToSchem:
    def __init__(self):
        # 1.21版本方块ID映射
        self.color_to_block = {
            # 羊毛系列 (1.21版本)
            (20, 21, 25): ("minecraft:white_wool", 0),       # 黑色羊毛
            (233, 236, 239): ("minecraft:white_wool", 0),    # 白色羊毛
            (160, 39, 34): ("minecraft:red_wool", 0),        # 红色羊毛
            (103, 117, 53): ("minecraft:green_wool", 0),     # 绿色羊毛
            (53, 57, 157): ("minecraft:blue_wool", 0),       # 蓝色羊毛
            (247, 233, 163): ("minecraft:yellow_wool", 0),   # 黄色羊毛
            (240, 118, 19): ("minecraft:orange_wool", 0),    # 橙色羊毛
            (121, 42, 172): ("minecraft:purple_wool", 0),    # 紫色羊毛
            (114, 71, 40): ("minecraft:brown_wool", 0),      # 棕色羊毛
            (62, 68, 71): ("minecraft:gray_wool", 0),        # 灰色羊毛
            (142, 142, 134): ("minecraft:light_gray_wool", 0), # 淡灰色羊毛
            (21, 137, 145): ("minecraft:cyan_wool", 0),      # 青色羊毛
            (189, 69, 180): ("minecraft:magenta_wool", 0),   # 品红色羊毛
            (84, 109, 27): ("minecraft:lime_wool", 0),       # 青柠色羊毛
            (58, 175, 217): ("minecraft:light_blue_wool", 0), # 淡蓝色羊毛
            (216, 129, 152): ("minecraft:pink_wool", 0),     # 粉红色羊毛
            
            # 混凝土系列 (1.21版本)
            (20, 21, 25): ("minecraft:black_concrete", 0),      # 黑色混凝土
            (233, 236, 239): ("minecraft:white_concrete", 0),   # 白色混凝土
            (160, 39, 34): ("minecraft:red_concrete", 0),      # 红色混凝土
            (103, 117, 53): ("minecraft:green_concrete", 0),    # 绿色混凝土
            (53, 57, 157): ("minecraft:blue_concrete", 0),     # 蓝色混凝土
            (247, 233, 163): ("minecraft:yellow_concrete", 0), # 黄色混凝土
            (240, 118, 19): ("minecraft:orange_concrete", 0),  # 橙色混凝土
            (121, 42, 172): ("minecraft:purple_concrete", 0),  # 紫色混凝土
            (114, 71, 40): ("minecraft:brown_concrete", 0),    # 棕色混凝土
            (62, 68, 71): ("minecraft:gray_concrete", 0),     # 灰色混凝土
            (142, 142, 134): ("minecraft:light_gray_concrete", 0), # 淡灰色混凝土
            (21, 137, 145): ("minecraft:cyan_concrete", 0),    # 青色混凝土
            (189, 69, 180): ("minecraft:magenta_concrete", 0), # 品红色混凝土
            (84, 109, 27): ("minecraft:lime_concrete", 0),     # 青柠色混凝土
            (58, 175, 217): ("minecraft:light_blue_concrete", 0), # 淡蓝色混凝土
            (216, 129, 152): ("minecraft:pink_concrete", 0),   # 粉红色混凝土
        }
        
        # 方块ID列表
        self.block_palette = []
        # 方块数据数组
        self.block_data = []
        # 图片尺寸
        self.width = 0
        self.height = 0
        # 固定为单层结构
        self.depth = 1
        
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
        
        for target_color in self.color_to_block:
            # 使用感知颜色距离算法
            distance = self.color_distance((r, g, b), target_color)
            if distance < min_distance:
                min_distance = distance
                closest_color = target_color
                
        return self.color_to_block.get(closest_color, ("minecraft:white_concrete", 0))
    
    def load_image(self, image_path):
        """加载图片，支持PNG和JPG格式"""
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
            
    def generate_schem(self):
        """生成schem数据结构"""
        # 初始化方块调色板
        self.block_palette = list(set([block[0] for block in self.color_to_block.values()]))
        
        # 创建方块数据数组 (二维数组: height × width)
        self.block_data = np.zeros((self.depth, self.height, self.width), dtype=int)
        self.block_data_values = np.zeros((self.depth, self.height, self.width), dtype=int)
        
        # 计算缩放比例
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
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
                block_index = self.block_palette.index(block_name)
                
                # 单层结构，只在z=0位置放置方块
                self.block_data[0, y, x] = block_index
                self.block_data_values[0, y, x] = block_data
        
    def save_schem(self, output_path):
        """保存为Sponge格式的.schem文件"""
        # 确保输出文件后缀正确
        if not output_path.lower().endswith('.schem'):
            output_path += '.schem'
        
        # 创建NBT数据结构
        schematic = Compound({
            "Version": Int(2),
            "DataVersion": Int(3100),  # 1.21版本
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
            "BlockEntities": List[Compound]([]),
            
            # 元数据
            "Metadata": Compound({
                "Author": String("Image to Schematic Converter"),
                "Name": String(os.path.basename(output_path).replace('.schem', '')),
                "Date": Long(int(time.time() * 1000)),  # 毫秒时间戳
                "Description": String("Generated from image")
            })
        })
        
        # 保存为.schem文件
        nbt_file = nbtlib.File(schematic)
        nbt_file.save(output_path, gzipped=True)
        
        # 返回转换统计信息
        return self.width, self.height, self.width * self.height
        
    def convert(self, input_image, output_schem, width=None, height=None):
        """转换入口函数"""
        self.load_image(input_image)
        
        # 如果没有指定尺寸，则使用原始图片尺寸
        if width is None or height is None:
            self.set_size(self.original_width, self.original_height)
        else:
            # 计算并建议最佳比例
            best_width, best_height = self.calculate_best_ratio(width, height)
            
            # 如果建议的尺寸与用户输入不同，询问用户
            if best_width != width or best_height != height:
                print(f"\n⚠️ 建议使用保持比例的最佳尺寸: {best_width}x{best_height} (原图比例 {self.original_width}:{self.original_height})")
                choice = input("是否使用建议尺寸? (y/n): ").strip().lower()
                if choice == 'y':
                    self.set_size(best_width, best_height)
                else:
                    self.set_size(width, height)
            else:
                self.set_size(width, height)
            
        self.generate_schem()
        return self.save_schem(output_schem)


def get_user_input():
    """获取用户输入"""
    print("\n🌈 Minecraft 像素画生成器 Beta-0.0.4")
    print("="*50)
    
    # 获取输入文件路径
    while True:
        input_path = input("\n请输入图片路径 (PNG或JPG): ").strip()
        if not os.path.exists(input_path):
            print(f"错误: 文件 '{input_path}' 不存在")
            continue
            
        ext = os.path.splitext(input_path)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg'):
            print("错误: 只支持PNG和JPG格式的图片")
            continue
            
        try:
            # 尝试打开图片以验证有效性
            if ext == '.png':
                with open(input_path, 'rb') as f:
                    reader = png.Reader(file=f)
                    width, height, _, _ = reader.read()
            else:  # JPG
                img = Image.open(input_path)
                width, height = img.size
                
            if width == 0 or height == 0:
                print("错误: 图片尺寸无效")
                continue
            break
        except Exception as e:
            print(f"无法打开文件: {e}，请重新输入")
    
    # 获取输出文件路径
    while True:
        output_path = input("\n请输入输出.schem文件路径(例如: output.schem): ").strip()
        if not output_path:
            print("错误: 输出路径不能为空")
            continue
            
        # 自动添加扩展名
        if not output_path.lower().endswith('.schem'):
            output_path += '.schem'
            
        try:
            # 检查目录是否存在
            output_dir = os.path.dirname(output_path) or '.'
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            break
        except Exception as e:
            print(f"无法创建输出目录: {e}，请重新输入")
    
    # 获取生成尺寸
    while True:
        size_input = input("\n请输入生成尺寸(格式: 宽x高，例如 64x64，留空则使用原图尺寸): ").strip()
        if not size_input:
            width, height = None, None
            break
        
        try:
            if 'x' in size_input:
                width, height = map(int, size_input.lower().split('x'))
            elif '×' in size_input:  # 处理中文乘号
                width, height = map(int, size_input.lower().split('×'))
            else:
                print("请输入有效的尺寸格式，例如 64x64")
                continue
                
            if width <= 0 or height <= 0:
                print("尺寸必须大于0")
                continue
            break
        except ValueError:
            print("请输入有效的尺寸格式，例如 64x64")
    
    return input_path, output_path, width, height


# 主程序
if __name__ == "__main__":
    try:
        # 获取用户输入
        input_image, output_schem, width, height = get_user_input()
        
        # 创建转换器并执行转换
        converter = ImageToSchem()
        print("\n开始转换...")
        start_time = time.time()
        
        # 执行转换并获取统计信息
        schem_width, schem_height, block_count = converter.convert(input_image, output_schem, width, height)
        elapsed = time.time() - start_time
        
        # 显示转换统计信息
        print(f"\n✅ 转换成功完成! 耗时: {elapsed:.2f}秒")
        print("="*50)
        print(f"生成结构尺寸: {schem_width} × {schem_height} 方块")
        print(f"总方块数量: {block_count} 个")
        print(f"输出文件: {os.path.abspath(output_schem)}")
        print("="*50)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
    finally:
        input("\n按Enter键退出...")