import os
import re
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        self.use_color = config.getboolean('ui', 'colored_output', True) if config else True
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

class RunAway:
    """RunAway 官方结构文件对象"""
    def __init__(self):
        self.blocks: list = TypeCheckList().setChecker(dict)

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
        for block in self.blocks:
            if not isinstance(block.get("name", None), str):
                raise Exception("方块数据缺少或存在错误的 name 参数")
            
            # 确保 aux 参数是整数类型
            aux_value = block.get("aux", 0)
            if not isinstance(aux_value, int):
                try:
                    block["aux"] = int(aux_value)
                except (ValueError, TypeError):
                    block["aux"] = 0
                    
            if not isinstance(block.get("x", None), int):
                raise Exception("方块数据存在错误的 x 参数")
            if not isinstance(block.get("y", None), int):
                raise Exception("方块数据存在错误的 y 参数")
            if not isinstance(block.get("z", None), int):
                raise Exception("方块数据存在错误的 z 参数")

            block["aux"] = block.get("aux", 0)

    def save_as(self, buffer):
        self.error_check()

        Json1 = list(self.blocks)

        if isinstance(buffer, str):
            base_path = os.path.realpath(os.path.join(buffer, os.pardir))
            os.makedirs(base_path, exist_ok=True)
            _file = open(buffer, "w+", encoding="utf-8")
        else:
            _file = buffer

        json.dump(Json1, _file, separators=(',', ':'))

class MCFunctionConverter:
    """MCFunction 格式转换器"""
    def __init__(self, config):
        self.config = config
        self.file_path = None
        self.blocks = []
        self.non_air_blocks = 0
        self.size = {"width": 0, "height": 0, "length": 0}
        self.original_size = {"width": 0, "height": 0, "length": 0}
        self.offset_pos = {"x": 0, "y": 0, "z": 0}
        self.min_coords = {"x": 0, "y": 0, "z": 0}
        self.max_coords = {"x": 0, "y": 0, "z": 0}
        
        # 方块映射表
        self.block_name_to_runtime_id = {}
        self.runtime_id_to_block_name = {}
        self.load_block_mappings()
        
        # 语言管理器
        self.language_manager = config.get_language_manager() if hasattr(config, 'get_language_manager') else None
    
    def get_text(self, key, default=None):
        """获取翻译文本"""
        if self.language_manager:
            return self.language_manager.get(key, default)
        return default if default is not None else key
    
    def load_block_mappings(self):
        """加载方块映射表"""
        # 这里可以加载本地的方块映射文件
        # 暂时使用一些基础映射
        self.block_name_to_runtime_id = {
            "minecraft:air": 0,
            "minecraft:stone": 1,
            "minecraft:grass": 2,
            "minecraft:dirt": 3,
            "minecraft:cobblestone": 4,
            "minecraft:planks": 5,
            "minecraft:bedrock": 7,
            "minecraft:water": 8,
            "minecraft:flowing_water": 9,
            "minecraft:lava": 10,
            "minecraft:flowing_lava": 11,
            "minecraft:sand": 12,
            "minecraft:gravel": 13,
            "minecraft:gold_ore": 14,
            "minecraft:iron_ore": 15,
            "minecraft:coal_ore": 16,
            "minecraft:log": 17,
            "minecraft:leaves": 18,
            "minecraft:glass": 20,
            "minecraft:lapis_ore": 21,
            "minecraft:lapis_block": 22,
            "minecraft:sandstone": 24,
            "minecraft:wool": 35,
            "minecraft:gold_block": 41,
            "minecraft:iron_block": 42,
            "minecraft:brick_block": 45,
            "minecraft:tnt": 46,
            "minecraft:bookshelf": 47,
            "minecraft:mossy_cobblestone": 48,
            "minecraft:obsidian": 49,
            "minecraft:diamond_ore": 56,
            "minecraft:diamond_block": 57,
            "minecraft:crafting_table": 58,
            "minecraft:farmland": 60,
            "minecraft:furnace": 61,
            "minecraft:redstone_ore": 73,
            "minecraft:snow": 78,
            "minecraft:ice": 79,
            "minecraft:snow_block": 80,
            "minecraft:cactus": 81,
            "minecraft:clay": 82,
            "minecraft:pumpkin": 86,
            "minecraft:netherrack": 87,
            "minecraft:soul_sand": 88,
            "minecraft:glowstone": 89,
            "minecraft:stone_bricks": 98,
            "minecraft:nether_brick": 112,
            "minecraft:quartz_block": 155,
            "minecraft:stained_hardened_clay": 159,
            "minecraft:sea_lantern": 169,
            "minecraft:redstone_block": 152,
            "minecraft:emerald_ore": 129,
            "minecraft:emerald_block": 133,
            "minecraft:beacon": 138,
            "minecraft:concrete": 236,
            "minecraft:concrete_powder": 237,
        }
        
        # 创建反向映射
        self.runtime_id_to_block_name = {v: k for k, v in self.block_name_to_runtime_id.items()}
        
        loaded_msg = self.get_text('file.block_mappings_loaded', '已加载 {} 种方块映射').format(len(self.block_name_to_runtime_id))
        print(f"{Color.GREEN}✅ {loaded_msg}{Color.RESET}")
        return True
    
    def parse_coord(self, token: str) -> int:
        """解析坐标（支持相对坐标 ~）"""
        token = token.strip()
        if not token:
            return 0
        
        if token.startswith('~'):
            # 相对坐标
            value = token[1:]
            if not value:
                return 0
            try:
                return int(value)
            except ValueError:
                error_msg = self.get_text('error.invalid_relative_coord', '相对坐标无效: {}').format(token)
                raise ValueError(error_msg)
        else:
            # 绝对坐标
            try:
                return int(token)
            except ValueError:
                error_msg = self.get_text('error.invalid_coord', '坐标无效: {}').format(token)
                raise ValueError(error_msg)
    
    def parse_block_states(self, state_part: str) -> Dict[str, Any]:
        """解析方块状态"""
        state_part = state_part.strip()
        if not state_part or not state_part.startswith('[') or not state_part.endswith(']'):
            return {}
        
        content = state_part[1:-1].strip()
        if not content:
            return {}
        
        states = {}
        
        # 分割属性，考虑引号内的逗号
        parts = []
        start = 0
        in_quotes = False
        for i, char in enumerate(content):
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                parts.append(content[start:i].strip())
                start = i + 1
        parts.append(content[start:].strip())
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            if '=' not in part:
                error_msg = self.get_text('error.invalid_state_entry', '状态条目无效: {}').format(part)
                raise ValueError(error_msg)
            
            key, value = part.split('=', 1)
            key = key.strip().strip('"')
            value = value.strip()
            
            # 解析值类型
            if value.lower() == 'true':
                states[key] = True
            elif value.lower() == 'false':
                states[key] = False
            elif value.startswith('"') and value.endswith('"'):
                states[key] = value[1:-1]
            elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                states[key] = int(value)
            else:
                states[key] = value
        
        return states
    
    def runtime_id_for_block(self, name: str, states: Dict[str, Any]) -> int:
        """根据方块名称和状态获取Runtime ID"""
        # 确保有命名空间
        if not ":" in name:
            name = "minecraft:" + name
        
        # 简化处理：忽略状态的影响
        # 在实际应用中，这里应该使用更复杂的映射
        if name in self.block_name_to_runtime_id:
            return self.block_name_to_runtime_id[name]
        
        # 尝试查找类似方块
        for block_name, runtime_id in self.block_name_to_runtime_id.items():
            if name in block_name:
                return runtime_id
        
        # 默认返回空气
        warning_msg = self.get_text('warning.unknown_block', '未知方块: {}, 使用空气替代').format(name)
        print(f"{Color.YELLOW}⚠️  {warning_msg}{Color.RESET}")
        return self.block_name_to_runtime_id.get("minecraft:air", 0)
    
    def process_mcfunction_file(self, file_path: str):
        """处理.mcfunction文件"""
        loading_msg = self.get_text('conversion.loading_mcfunction', '正在加载MCFunction文件...')
        print(f"{Color.CYAN}📄 {loading_msg}{Color.RESET}")
        
        block_map = {}
        min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
        max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                line_number = 0
                
                for line in file:
                    line_number += 1
                    line = line.strip()
                    
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue
                    
                    # 只处理fill和setblock命令
                    cmd_lower = line.lower()
                    if not (cmd_lower.startswith('fill ') or cmd_lower.startswith('setblock ')):
                        continue
                    
                    # 提取状态部分
                    state_part = ""
                    if '[' in line and ']' in line:
                        start_idx = line.find('[')
                        end_idx = line.rfind(']')
                        if end_idx > start_idx:
                            state_part = line[start_idx:end_idx+1]
                            line = line[:start_idx] + line[end_idx+1:]
                            line = line.strip()
                    
                    fields = line.split()
                    if not fields:
                        continue
                    
                    cmd_type = fields[0].lower()
                    
                    try:
                        if cmd_type == 'fill':
                            if len(fields) < 8:
                                continue
                            
                            x1 = self.parse_coord(fields[1])
                            y1 = self.parse_coord(fields[2])
                            z1 = self.parse_coord(fields[3])
                            x2 = self.parse_coord(fields[4])
                            y2 = self.parse_coord(fields[5])
                            z2 = self.parse_coord(fields[6])
                            block_name = fields[7]
                            
                            states = self.parse_block_states(state_part)
                            runtime_id = self.runtime_id_for_block(block_name, states)
                            
                            # 更新边界
                            x_min, x_max = min(x1, x2), max(x1, x2)
                            y_min, y_max = min(y1, y2), max(y1, y2)
                            z_min, z_max = min(z1, z2), max(z1, z2)
                            
                            for x in range(x_min, x_max + 1):
                                for y in range(y_min, y_max + 1):
                                    for z in range(z_min, z_max + 1):
                                        block_map[(x, y, z)] = runtime_id
                                        min_x = min(min_x, x)
                                        min_y = min(min_y, y)
                                        min_z = min(min_z, z)
                                        max_x = max(max_x, x)
                                        max_y = max(max_y, y)
                                        max_z = max(max_z, z)
                        
                        elif cmd_type == 'setblock':
                            if len(fields) < 5:
                                continue
                            
                            x = self.parse_coord(fields[1])
                            y = self.parse_coord(fields[2])
                            z = self.parse_coord(fields[3])
                            block_name = fields[4]
                            
                            states = self.parse_block_states(state_part)
                            runtime_id = self.runtime_id_for_block(block_name, states)
                            
                            block_map[(x, y, z)] = runtime_id
                            min_x = min(min_x, x)
                            min_y = min(min_y, y)
                            min_z = min(min_z, z)
                            max_x = max(max_x, x)
                            max_y = max(max_y, y)
                            max_z = max(max_z, z)
                    
                    except Exception as e:
                        error_msg = self.get_text('error.line_parse_failed', '第 {} 行解析失败: {}').format(line_number, e)
                        print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
                        continue
            
            if not block_map:
                error_msg = self.get_text('error.no_valid_blocks', '文件中没有有效的方块数据')
                print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
                return False
            
            # 保存文件路径
            self.file_path = file_path
            
            # 计算尺寸
            self.min_coords = {"x": min_x, "y": min_y, "z": min_z}
            self.max_coords = {"x": max_x, "y": max_y, "z": max_z}
            
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            length = max_z - min_z + 1
            
            self.original_size = {"width": width, "height": height, "length": length}
            self.size = {"width": width, "height": height, "length": length}
            
            # 创建方块列表
            self.blocks = []
            self.non_air_blocks = 0
            
            # 按y, z, x排序
            sorted_positions = sorted(block_map.keys(), key=lambda pos: (pos[1], pos[2], pos[0]))
            
            air_runtime_id = self.block_name_to_runtime_id.get("minecraft:air", 0)
            
            progress = ProgressDisplay(len(sorted_positions), 
                                      self.get_text('progress.processing_blocks', '处理方块'), 
                                      self.config)
            
            for idx, (x, y, z) in enumerate(sorted_positions):
                runtime_id = block_map[(x, y, z)]
                
                # 转换为局部坐标
                local_x = x - min_x
                local_y = y - min_y
                local_z = z - min_z
                
                # 获取方块名称
                block_name = self.runtime_id_to_block_name.get(runtime_id, "minecraft:air")
                
                self.blocks.append({
                    "name": block_name,
                    "aux": 0,  # MCFunction中aux通常为0
                    "x": local_x,
                    "y": local_y,
                    "z": local_z,
                    "runtime_id": runtime_id
                })
                
                if runtime_id != air_runtime_id:
                    self.non_air_blocks += 1
                
                progress.update(idx + 1)
            
            progress.complete()
            
            loaded_msg = self.get_text('conversion.mcfunction_loaded', 'MCFunction文件加载完成')
            stats_msg = self.get_text('stats.file_stats', '尺寸: {}×{}×{}, 方块数: {}').format(
                width, height, length, len(self.blocks))
            print(f"{Color.GREEN}✅ {loaded_msg}{Color.RESET}")
            print(f"{Color.CYAN}📊 {stats_msg}{Color.RESET}")
            
            return True
            
        except Exception as e:
            error_msg = self.get_text('error.file_load_failed', '加载文件失败: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return False
    
    def set_offset_pos(self, offset_x: int = 0, offset_y: int = 0, offset_z: int = 0):
        """设置偏移位置"""
        self.offset_pos = {"x": offset_x, "y": offset_y, "z": offset_z}
        self.size["width"] = self.original_size["width"] + abs(offset_x)
        self.size["height"] = self.original_size["height"] + abs(offset_y)
        self.size["length"] = self.original_size["length"] + abs(offset_z)
        
        offset_msg = self.get_text('conversion.offset_set', '偏移位置已设置: X={}, Y={}, Z={}').format(
            offset_x, offset_y, offset_z)
        print(f"{Color.CYAN}📍 {offset_msg}{Color.RESET}")
    
    def convert_to_runaway(self, output_path: str, offset_x: int = 0, offset_y: int = 0, offset_z: int = 0):
        """转换为RunAway格式"""
        if not self.blocks:
            error_msg = self.get_text('error.no_blocks_to_convert', '没有方块数据可转换')
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            return None
        
        starting_msg = self.get_text('conversion.starting_conversion', '开始转换到RunAway格式...')
        print(f"{Color.CYAN}🔄 {starting_msg}{Color.RESET}")
        
        # 设置偏移
        self.set_offset_pos(offset_x, offset_y, offset_z)
        
        # 创建RunAway对象
        runaway = RunAway()
        
        # 转换方块数据
        total_blocks = len(self.blocks)
        progress = ProgressDisplay(total_blocks, 
                                  self.get_text('progress.converting_blocks', '转换方块'), 
                                  self.config)
        
        air_runtime_id = self.block_name_to_runtime_id.get("minecraft:air", 0)
        
        for idx, block in enumerate(self.blocks):
            # 应用偏移
            new_x = block["x"] + offset_x
            new_y = block["y"] + offset_y
            new_z = block["z"] + offset_z
            
            # 只添加非空气方块
            if block.get("runtime_id", air_runtime_id) != air_runtime_id:
                runaway.blocks.append({
                    "name": block["name"],
                    "aux": block["aux"],
                    "x": new_x,
                    "y": new_y,
                    "z": new_z
                })
            
            progress.update(idx + 1)
        
        progress.complete()
        
        # 保存文件
        saving_msg = self.get_text('conversion.saving_file', '正在保存RunAway文件...')
        print(f"{Color.CYAN}💾 {saving_msg}{Color.RESET}")
        
        if not output_path.lower().endswith('.json'):
            output_path += '.json'
        
        # 确保目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        runaway.save_as(output_path)
        
        # 统计信息
        converted_blocks = len(runaway.blocks)
        saved_msg = self.get_text('conversion.conversion_complete', '转换完成!')
        stats_msg = self.get_text('stats.conversion_stats', '原始方块: {}, 转换后方块: {}, 文件: {}').format(
            total_blocks, converted_blocks, output_path)
        
        print(f"{Color.GREEN}✅ {saved_msg}{Color.RESET}")
        print(f"{Color.CYAN}📊 {stats_msg}{Color.RESET}")
        
        return self.size["width"], self.size["height"], self.size["length"], converted_blocks
    
    def convert(self, input_file, output_path, offset_x=0, offset_y=0, offset_z=0):
        """转换入口函数（与RunawayConverter保持相同接口）"""
        if not os.path.exists(input_file):
            error_msg = self.get_text('error.file_not_found', '文件不存在: {}').format(input_file)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            return None
        
        if not input_file.lower().endswith('.mcfunction'):
            warning_msg = self.get_text('warning.not_mcfunction', '文件不是.mcfunction格式: {}').format(input_file)
            print(f"{Color.YELLOW}⚠️  {warning_msg}{Color.RESET}")
        
        try:
            # 加载MCFunction文件
            if not self.process_mcfunction_file(input_file):
                return None
            
            # 转换为RunAway格式
            result = self.convert_to_runaway(output_path, offset_x, offset_y, offset_z)
            return result
            
        except Exception as e:
            error_msg = self.get_text('error.conversion_failed', '转换过程中发生错误: {}').format(e)
            print(f"{Color.RED}❌ {error_msg}{Color.RESET}")
            import traceback
            traceback.print_exc()
            return None

# 兼容性别名
Converter = MCFunctionConverter