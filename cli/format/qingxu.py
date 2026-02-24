import json
import os
import numpy as np
from PIL import Image
import time
from pathlib import Path
import sys
from typing import Dict, List, Union, TypedDict
from enum import Enum
from io import BytesIO, StringIO, TextIOBase, IOBase

class Color(Enum):
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

class FormatError(Exception):
    """格式错误异常"""
    pass

class BLOCK(TypedDict):
    """方块数据结构定义"""
    Name: str
    X: int
    Y: int
    Z: int

class QingXu_V1:
    """
    由 情绪 开发的结构文件对象
    -----------------------
    * 以 .json 为后缀的json格式文件
    * 格式：{ "0": "{\"0\":\"{\\\"Name\\\":\\\"grass\\\",\\\"X\\\":0,\\\"Y\\\":0,\\\"Z\\\":0}\"", "totalBlocks": 1}
    ----------------------------------------
    * 可用属性 chunks : 区块储存列表
    -----------------------
    * 可用类方法 from_buffer : 通过路径、字节数字 或 流式缓冲区 生成对象
    * 可用方法 save_as : 通过路径 或 流式缓冲区 保存对象数据
    """

    def __init__(self):
        self.chunks: List[List[BLOCK]] = TypeCheckList().setChecker(list)

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
        """检查数据结构完整性"""
        for chunk in self.chunks:
            for block in chunk:
                if not isinstance(block, dict):
                    raise Exception("方块数据不为dict参数")
                if not isinstance(block.get("Name", None), str):
                    raise Exception("方块数据缺少或存在错误 Name 参数")
                if not isinstance(block.get("X", None), int):
                    raise Exception("方块数据缺少或存在错误 X 参数")
                if not isinstance(block.get("Y", None), int):
                    raise Exception("方块数据缺少或存在错误 Y 参数")
                if not isinstance(block.get("Z", None), int):
                    raise Exception("方块数据缺少或存在错误 Z 参数")

    def get_volume(self):
        """获取结构体积范围"""
        if not self.chunks or not any(self.chunks):
            return [0, 0, 0], [0, 0, 0]
        
        origin_min, origin_max, str1 = [0, 0, 0], [0, 0, 0], ["X", "Y", "Z"]
        
        # 初始化第一个方块的位置
        first_block = None
        for chunk in self.chunks:
            if chunk:
                first_block = chunk[0]
                break
        
        if not first_block:
            return [0, 0, 0], [0, 0, 0]
        
        for i in range(3):
            origin_min[i] = first_block[str1[i]]
            origin_max[i] = first_block[str1[i]]
        
        # 遍历所有方块更新最小最大值
        for chunk in self.chunks:
            for block in chunk:
                for i in range(3):
                    origin_min[i] = min(origin_min[i], block[str1[i]])
                    origin_max[i] = max(origin_max[i], block[str1[i]])

        return origin_min, origin_max

    @classmethod
    def from_buffer(cls, buffer: Union[str, IOBase, BytesIO, StringIO]):
        """从缓冲区加载结构"""
        if isinstance(buffer, str):
            _file = open(buffer, "rb")
        elif isinstance(buffer, bytes):
            _file = BytesIO(buffer)
        else:
            _file = buffer
        
        Json1 = json.load(fp=_file)

        if "totalBlocks" not in Json1:
            raise FormatError("文件缺少totalBlocks参数")

        StructureObject = cls()
        
        total_blocks = Json1.get("totalBlocks", 0)
        for i in range(total_blocks):
            chunk_data = Json1.get(f"{i}", '{"totalPoints":0}')
            try:
                chunk = json.loads(chunk_data)
            except:
                chunk = {"totalPoints": 0}
                
            if not chunk:
                continue
                
            StructureObject.chunks.append([])
            total_points = chunk.get("totalPoints", 0)
            
            for j in range(total_points):
                block_data = chunk.get(f"{j}", None)
                if not block_data:
                    continue
                    
                try:
                    block = json.loads(block_data)
                    if isinstance(block, dict) and "Name" in block:
                        StructureObject.chunks[-1].append(block)
                except:
                    continue

        return StructureObject

    def save_as(self, buffer: Union[str, IOBase, StringIO]):
        """保存结构到缓冲区"""
        self.error_check()
        
        Json1 = {"totalBlocks": len(self.chunks)}
        
        for i, chunk in enumerate(self.chunks):
            if not chunk:
                continue
                
            # 计算区块边界
            minX = min(block["X"] for block in chunk)
            maxX = max(block["X"] for block in chunk)
            minY = min(block["Y"] for block in chunk)
            maxY = max(block["Y"] for block in chunk)
            minZ = min(block["Z"] for block in chunk)
            maxZ = max(block["Z"] for block in chunk)
            
            Cache = {
                "totalPoints": len(chunk),
                "centerX": (minX + maxX) // 2 if chunk else 0,
                "centerY": (minY + maxY) // 2 if chunk else 0,
                "centerZ": (minZ + maxZ) // 2 if chunk else 0
            }
            
            for j, block in enumerate(chunk):
                Cache[f"{j}"] = json.dumps(block, separators=(',', ':'))
            
            Json1[f"{i}"] = json.dumps(Cache, separators=(',', ':'))

        if isinstance(buffer, str):
            base_path = os.path.realpath(os.path.join(buffer, os.pardir))
            os.makedirs(base_path, exist_ok=True)
            _file = open(buffer, "w+", encoding="utf-8")
        else:
            _file = buffer

        if not isinstance(_file, TextIOBase):
            raise TypeError("buffer 参数需要文本缓冲区类型")
        
        json.dump(Json1, _file, separators=(',', ':'))

    @classmethod
    def is_this_file(cls, data, data_type: str):
        """判断是否为QingXu格式文件"""
        if data_type != "json":
            return False
            
        if not isinstance(data, dict):
            return False
            
        if "totalBlocks" not in data:
            return False
            
        # 检查首个区块格式
        first_chunk_key = "0"
        if first_chunk_key not in data:
            return False
            
        try:
            first_chunk = json.loads(data[first_chunk_key])
            if not isinstance(first_chunk, dict):
                return False
                
            if "totalPoints" not in first_chunk:
                return False
                
            # 检查第一个方块
            first_block_key = "0"
            if first_block_key not in first_chunk:
                return True  # 可能是空区块
                
            block = json.loads(first_chunk[first_block_key])
            return all(key in block for key in ["Name", "X", "Y", "Z"])
            
        except Exception:
            return False


class QingxuConverter:
    """QingXu 格式转换器"""
    
    def __init__(self, config=None):
        self.config = config
        self.language_manager = None
        if config and hasattr(config, 'get_language_manager'):
            self.language_manager = config.get_language_manager()
    
    def get_text(self, key, default=None):
        """获取翻译文本"""
        if self.language_manager:
            return self.language_manager.get(key, default)
        return default if default is not None else key
    
    def convert(self, input_image, output_file, width=None, height=None, selected_blocks=None):
        """将图片转换为 QingXu 格式结构文件"""
        try:
            use_color = False
            if self.config and hasattr(self.config, 'getboolean'):
                use_color = self.config.getboolean('ui', 'colored_output', True)
            
            # 读取图片
            img = Image.open(input_image)
            
            # 如果指定了尺寸，调整图片大小
            if width and height:
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            
            img_width, img_height = img.size
            
            # 将图片转换为RGB模式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 获取像素数据
            pixels = np.array(img)
            
            if use_color:
                print(f"{Color.CYAN.value}📊 {self.get_text('stats.image_size', '图片尺寸')}: {img_width} x {img_height}{Color.RESET.value}")
                print(f"{Color.CYAN.value}🎨 {self.get_text('stats.start_conversion', '开始转换像素到方块...')}{Color.RESET.value}")
            else:
                print(f"📊 {self.get_text('stats.image_size', '图片尺寸')}: {img_width} x {img_height}")
                print(f"🎨 {self.get_text('stats.start_conversion', '开始转换像素到方块...')}")
            
            # 创建QingXu结构对象
            structure = QingXu_V1()
            
            # 加载选中的方块映射
            block_mappings = self.load_block_mappings(selected_blocks)
            
            # 进度显示
            total_pixels = img_width * img_height
            processed = 0
            last_progress = 0
            
            # 创建区块（每个区块最多2048个方块，减少内存使用）
            chunk = []
            chunks_created = 0
            
            for y in range(img_height):
                for x in range(img_width):
                    # 获取像素颜色
                    r, g, b = pixels[y, x]
                    
                    # 找到最接近的颜色映射
                    best_block = self.find_closest_color(r, g, b, block_mappings)
                    
                    if best_block:
                        # 创建方块数据
                        block_data = {
                            "Name": best_block[0],
                            "X": x,
                            "Y": 0,  # QingXu格式通常使用平面坐标，Y设为0
                            "Z": y
                        }
                        
                        chunk.append(block_data)
                        
                        # 如果区块已满，添加到结构中并创建新区块
                        if len(chunk) >= 2048:  # 减少每个区块的方块数，避免性能问题
                            structure.chunks.append(chunk)
                            chunk = []
                            chunks_created += 1
                    
                    processed += 1
                    
                    # 显示进度
                    progress = (processed / total_pixels) * 100
                    if int(progress) > last_progress:
                        last_progress = int(progress)
                        if use_color:
                            sys.stdout.write(f"\r{Color.YELLOW.value}📊 {self.get_text('conversion.progress', '转换进度')}: {progress:.1f}%{Color.RESET.value}")
                        else:
                            sys.stdout.write(f"\r📊 {self.get_text('conversion.progress', '转换进度')}: {progress:.1f}%")
                        sys.stdout.flush()
            
            # 添加最后一个区块（如果有剩余方块）
            if chunk:
                structure.chunks.append(chunk)
                chunks_created += 1
            
            print(f"\r📊 {self.get_text('conversion.progress', '转换进度')}: 100.0%")
            
            # 计算结构尺寸和总方块数
            total_blocks = 0
            structure_width = 0
            structure_length = 0
            
            if structure.chunks:
                # 计算总方块数
                for chunk in structure.chunks:
                    total_blocks += len(chunk)
                
                if total_blocks > 0:
                    # 收集所有方块的位置信息
                    all_x = []
                    all_z = []
                    for chunk in structure.chunks:
                        for block in chunk:
                            all_x.append(block["X"])
                            all_z.append(block["Z"])
                    
                    if all_x and all_z:
                        min_x = min(all_x)
                        max_x = max(all_x)
                        min_z = min(all_z)
                        max_z = max(all_z)
                        
                        structure_width = max_x - min_x + 1
                        structure_length = max_z - min_z + 1
                    else:
                        structure_width = 0
                        structure_length = 0
                else:
                    structure_width = 0
                    structure_length = 0
            else:
                total_blocks = 0
                structure_width = 0
                structure_length = 0
            
            structure_height = 1  # QingXu格式通常是平面结构
            
            if use_color:
                print(f"{Color.GREEN.value}📦 {self.get_text('stats.chunks_created', '创建区块数')}: {chunks_created}{Color.RESET.value}")
                print(f"{Color.GREEN.value}🧱 {self.get_text('stats.total_blocks', '总方块数')}: {total_blocks}{Color.RESET.value}")
            else:
                print(f"📦 {self.get_text('stats.chunks_created', '创建区块数')}: {chunks_created}")
                print(f"🧱 {self.get_text('stats.total_blocks', '总方块数')}: {total_blocks}")
            
            # 保存为QingXu格式
            if use_color:
                print(f"{Color.BLUE.value}💾 {self.get_text('stats.saving_file', '正在保存文件...')}{Color.RESET.value}")
            else:
                print(f"💾 {self.get_text('stats.saving_file', '正在保存文件...')}")
            
            structure.save_as(output_file)
            
            # 确保返回正确的值
            return structure_width, structure_height, total_blocks
            
        except Exception as e:
            if use_color:
                print(f"{Color.RED.value}❌ {self.get_text('error.conversion_failed', '转换失败')}: {e}{Color.RESET.value}")
            else:
                print(f"❌ {self.get_text('error.conversion_failed', '转换失败')}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def load_block_mappings(self, selected_blocks):
        """加载选中的方块映射"""
        block_mappings = {}
        block_dir = Path("block")
        
        if not selected_blocks:
            # 默认使用羊毛和混凝土
            selected_blocks = ["wool", "concrete"]
        
        for block_type in selected_blocks:
            block_file = block_dir / f"{block_type}.json"
            
            if not block_file.exists():
                print(f"⚠️  {self.get_text('warning.block_file_not_found', '方块文件不存在')}: {block_file}")
                continue
            
            try:
                with open(block_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # 尝试解析JSON
                    try:
                        mappings = json.loads(content)
                    except json.JSONDecodeError:
                        # 如果文件包含注释，尝试删除注释后解析
                        lines = content.split('\n')
                        json_lines = []
                        for line in lines:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                json_lines.append(line)
                        json_content = '\n'.join(json_lines)
                        mappings = json.loads(json_content)
                
                # 处理映射数据
                for color_str, block_info in mappings.items():
                    # 跳过注释行
                    if color_str.startswith('#'):
                        continue
                    
                    # 解析颜色字符串
                    if color_str.startswith('(') and color_str.endswith(')'):
                        color_str = color_str[1:-1]
                        try:
                            r, g, b = map(int, color_str.split(','))
                            color_key = (r, g, b)
                            
                            if isinstance(block_info, list) and len(block_info) >= 1:
                                block_mappings[color_key] = block_info
                        except:
                            continue
            
            except Exception as e:
                print(f"⚠️  {self.get_text('warning.failed_load_block', '加载方块映射失败')} {block_type}: {e}")
        
        if not block_mappings:
            print(f"⚠️  {self.get_text('warning.no_block_mappings', '没有找到可用的方块映射')}")
        return block_mappings
    
    def find_closest_color(self, r, g, b, block_mappings):
        """找到最接近的颜色映射，修复数值溢出问题"""
        if not block_mappings:
            return ["minecraft:stone", 0]
        
        min_distance = float('inf')
        closest_block = None
        
        for (cr, cg, cb), block_info in block_mappings.items():
            # 计算颜色距离，使用更安全的计算方法避免溢出
            # 将值转换为浮点数以避免溢出
            r_f, g_f, b_f = float(r), float(g), float(b)
            cr_f, cg_f, cb_f = float(cr), float(cg), float(cb)
            
            # 计算欧几里得距离的平方，避免开方运算
            distance_sq = (r_f - cr_f) ** 2 + (g_f - cg_f) ** 2 + (b_f - cb_f) ** 2
            
            if distance_sq < min_distance:
                min_distance = distance_sq
                closest_block = block_info
        
        return closest_block


# 兼容性函数
def get_converter_class():
    """获取转换器类"""
    return QingxuConverter


# 直接导出转换器类
Converter = QingxuConverter
QingXuConverter = QingxuConverter