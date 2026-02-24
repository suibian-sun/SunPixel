import struct
import brotli
import io
import os
import math
import json
from typing import Dict, List, Tuple, Any, Optional
import sys

# 颜色输出类
class Color:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'

# 定义结构体类
class BlockPos:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z
    
    def X(self):
        return self.x
    
    def Y(self):
        return self.y
    
    def Z(self):
        return self.z
    
    def __repr__(self):
        return f"BlockPos({self.x}, {self.y}, {self.z})"

class Size:
    def __init__(self, width=0, height=0, length=0):
        self.width = width
        self.height = height
        self.length = length
    
    def __repr__(self):
        return f"Size({self.width}, {self.height}, {self.length})"

class Offset:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z
    
    def X(self):
        return self.x
    
    def Y(self):
        return self.y
    
    def Z(self):
        return self.z
    
    def __repr__(self):
        return f"Offset({self.x}, {self.y}, {self.z})"

class ChunkPos:
    def __init__(self, x=0, z=0):
        self.x = x
        self.z = z
    
    def __repr__(self):
        return f"ChunkPos({self.x}, {self.z})"

# 命令类定义
class Command:
    def __init__(self):
        self.id = 0

class AddXValue(Command):
    def __init__(self):
        super().__init__()
        self.id = 0x01

class AddYValue(Command):
    def __init__(self):
        super().__init__()
        self.id = 0x02

class AddZValue(Command):
    def __init__(self):
        super().__init__()
        self.id = 0x03

class SubtractXValue(Command):
    def __init__(self):
        super().__init__()
        self.id = 0x05

class SubtractYValue(Command):
    def __init__(self):
        super().__init__()
        self.id = 0x06

class SubtractZValue(Command):
    def __init__(self):
        super().__init__()
        self.id = 0x07

class AddInt8XValue(Command):
    def __init__(self, value):
        super().__init__()
        self.id = 0x08
        self.value = value

class AddInt8YValue(Command):
    def __init__(self, value):
        super().__init__()
        self.id = 0x09
        self.value = value

class AddInt8ZValue(Command):
    def __init__(self, value):
        super().__init__()
        self.id = 0x0A
        self.value = value

class AddInt16XValue(Command):
    def __init__(self, value):
        super().__init__()
        self.id = 0x0B
        self.value = value

class AddInt16YValue(Command):
    def __init__(self, value):
        super().__init__()
        self.id = 0x0C
        self.value = value

class AddInt16ZValue(Command):
    def __init__(self, value):
        super().__init__()
        self.id = 0x0D
        self.value = value

class PlaceBlock(Command):
    def __init__(self, block_constant_string_id, block_data):
        super().__init__()
        self.id = 0x13
        self.block_constant_string_id = block_constant_string_id
        self.block_data = block_data

class PlaceBlockWithBlockStates(Command):
    def __init__(self, block_constant_string_id, block_states_constant_string_id):
        super().__init__()
        self.id = 0x14
        self.block_constant_string_id = block_constant_string_id
        self.block_states_constant_string_id = block_states_constant_string_id

class CreateConstantString(Command):
    def __init__(self, constant_string):
        super().__init__()
        self.id = 0x20
        self.constant_string = constant_string

class UseRuntimeIDPool(Command):
    def __init__(self, pool_id):
        super().__init__()
        self.id = 0x21
        self.pool_id = pool_id

class Terminate(Command):
    def __init__(self):
        super().__init__()
        self.id = 0x22

# 错误类
class ErrInvalidFile(Exception):
    pass

# BDX运行时块池
BDXRuntimeBlockPools = {
    0: [0, 1, 2, 3, 4, 5],  # 基础方块池
}

# 模拟block包
class Block:
    AirRuntimeID = 0
    
    @staticmethod
    def RuntimeIDToState(runtime_id):
        """简化实现"""
        if runtime_id == 0:
            return "minecraft:air", {}, True
        elif runtime_id == 1:
            return "minecraft:stone", {"stone_type": "stone"}, True
        elif runtime_id == 2:
            return "minecraft:grass", {}, True
        elif runtime_id == 3:
            return "minecraft:dirt", {}, True
        else:
            return "minecraft:stone", {"stone_type": "stone"}, True
    
    @staticmethod
    def StateToRuntimeID(name, properties):
        """简化实现"""
        if name == "minecraft:air":
            return 0, True
        elif name == "minecraft:stone":
            return 1, True
        elif name == "minecraft:grass":
            return 2, True
        elif name == "minecraft:dirt":
            return 3, True
        else:
            return 1, True

# 命令读写工具类
class CommandIO:
    @staticmethod
    def read_command(reader):
        """从读取器读取命令"""
        try:
            cmd_id_bytes = reader.read(1)
            if not cmd_id_bytes:
                return None  # EOF
            
            cmd_id = struct.unpack('B', cmd_id_bytes)[0]
            
            # 根据命令ID创建相应的命令对象
            if cmd_id == 0x01:
                return AddXValue()
            elif cmd_id == 0x02:
                return AddYValue()
            elif cmd_id == 0x03:
                return AddZValue()
            elif cmd_id == 0x05:
                return SubtractXValue()
            elif cmd_id == 0x06:
                return SubtractYValue()
            elif cmd_id == 0x07:
                return SubtractZValue()
            elif cmd_id == 0x08:
                value = struct.unpack('b', reader.read(1))[0]
                return AddInt8XValue(value)
            elif cmd_id == 0x09:
                value = struct.unpack('b', reader.read(1))[0]
                return AddInt8YValue(value)
            elif cmd_id == 0x0A:
                value = struct.unpack('b', reader.read(1))[0]
                return AddInt8ZValue(value)
            elif cmd_id == 0x0B:
                value = struct.unpack('<h', reader.read(2))[0]
                return AddInt16XValue(value)
            elif cmd_id == 0x0C:
                value = struct.unpack('<h', reader.read(2))[0]
                return AddInt16YValue(value)
            elif cmd_id == 0x0D:
                value = struct.unpack('<h', reader.read(2))[0]
                return AddInt16ZValue(value)
            elif cmd_id == 0x13:
                block_constant_string_id = struct.unpack('<H', reader.read(2))[0]
                block_data = struct.unpack('<H', reader.read(2))[0]
                return PlaceBlock(block_constant_string_id, block_data)
            elif cmd_id == 0x14:
                block_constant_string_id = struct.unpack('<H', reader.read(2))[0]
                block_states_constant_string_id = struct.unpack('<H', reader.read(2))[0]
                return PlaceBlockWithBlockStates(block_constant_string_id, block_states_constant_string_id)
            elif cmd_id == 0x20:
                string_length = struct.unpack('<H', reader.read(2))[0]
                constant_string = reader.read(string_length).decode('utf-8')
                return CreateConstantString(constant_string)
            elif cmd_id == 0x21:
                pool_id = struct.unpack('B', reader.read(1))[0]
                return UseRuntimeIDPool(pool_id)
            elif cmd_id == 0x22:
                return Terminate()
            else:
                # 跳过未知命令
                print(f"跳过未知命令ID: 0x{cmd_id:02x}")
                return None
        except Exception as e:
            print(f"读取命令时出错: {e}")
            return None
    
    @staticmethod
    def write_command(cmd, writer):
        """写入命令到流"""
        try:
            if isinstance(cmd, AddXValue):
                writer.write(struct.pack('B', 0x01))
            elif isinstance(cmd, AddYValue):
                writer.write(struct.pack('B', 0x02))
            elif isinstance(cmd, AddZValue):
                writer.write(struct.pack('B', 0x03))
            elif isinstance(cmd, SubtractXValue):
                writer.write(struct.pack('B', 0x05))
            elif isinstance(cmd, SubtractYValue):
                writer.write(struct.pack('B', 0x06))
            elif isinstance(cmd, SubtractZValue):
                writer.write(struct.pack('B', 0x07))
            elif isinstance(cmd, AddInt8XValue):
                writer.write(struct.pack('B', 0x08))
                writer.write(struct.pack('b', cmd.value))
            elif isinstance(cmd, AddInt8YValue):
                writer.write(struct.pack('B', 0x09))
                writer.write(struct.pack('b', cmd.value))
            elif isinstance(cmd, AddInt8ZValue):
                writer.write(struct.pack('B', 0x0A))
                writer.write(struct.pack('b', cmd.value))
            elif isinstance(cmd, AddInt16XValue):
                writer.write(struct.pack('B', 0x0B))
                writer.write(struct.pack('<h', cmd.value))
            elif isinstance(cmd, AddInt16YValue):
                writer.write(struct.pack('B', 0x0C))
                writer.write(struct.pack('<h', cmd.value))
            elif isinstance(cmd, AddInt16ZValue):
                writer.write(struct.pack('B', 0x0D))
                writer.write(struct.pack('<h', cmd.value))
            elif isinstance(cmd, PlaceBlock):
                writer.write(struct.pack('B', 0x13))
                writer.write(struct.pack('<H', cmd.block_constant_string_id))
                writer.write(struct.pack('<H', cmd.block_data))
            elif isinstance(cmd, PlaceBlockWithBlockStates):
                writer.write(struct.pack('B', 0x14))
                writer.write(struct.pack('<H', cmd.block_constant_string_id))
                writer.write(struct.pack('<H', cmd.block_states_constant_string_id))
            elif isinstance(cmd, CreateConstantString):
                writer.write(struct.pack('B', 0x20))
                writer.write(struct.pack('<H', len(cmd.constant_string)))
                writer.write(cmd.constant_string.encode('utf-8'))
            elif isinstance(cmd, UseRuntimeIDPool):
                writer.write(struct.pack('B', 0x21))
                writer.write(struct.pack('B', cmd.pool_id))
            elif isinstance(cmd, Terminate):
                writer.write(struct.pack('B', 0x22))
            else:
                raise ValueError(f"未知的命令类型: {type(cmd)}")
        except Exception as e:
            print(f"写入命令时出错: {e}")
            raise

# 主要BDX类
class BDX:
    """BDX格式处理器"""
    
    def __init__(self):
        self.file = None
        self.size = Size()
        self.originalSize = Size()
        self.offsetPos = Offset()
        self.minPos = BlockPos()
        self.cmdNum = 0
        self.runtimeBlockPoolID = 0
        self.constantStrings = {}
        self.Author = ""
        self.BlockNBT = {}
    
    def ID(self):
        return 0  # IDBDX
    
    def Name(self):
        return "BDX"
    
    def FromFile(self, file_path):
        """从文件加载BDX"""
        try:
            self.file = open(file_path, 'rb')
            
            self.size = Size()
            self.originalSize = Size()
            self.offsetPos = Offset()
            self.minPos = BlockPos()
            self.constantStrings = {}
            self.BlockNBT = {}
            
            # 解析文件头
            if self.parse_header() is False:
                return False
            
            # 创建Brotli阅读器
            brw = brotli.Decompressor()
            compressed_data = self.file.read()
            decompressed_data = brw.process(compressed_data)
            br_reader = io.BytesIO(decompressed_data)
            
            # 解析元数据
            if self.parse_metadata(br_reader) is False:
                return False
            
            # 解析命令
            if self.parse_commands(br_reader) is False:
                return False
            
            return True
        except Exception as e:
            print(f"{Color.RED}❌ 加载BDX文件失败: {e}{Color.RESET}")
            return False
    
    def parse_header(self):
        """解析文件头"""
        try:
            header = self.file.read(3)
            if header != b'BD@':
                raise ErrInvalidFile("无效的BDX文件头")
            return True
        except Exception as e:
            print(f"{Color.RED}❌ 解析文件头失败: {e}{Color.RESET}")
            return False
    
    def parse_metadata(self, reader):
        """解析元数据"""
        try:
            header = reader.read(3)
            if header != b'BDX':
                raise ErrInvalidFile("无效的BDX元数据")
            
            # 读取作者信息
            author_bytes = b''
            while True:
                byte = reader.read(1)
                if not byte or byte == b'\x00':
                    break
                author_bytes += byte
            self.Author = author_bytes.decode('utf-8', errors='ignore')
            
            # 跳过额外的字节
            reader.read(1)
            
            return True
        except Exception as e:
            print(f"{Color.RED}❌ 解析元数据失败: {e}{Color.RESET}")
            return False
    
    def parse_commands(self, reader):
        """解析命令"""
        try:
            constantStringID = 0
            pos = [0, 0, 0]
            size = [0, 0, 0]
            minPos = [0, 0, 0]
            cmdNum = 0
            
            while True:
                cmd = CommandIO.read_command(reader)
                if cmd is None:
                    break
                
                cmdNum += 1
                
                # 更新位置
                if isinstance(cmd, AddXValue):
                    pos[0] += 1
                elif isinstance(cmd, AddYValue):
                    pos[1] += 1
                elif isinstance(cmd, AddZValue):
                    pos[2] += 1
                elif isinstance(cmd, SubtractXValue):
                    pos[0] -= 1
                elif isinstance(cmd, SubtractYValue):
                    pos[1] -= 1
                elif isinstance(cmd, SubtractZValue):
                    pos[2] -= 1
                elif isinstance(cmd, AddInt8XValue):
                    pos[0] += cmd.value
                elif isinstance(cmd, AddInt8YValue):
                    pos[1] += cmd.value
                elif isinstance(cmd, AddInt8ZValue):
                    pos[2] += cmd.value
                elif isinstance(cmd, AddInt16XValue):
                    pos[0] += cmd.value
                elif isinstance(cmd, AddInt16YValue):
                    pos[1] += cmd.value
                elif isinstance(cmd, AddInt16ZValue):
                    pos[2] += cmd.value
                
                if isinstance(cmd, CreateConstantString):
                    self.constantStrings[constantStringID] = cmd.constant_string
                    constantStringID += 1
                    continue
                elif isinstance(cmd, UseRuntimeIDPool):
                    self.runtimeBlockPoolID = cmd.pool_id
                    continue
                elif isinstance(cmd, Terminate):
                    break
                
                # 更新尺寸
                if pos[0] > size[0]:
                    size[0] = pos[0]
                if pos[1] > size[1]:
                    size[1] = pos[1]
                if pos[2] > size[2]:
                    size[2] = pos[2]
                if pos[0] < minPos[0]:
                    minPos[0] = pos[0]
                if pos[1] < minPos[1]:
                    minPos[1] = pos[1]
                if pos[2] < minPos[2]:
                    minPos[2] = pos[2]
                
                if isinstance(cmd, Terminate):
                    break
            
            self.minPos = BlockPos(minPos[0], minPos[1], minPos[2])
            self.cmdNum = cmdNum
            self.size.width = int(size[0] - minPos[0]) + 1
            self.size.height = int(size[1] - minPos[1]) + 1
            self.size.length = int(size[2] - minPos[2]) + 1
            self.originalSize.width = self.size.width
            self.originalSize.height = self.size.height
            self.originalSize.length = self.size.length
            
            return True
        except Exception as e:
            print(f"{Color.RED}❌ 解析命令失败: {e}{Color.RESET}")
            return False
    
    def GetOffsetPos(self):
        return self.offsetPos
    
    def SetOffsetPos(self, offset):
        self.offsetPos = offset
        self.size.width = self.originalSize.width + int(abs(offset.X()))
        self.size.length = self.originalSize.length + int(abs(offset.Z()))
        self.size.height = self.originalSize.height + int(abs(offset.Y()))
    
    def GetSize(self):
        return self.size
    
    def Close(self):
        """关闭文件"""
        if self.file:
            self.file.close()
        return True

# BdxConverter类（用于图像转换）
class BdxConverter:
    """BDX格式转换器"""
    def __init__(self, config, language=None):
        self.config = config
        self.language = language
        self.color_to_block = {}
        self.block_palette = {}
        self.constant_strings = {}
        self.next_string_id = 0
        self.width = 0
        self.height = 0
        self.depth = 1
        self.pixels = None
        self.original_width = 0
        self.original_height = 0
        self.block_data = None
        self.blocks = []
        
    def load_block_mappings(self, selected_blocks):
        """从block目录加载选中的方块映射"""
        self.color_to_block = {}
        from pathlib import Path
        
        block_dir = Path("block")
        
        if not block_dir.exists():
            print(f"{Color.RED}❌ block目录不存在!{Color.RESET}")
            return False
            
        for block_file in block_dir.glob("*.json"):
            block_name = block_file.stem
            if block_name in selected_blocks or not selected_blocks:
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
                                    block_name = block_info[0]
                                    aux_value = block_info[1]
                                    try:
                                        aux_int = int(aux_value)
                                    except (ValueError, TypeError):
                                        aux_int = 0
                                    processed_block_data[str(color_key)] = [block_name, aux_int]
                            
                            self.color_to_block.update(processed_block_data)
                            print(f"{Color.GREEN}✅ 已加载: {block_file.stem}{Color.RESET}")
                except Exception as e:
                    print(f"{Color.RED}❌ 加载 {block_file.name} 时出错: {e}{Color.RESET}")
        
        if not self.color_to_block:
            print(f"{Color.RED}❌ 错误: 没有加载任何方块映射!{Color.RESET}")
            return False
            
        print(f"{Color.GREEN}✅ 总共加载 {len(self.color_to_block)} 种颜色映射{Color.RESET}")
        return True
    
    def load_image(self, image_path):
        """加载图片"""
        print(f"{Color.CYAN}🖼️  正在加载图片...{Color.RESET}")
        
        try:
            from PIL import Image
            img = Image.open(image_path)
            img = img.convert('RGB')
            self.original_width, self.original_height = img.size
            self.pixels = img.load()
            
            print(f"{Color.GREEN}✅ 图片加载完成: {self.original_width} × {self.original_height} 像素{Color.RESET}")
            return True
        except ImportError:
            print(f"{Color.RED}❌ 请安装Pillow库: pip install Pillow{Color.RESET}")
            return False
        except Exception as e:
            print(f"{Color.RED}❌ 加载图片失败: {e}{Color.RESET}")
            return False
    
    def set_size(self, width, height):
        """设置生成结构的尺寸"""
        self.width = max(1, width)
        self.height = max(1, height)
        print(f"{Color.CYAN}📐 设置生成尺寸: {self.width} × {self.height} 方块{Color.RESET}")
    
    def color_distance(self, c1, c2):
        """计算颜色距离"""
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
        """找到最接近的颜色"""
        r, g, b = color
        closest_color = None
        min_distance = float('inf')
        
        for color_str, block_info in self.color_to_block.items():
            try:
                # 解析颜色字符串
                if color_str.startswith('(') and color_str.endswith(')'):
                    color_str = color_str[1:-1]
                
                color_values = [int(x.strip()) for x in color_str.split(',')]
                target_color = tuple(color_values[:3])
                
                distance = self.color_distance((r, g, b), target_color)
                if distance < min_distance:
                    min_distance = distance
                    closest_color = color_str
            except:
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
        
        return "minecraft:stone", 0
    
    def generate_block_data(self):
        """生成方块数据"""
        print(f"{Color.CYAN}🔨 正在生成方块数据...{Color.RESET}")
        
        self.blocks = []
        scale_x = self.original_width / self.width
        scale_y = self.original_height / self.height
        
        import time
        start_time = time.time()
        
        for y in range(self.height):
            src_y = int(y * scale_y)
            for x in range(self.width):
                src_x = int(x * scale_x)
                
                # 获取像素颜色
                try:
                    color = self.pixels[src_x, src_y]
                    if isinstance(color, int):
                        color = (color, color, color)
                    elif len(color) == 4:
                        color = color[:3]
                except:
                    color = (255, 255, 255)
                
                # 查找对应的方块
                block_name, block_data = self.find_closest_color(color)
                
                self.blocks.append({
                    "x": x,
                    "y": 0,
                    "z": y,
                    "name": block_name,
                    "aux": block_data
                })
            
            # 显示进度
            if y % 10 == 0 or y == self.height - 1:
                elapsed = time.time() - start_time
                progress = (y + 1) / self.height * 100
                sys.stdout.write(f'\r📊 处理进度: [{y+1}/{self.height}] ({progress:.1f}%) - {elapsed:.1f}s')
                sys.stdout.flush()
        
        print(f"\n{Color.GREEN}✅ 方块数据生成完成{Color.RESET}")
    
    def create_bdx_commands(self):
        """创建BDX命令序列"""
        commands_io = io.BytesIO()
        
        print(f"{Color.CYAN}📝 创建常量字符串...{Color.RESET}")
        
        # 创建常量字符串
        self.constant_strings = {}
        string_id = 0
        
        # 收集所有方块名称
        all_block_names = set()
        for block in self.blocks:
            all_block_names.add(block["name"])
        
        # 创建常量字符串
        for block_name in all_block_names:
            cmd = CreateConstantString(block_name)
            self.constant_strings[string_id] = block_name
            string_id += 1
            CommandIO.write_command(cmd, commands_io)
        
        # 创建空状态字符串
        empty_state = ""
        cmd = CreateConstantString(empty_state)
        self.constant_strings[string_id] = empty_state
        string_id += 1
        CommandIO.write_command(cmd, commands_io)
        
        # 使用运行时ID池
        cmd = UseRuntimeIDPool(0)
        CommandIO.write_command(cmd, commands_io)
        
        print(f"{Color.CYAN}🧱 生成方块命令...{Color.RESET}")
        
        total_blocks = len(self.blocks)
        pos_x, pos_y, pos_z = 0, 0, 0
        
        # 处理方块
        for block in self.blocks:
            x, y, z = block["x"], block["y"], block["z"]
            block_name = block["name"]
            
            # 移动到位置
            move_x = x - pos_x
            move_y = y - pos_y
            move_z = z - pos_z
            
            # 处理X轴移动
            if move_x != 0:
                if move_x == 1:
                    cmd = AddXValue()
                elif move_x == -1:
                    cmd = SubtractXValue()
                elif -128 <= move_x <= 127:
                    cmd = AddInt8XValue(move_x)
                elif -32768 <= move_x <= 32767:
                    cmd = AddInt16XValue(move_x)
                CommandIO.write_command(cmd, commands_io)
            
            # 处理Y轴移动
            if move_y != 0:
                if move_y == 1:
                    cmd = AddYValue()
                elif move_y == -1:
                    cmd = SubtractYValue()
                elif -128 <= move_y <= 127:
                    cmd = AddInt8YValue(move_y)
                elif -32768 <= move_y <= 32767:
                    cmd = AddInt16YValue(move_y)
                CommandIO.write_command(cmd, commands_io)
            
            # 处理Z轴移动
            if move_z != 0:
                if move_z == 1:
                    cmd = AddZValue()
                elif move_z == -1:
                    cmd = SubtractZValue()
                elif -128 <= move_z <= 127:
                    cmd = AddInt8ZValue(move_z)
                elif -32768 <= move_z <= 32767:
                    cmd = AddInt16ZValue(move_z)
                CommandIO.write_command(cmd, commands_io)
            
            pos_x, pos_y, pos_z = x, y, z
            
            # 查找方块名称对应的字符串ID
            block_string_id = None
            empty_string_id = None
            
            for sid, string_value in self.constant_strings.items():
                if string_value == block_name:
                    block_string_id = sid
                elif string_value == "" and empty_string_id is None:
                    empty_string_id = sid
            
            if block_string_id is not None and empty_string_id is not None:
                cmd = PlaceBlockWithBlockStates(block_string_id, empty_string_id)
                CommandIO.write_command(cmd, commands_io)
        
        # 终止命令
        cmd = Terminate()
        CommandIO.write_command(cmd, commands_io)
        
        return commands_io.getvalue()
    
    def save_bdx(self, output_path):
        """保存为BDX格式"""
        print(f"{Color.CYAN}💾 保存BDX文件...{Color.RESET}")
        
        if not output_path.lower().endswith('.bdx'):
            output_path += '.bdx'
        
        try:
            # 生成命令数据
            commands_data = self.create_bdx_commands()
            
            # 创建压缩数据
            compressed_io = io.BytesIO()
            
            # 写入BDX签名
            compressed_io.write(b'BDX')
            
            # 写入作者信息
            author = "ImageConverter"
            compressed_io.write(author.encode('utf-8'))
            compressed_io.write(b'\x00')
            
            # 写入额外的字节
            compressed_io.write(b'\x00')
            
            # 写入命令数据
            compressed_io.write(commands_data)
            
            # 压缩数据
            print(f"{Color.CYAN}📦 压缩数据...{Color.RESET}")
            compressed_data = brotli.compress(compressed_io.getvalue())
            
            # 写入文件
            with open(output_path, 'wb') as f:
                f.write(b'BD@')
                f.write(compressed_data)
            
            # 验证文件
            file_size = os.path.getsize(output_path)
            
            print(f"{Color.GREEN}✅ BDX文件保存完成: {output_path}{Color.RESET}")
            
            # 统计信息
            non_air_blocks = len(self.blocks)
            
            print(f"{Color.CYAN}📊 文件信息:{Color.RESET}")
            print(f"  结构尺寸: {self.width} × {self.depth} × {self.height}")
            print(f"  方块总数: {self.width * self.height * self.depth}")
            print(f"  非空气方块数: {non_air_blocks}")
            print(f"  文件总大小: {file_size} 字节")
            
            return self.width, self.height, non_air_blocks
            
        except Exception as e:
            print(f"{Color.RED}❌ 保存BDX文件失败: {e}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return None
    
    def convert(self, input_image, output_path, width=None, height=None, selected_blocks=None):
        """转换入口函数 - 将图像转换为BDX格式"""
        if selected_blocks is None:
            selected_blocks = []
            
        print(f"{Color.CYAN}🚀 开始BDX转换流程...{Color.RESET}")
        
        if not self.load_block_mappings(selected_blocks):
            return None
            
        try:
            if not self.load_image(input_image):
                return None
            
            if width is None or height is None:
                self.set_size(self.original_width, self.original_height)
            else:
                self.set_size(width, height)
            
            self.generate_block_data()
            
            # 验证数据
            total_blocks = len(self.blocks)
            print(f"{Color.CYAN}📊 数据统计:{Color.RESET}")
            print(f"  总方块数: {total_blocks}")
            
            return self.save_bdx(output_path)
            
        except Exception as e:
            print(f"{Color.RED}❌ 转换失败: {e}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return None

# 兼容性别名
Converter = BdxConverter