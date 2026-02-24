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
import datetime
import urllib.request
import urllib.error
import re
import sys
import threading
from io import BytesIO, StringIO, TextIOBase, IOBase
from typing import Dict, List, Union
from enum import Enum

# 创建必要的目录结构
Path("format").mkdir(exist_ok=True)

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

# 临时占位符，稍后会在get_available_formats函数后定义
class OutputFormat(Enum):
    """输出格式枚举（临时占位）"""
    SCHEMATIC = "schem"
    RUNAWAY = "json"
    LITEMATICA = "litematic"

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

# ====== 新增功能：资源监控和时间检查 ======

# 全局变量用于资源监控
import threading
import psutil
import gc
from dataclasses import dataclass
from typing import Optional
import requests

# 资源监控全局变量
resource_lock = threading.Lock()
monitor_thread: Optional[threading.Thread] = None
monitor_running = False
max_memory_mb = 0.0

@dataclass
class TimeResponse:
    """服务器时间响应结构"""
    code: int
    message: str
    details: str
    entity: dict
    
    @property
    def current_time(self) -> int:
        """获取当前时间戳"""
        return self.entity.get("current", 0)

class ResourceMonitor:
    """资源监控器"""
    def __init__(self):
        self.max_memory_mb = 0.0
        self.monitor_thread = None
        self.running = False
        
    def start(self):
        """启动资源监控"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print(f"📊 资源监控已启动")
        
    def stop(self):
        """停止资源监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print(f"📊 资源监控已停止")
        
    def _monitor_loop(self):
        """监控循环，1秒采样一次"""
        process = psutil.Process()
        
        while self.running:
            try:
                # 获取内存使用（MB）
                memory_info = process.memory_info()
                current_mb = memory_info.rss / 1024 / 1024  # RSS是实际使用的物理内存
                
                with resource_lock:
                    if current_mb > self.max_memory_mb:
                        self.max_memory_mb = current_mb
                
                time.sleep(1)  # 1秒采样一次
                
            except Exception as e:
                print(f"⚠️  资源监控出错: {e}")
                time.sleep(5)
    
    def get_max_memory_usage(self) -> float:
        """获取最高内存占用"""
        with resource_lock:
            return self.max_memory_mb

# 创建全局资源监控器实例
global_monitor = ResourceMonitor()

class RunAway:
    """RunAway 官方结构文件对象"""
    def __init__(self):
        self.blocks: List[Dict] = TypeCheckList().setChecker(dict)

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            super().__setattr__(name, value)
        elif isinstance(value, type(getattr(self, name))):
            super().__setattr__(name, value)
        else:
            raise Exception(f"无法修改 {name} 属性")

    def __delattr__(self, name):
        raise Exception("无法删除任何属性")

    def get_volume(self):
        if not self.blocks:
            return [0, 0, 0], [0, 0, 0]
            
        origin_min, origin_max = [0, 0, 0], [0, 0, 0]
        
        def pos_iter():
            for i in self.blocks:
                yield (i["x"], i["y"], i["z"])
        
        first = next(pos_iter())
        origin_min = list(first)
        origin_max = list(first)
        
        for pos in pos_iter():
            for i in range(3):
                origin_min[i] = min(origin_min[i], pos[i])
                origin_max[i] = max(origin_max[i], pos[i])

        return origin_min, origin_max

    def error_check(self):
        for block in self.blocks:
            if not isinstance(block.get("name", None), str):
                raise Exception("方块数据缺少或存在错误的 name 参数")
            if not isinstance(block.get("aux", 0), int):
                raise Exception("方块数据存在错误的 aux 参数")
            if not isinstance(block.get("x", None), int):
                raise Exception("方块数据存在错误的 x 参数")
            if not isinstance(block.get("y", None), int):
                raise Exception("方块数据存在错误的 y 参数")
            if not isinstance(block.get("z", None), int):
                raise Exception("方块数据存在错误的 z 参数")

            block["aux"] = block.get("aux", 0)

    @classmethod
    def from_buffer(cls, buffer: Union[str, IOBase, BytesIO, StringIO]):
        if isinstance(buffer, str):
            _file = open(buffer, "rb")
        elif isinstance(buffer, bytes):
            _file = BytesIO(buffer)
        else:
            _file = buffer
        
        Json1: List[Dict] = json.load(fp=_file)

        StructureObject = cls()
        StructureObject.blocks.extend(Json1)

        return StructureObject

    def save_as(self, buffer: Union[str, IOBase, StringIO]):
        self.error_check()

        Json1: List[Dict] = list(self.blocks)

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
        if data_type != "json":
            return False
        Json1 = data

        if not isinstance(Json1, list):
            return False
        if any(not isinstance(i, dict) for i in Json1[:10]):
            return False
        if isinstance(Json1, list) and len(Json1) and isinstance(Json1[0], dict) and \
                "name" in Json1[0] and isinstance(Json1[0].get("x", None), int):
            return True
        return False

# ====== 资源监控和缓存清理功能 ======

def show_max_resource_usage():
    """展示最高资源占用"""
    global_monitor.stop()
    
    max_memory = global_monitor.get_max_memory_usage()
    
    print(f"\n{'='*50}")
    print(f"📊 程序运行资源统计")
    print(f"{'='*50}")
    print(f"最高内存占用: {max_memory:.2f} MB")
    print(f"{'='*50}")
    
    return max_memory

def cleanup_cache():
    """清理缓存数据"""
    use_color = True  # 假设使用颜色输出
    
    print(f"\n🧹 正在清理缓存数据...")
    
    # 清理内存缓存
    print(f"🧹 清理内存缓存...")
    
    # 清理所有paletteCache缓存
    # 注意：这里无法直接访问各个结构体的私有paletteCache字段
    # 依赖垃圾回收器自动清理
    
    # 清理临时文件
    print(f"🧹 清理临时文件...")
    cleanup_temp_files()
    
    # 强制垃圾回收
    gc.collect()
    
    if use_color:
        print(f"✅ 缓存清理完成")
    else:
        print(f"✅ 缓存清理完成")

def cleanup_temp_files():
    """清理临时文件"""
    import shutil
    
    # 清理默认的world目录
    if os.path.exists("world"):
        try:
            shutil.rmtree("world")
            print(f"🧹 清理临时世界目录: world")
        except Exception as e:
            print(f"⚠️  清理world目录失败: {e}")
    
    # 清理world_tmp_*目录
    for entry in os.listdir("."):
        if os.path.isdir(entry) and entry.startswith("world_tmp_"):
            try:
                shutil.rmtree(entry)
                print(f"🧹 清理临时世界目录: {entry}")
            except Exception as e:
                print(f"⚠️  清理{entry}目录失败: {e}")
    
    # 清理mcworld_extract_*目录
    for entry in os.listdir("."):
        if os.path.isdir(entry) and entry.startswith("mcworld_extract_"):
            try:
                shutil.rmtree(entry)
                print(f"🧹 清理解压目录: {entry}")
            except Exception as e:
                print(f"⚠️  清理{entry}目录失败: {e}")
    
    # 清理临时zip文件
    for entry in os.listdir("."):
        if os.path.isfile(entry) and entry.endswith(".zip"):
            # 检查是否为临时zip文件（通常由程序生成）
            if "@[" in entry and "]~" in entry:
                try:
                    os.remove(entry)
                    print(f"🧹 清理临时zip文件: {entry}")
                except Exception as e:
                    print(f"⚠️  清理{entry}文件失败: {e}")

def check_time_bomb() -> bool:
    """检查时间炸弹，如果当前时间超过明天这个时间，程序将无法运行"""
    print(f"\n⏰ 正在检查程序有效期...")
    
    try:
        # 获取服务器时间
        response = requests.get("https://g79mclobt.minecraft.cn/server-time", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        time_resp = TimeResponse(
            code=data.get("code", 0),
            message=data.get("message", ""),
            details=data.get("details", ""),
            entity=data.get("entity", {})
        )
        
        # 当前服务器时间
        current_time = time_resp.current_time
        if current_time == 0:
            print(f"❌ 无法获取有效的时间戳，有效期检查失败")
            return False
        
        # 计算炸弹时间：当前时间戳 + 1天
        bomb_time = current_time + 86400
        
        # 如果当前时间超过了炸弹时间，程序无法运行
        if current_time > bomb_time:
            print(f"❌ 程序已过期，无法继续运行。")
            return False
        
        print(f"✅ 程序有效期检查通过。")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 无法连接到时间服务器，有效期检查失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 有效期检查过程中发生错误: {e}")
        return False

def bye():
    """程序退出清理"""
    show_max_resource_usage()
    cleanup_cache()
    print(f"\n👋 已退出 SunPixel，再见！")

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
                bar = f'{Color.GREEN.value}█{Color.RESET.value}' * filled_length + f'{Color.GRAY.value}░{Color.RESET.value}' * (bar_length - filled_length)
            else:
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            sys.stdout.write(f'\r📊 {self.description}: [{bar}] {self.current}/{self.total} ({progress:.1f}%)')
            sys.stdout.flush()
            time.sleep(0.1)
        
        if self.current >= self.total:
            progress = 100.0
            bar_length = 30
            if use_color:
                bar = f'{Color.GREEN.value}█{Color.RESET.value}' * bar_length
            else:
                bar = '█' * bar_length
            sys.stdout.write(f'\r📊 {self.description}: [{bar}] {self.current}/{self.total} ({progress:.1f}%) ✅\n')
            sys.stdout.flush()

class Config:
    """JSON配置管理器"""
    def __init__(self):
        self.config_path = Path("config.json")
        self.config_data = {}
        self.load()
        
    def load(self):
        """加载配置文件"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️  配置文件损坏，使用默认配置")
                self.create_default()
        else:
            self.create_default()
            
    def save(self):
        """保存配置文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            
    def get(self, section, key, fallback=None):
        """获取配置值"""
        try:
            return self.config_data.get(section, {}).get(key, fallback)
        except:
            return fallback
            
    def getboolean(self, section, key, fallback=False):
        """获取布尔配置值"""
        try:
            value = self.get(section, key, fallback)
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ['true', 'yes', '1', 'y']
            else:
                return bool(value)
        except:
            return fallback
            
    def set(self, section, key, value):
        """设置配置值"""
        if section not in self.config_data:
            self.config_data[section] = {}
        self.config_data[section][key] = value
        self.save()

def get_gradient_colors(num_colors, use_color=True):
    """生成渐变颜色序列"""
    if not use_color:
        return [''] * num_colors
        
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
    
    if num_colors <= len(gradient_colors):
        return gradient_colors[:num_colors]
    
    result = []
    for i in range(num_colors):
        pos = i / (num_colors - 1) * (len(gradient_colors) - 1)
        idx = int(pos)
        result.append(gradient_colors[idx])
    
    return result

def colored_text(text, color, use_color=True):
    """返回带颜色的文本，根据配置决定是否添加颜色"""
    if use_color and color:
        return f"{color.value}{text}{Color.RESET.value}"
    return text

def display_logo(config):
    """显示渐变颜色程序logo"""
    use_color = config.getboolean('ui', 'colored_output', True)
    
    logo_lines = [
        "╔═════════════════════════════════════════════╗",
        "║  ███████╗██╗   ██║███╗   ██║                ║",
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
    
    if use_color:
        gradient = get_gradient_colors(len(logo_lines), use_color)
        reset_color = Color.RESET.value
    else:
        gradient = [''] * len(logo_lines)
        reset_color = ''
    
    print()
    for i, line in enumerate(logo_lines):
        print(f"{gradient[i]}{line}{reset_color}")
    
    info_lines = [
        "┌───────────────────────────────────────────┐",
        "│         Open source - SunPixel            │",
        "│ https://github.com/suibian-sun/SunPixel   │",
        "└───────────────────────────────────────────┘",
        "Authors: suibian-sun"
    ]
    
    if use_color:
        info_gradient = get_gradient_colors(len(info_lines), use_color)
    else:
        info_gradient = [''] * len(info_lines)
    
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
    
    box_width = max(60, max_line_length + 4)
    
    top_border = "╔" + "═" * (box_width - 2) + "╗"
    middle_border = "╠" + "═" * (box_width - 2) + "╣"
    bottom_border = "╚" + "═" * (box_width - 2) + "╝"
    
    formatted_lines = []
    
    title_line = f"║ 📅 发布日期: {date_str}"
    formatted_lines.append(title_line.ljust(box_width - 1) + "║")
    formatted_lines.append(middle_border)
    
    for line in lines:
        if line.strip():
            while len(line) > box_width - 4:
                segment = line[:box_width - 4]
                formatted_line = f"║ {segment}"
                formatted_lines.append(formatted_line.ljust(box_width - 1) + "║")
                line = line[box_width - 4:]
            
            if line.strip():
                formatted_line = f"║ {line}"
                formatted_lines.append(formatted_line.ljust(box_width - 1) + "║")
        else:
            formatted_lines.append(f"║{' ' * (box_width - 2)}║")
    
    formatted_content = [top_border] + formatted_lines + [bottom_border]
    
    return formatted_content

def display_announcement(config):
    """显示最新公告"""
    announcement = get_latest_announcement()
    
    if announcement:
        date_str, content = announcement
        formatted_announcement = format_announcement_box(date_str, content)
        
        print(f"\n📢 最新公告")
        for line in formatted_announcement:
            print(line)
    else:
        print(f"\n📢 暂无公告或无法获取公告")

def get_available_formats():
    """自动获取Format文件夹中的所有可用转换器格式"""
    format_dir = Path("Format")
    formats = []
    
    if not format_dir.exists():
        print(f"⚠️  Format目录不存在，创建中...")
        format_dir.mkdir(exist_ok=True)
        return formats
    
    # 扫描Format目录下的所有.py文件
    for file in format_dir.glob("*.py"):
        if file.name == "__init__.py" or file.name.startswith("_"):
            continue
            
        format_name = file.stem
        
        # 尝试读取文件第一行获取格式描述
        description = format_name
        try:
            with open(file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#'):
                    # 提取注释内容作为描述
                    description = first_line[1:].strip()
        except:
            pass
        
        # 确定文件扩展名
        if format_name == "schem":
            extension = ".schem"
        elif format_name == "runaway":
            extension = ".json"
        elif format_name == "litematic":
            extension = ".litematic"
        else:
            extension = f".{format_name}"
        
        formats.append({
            "name": format_name,
            "description": description,
            "extension": extension,
            "file": file
        })
    
    return formats

def get_format_display_name(format_info):
    """获取格式的显示名称"""
    name = format_info["name"]
    description = format_info["description"]
    
    if description != name:
        return f"{name} ({description})"
    return name

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

def select_blocks(config):
    """让用户选择要使用的方块类型"""
    blocks_info = get_available_blocks()
    available_blocks = list(blocks_info.keys())
    
    if not available_blocks:
        print(f"❌ 没有找到任何方块映射文件!")
        return []
        
    print(f"\n📦 请选择要使用的方块类型:")
    print("-" * 50)
    
    use_color = config.getboolean('ui', 'colored_output', True)
    
    for i, block in enumerate(available_blocks, 1):
        chinese_name = blocks_info[block]
        if use_color:
            print(f"  {Color.CYAN.value}{i}. {block}{Color.RESET.value} ({chinese_name})")
        else:
            print(f"  {i}. {block} ({chinese_name})")
    
    if use_color:
        print(f"  {Color.GREEN.value}{len(available_blocks) + 1}. 全选{Color.RESET.value}")
        print(f"  {Color.YELLOW.value}{len(available_blocks) + 2}. 取消全选{Color.RESET.value}")
    else:
        print(f"  {len(available_blocks) + 1}. 全选")
        print(f"  {len(available_blocks) + 2}. 取消全选")
    print("-" * 50)
    
    selected = set()
    
    while True:
        choice = input(f"\n📦 请选择方块类型(输入编号，多个用逗号分隔，回车确认): ").strip()
        
        if not choice:
            if not selected:
                print(f"⚠️  未选择任何方块，将使用默认方块")
                return ["wool", "concrete"]
            break
            
        try:
            choices = [c.strip() for c in choice.split(',')]
            for c in choices:
                if c.isdigit():
                    idx = int(c)
                    if 1 <= idx <= len(available_blocks):
                        selected.add(available_blocks[idx-1])
                    elif idx == len(available_blocks) + 1:
                        selected = set(available_blocks)
                        if use_color:
                            print(f"{Color.GREEN.value}✅ 已全选所有方块{Color.RESET.value}")
                        else:
                            print(f"✅ 已全选所有方块")
                        break
                    elif idx == len(available_blocks) + 2:
                        selected.clear()
                        if use_color:
                            print(f"{Color.YELLOW.value}✅ 已取消全选{Color.RESET.value}")
                        else:
                            print(f"✅ 已取消全选")
                        break
                    else:
                        print(f"❌ 无效的选择: {c}")
                else:
                    if c in available_blocks:
                        selected.add(c)
                    else:
                        print(f"❌ 无效的方块类型: {c}")
            
            if selected:
                selected_names = []
                for block in sorted(selected):
                    chinese_name = blocks_info[block]
                    if use_color:
                        selected_names.append(f"{Color.GREEN.value}{block}{Color.RESET.value}({chinese_name})")
                    else:
                        selected_names.append(f"{block}({chinese_name})")
                if use_color:
                    print(f"{Color.GREEN.value}✅ 已选择: {', '.join(selected_names)}{Color.RESET.value}")
                else:
                    print(f"✅ 已选择: {', '.join(selected_names)}")
                break
                
        except ValueError:
            print(f"❌ 请输入有效的数字")
    
    return list(selected)

def create_dynamic_output_format(config):
    """创建动态输出格式对象"""
    # 自动获取可用格式
    available_formats = get_available_formats()
    
    if not available_formats:
        print(f"❌ 错误: Format文件夹中没有找到任何转换器文件!")
        return None
    
    # 动态创建OutputFormat类
    format_names = [fmt["name"] for fmt in available_formats]
    
    # 创建枚举类
    DynamicOutputFormat = Enum('DynamicOutputFormat', 
                              {name.upper(): name for name in format_names})
    
    return DynamicOutputFormat

def get_user_input(config):
    """获取用户输入"""
    use_color = config.getboolean('ui', 'colored_output', True)
    
    print(f"\n{'='*50}")
    
    # 自动获取可用格式
    available_formats = get_available_formats()
    
    if not available_formats:
        print(f"❌ 错误: Format文件夹中没有找到任何转换器文件!")
        print(f"请确保Format文件夹中包含以下文件:")
        print(f"  - schem.py (Schematic格式转换器)")
        print(f"  - runaway.py (RunAway格式转换器)")
        print(f"  - litematic.py (Litematica格式转换器)")
        sys.exit(1)
    
    # 选择输出格式
    print(f"\n📁 请选择输出文件格式:")
    
    # 动态生成格式选择菜单
    format_map = {}
    for i, format_info in enumerate(available_formats, 1):
        display_name = get_format_display_name(format_info)
        extension = format_info["extension"]
        
        # 分配颜色
        colors = [Color.GREEN, Color.BLUE, Color.MAGENTA, Color.CYAN, Color.YELLOW]
        color_idx = (i - 1) % len(colors)
        
        if use_color:
            print(f"  {colors[color_idx].value}{i}. {extension} ({display_name}){Color.RESET.value}")
        else:
            print(f"  {i}. {extension} ({display_name})")
        
        format_map[str(i)] = format_info
    
    while True:
        if use_color:
            format_choice = input(f"{Color.CYAN.value}请选择格式 (1-{len(available_formats)}):{Color.RESET.value} ").strip()
        else:
            format_choice = input(f"请选择格式 (1-{len(available_formats)}): ").strip()
        
        if format_choice in format_map:
            selected_format = format_map[format_choice]
            # 创建动态的OutputFormat对象
            output_format = type('DynamicOutputFormat', (), {
                'value': selected_format["name"],
                'name': selected_format["name"].upper()
            })()
            break
        else:
            print(f"❌ 请选择 1-{len(available_formats)} 之间的数字")
    
    # 获取输入文件路径
    while True:
        if use_color:
            input_path = input(f"\n{Color.CYAN.value}🖼️  请输入图片路径 (PNG或JPG):{Color.RESET.value} ").strip()
        else:
            input_path = input(f"\n🖼️  请输入图片路径 (PNG或JPG): ").strip()
        if not input_path:
            print(f"❌ 路径不能为空")
            continue
            
        if not os.path.exists(input_path):
            print(f"❌ 错误: 文件 '{input_path}' 不存在")
            continue
            
        ext = os.path.splitext(input_path)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg'):
            print(f"❌ 错误: 只支持PNG和JPG格式的图片")
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
                print(f"❌ 请输入有效的尺寸格式，例如 64x64")
                continue
            break
        except Exception as e:
            print(f"❌ 无法打开文件: {e}，请重新输入")
    
    # 选择方块类型
    selected_blocks = select_blocks(config)
    
    # 设置输出目录和文件名
    output_dir = Path(config.get('general', 'output_directory', 'output'))
    output_dir.mkdir(exist_ok=True)
    
    default_name = Path(input_path).stem + f".{output_format.value}"
    if use_color:
        output_path = input(f"\n{Color.CYAN.value}💾 输出文件名 (回车使用 '{default_name}'):{Color.RESET.value} ").strip()
    else:
        output_path = input(f"\n💾 输出文件名 (回车使用 '{default_name}'): ").strip()
    
    if not output_path:
        output_path = default_name
    elif not output_path.lower().endswith(f'.{output_format.value}'):
        output_path += f'.{output_format.value}'
    
    output_file = output_dir / output_path
    
    # 获取生成尺寸
    while True:
        if use_color:
            size_input = input(f"\n{Color.CYAN.value}📐 请输入生成尺寸(格式: 宽x高，例如 64x64，留空则使用原图尺寸):{Color.RESET.value} ").strip()
        else:
            size_input = input(f"\n📐 请输入生成尺寸(格式: 宽x高，例如 64x64，留空则使用原图尺寸): ").strip()
        if not size_input:
            width, height = None, None
            break
        
        try:
            if 'x' in size_input:
                width, height = map(int, size_input.lower().split('x'))
            elif '×' in size_input:
                width, height = map(int, size_input.lower().split('×'))
            else:
                print(f"❌ 请输入有效的尺寸格式，例如 64x64")
                continue
                
            if width <= 0 or height <= 0:
                print(f"❌ 尺寸必须大于0")
                continue
            break
        except ValueError:
            print(f"❌ 请输入有效的尺寸格式，例如 64x64")
    
    return input_path, str(output_file), width, height, selected_blocks, output_format

def verify_schem_file(file_path, config):
    """验证schem文件内容并修复可能的错误"""
    use_color = config.getboolean('ui', 'colored_output', True)
    
    print(f"\n🔍 正在验证生成的schem文件...")
    
    try:
        nbt_file = nbtlib.load(file_path, gzipped=True)
        
        required_fields = ["Version", "DataVersion", "Width", "Height", "Length", "Palette", "BlockData"]
        missing_fields = [field for field in required_fields if field not in nbt_file]
        
        if missing_fields:
            print(f"❌ 文件缺少必要字段: {', '.join(missing_fields)}")
            return False, "文件结构不完整"
        
        width = nbt_file["Width"]
        height = nbt_file["Height"]
        length = nbt_file["Length"]
        
        if width <= 0 or height <= 0 or length <= 0:
            print(f"❌ 文件尺寸数据无效")
            return False, "尺寸数据无效"
        
        palette = nbt_file["Palette"]
        if not palette:
            print(f"❌ 调色板为空")
            return False, "调色板为空"
        
        block_data = nbt_file["BlockData"]
        expected_size = width * height * length
        
        if len(block_data) != expected_size:
            print(f"❌ 方块数据长度不匹配: 期望 {expected_size}, 实际 {len(block_data)}")
            return False, "方块数据长度不匹配"
        
        palette_size = len(palette)
        out_of_range_blocks = [block_id for block_id in block_data if block_id >= palette_size]
        
        if out_of_range_blocks:
            print(f"❌ 发现 {len(out_of_range_blocks)} 个超出调色板范围的方块ID")
            return False, "方块ID超出调色板范围"
        
        if use_color:
            print(f"{Color.GREEN.value}✅ schem文件验证通过{Color.RESET.value}")
        else:
            print(f"✅ schem文件验证通过")
        return True, "文件验证通过"
        
    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        return False, f"验证错误: {str(e)}"

def fix_schem_file(file_path, issue, config):
    """根据问题修复schem文件"""
    use_color = config.getboolean('ui', 'colored_output', True)
    
    if use_color:
        print(f"\n{Color.YELLOW.value}🔧 正在尝试修复schem文件: {issue}{Color.RESET.value}")
    else:
        print(f"\n🔧 正在尝试修复schem文件: {issue}")
    
    try:
        nbt_file = nbtlib.load(file_path, gzipped=True)
        
        fix_description = ""
        
        if "方块数据长度不匹配" in issue:
            width = nbt_file["Width"]
            height = nbt_file["Height"]
            length = nbt_file["Length"]
            expected_size = width * height * length
            
            new_block_data = nbtlib.ByteArray([0] * expected_size)
            nbt_file["BlockData"] = new_block_data
            
            fix_description = f"重置方块数据为默认值，长度: {expected_size}"
            
        elif "方块ID超出调色板范围" in issue:
            palette_size = len(nbt_file["Palette"])
            block_data = nbt_file["BlockData"]
            
            fixed_blocks = 0
            for i in range(len(block_data)):
                if block_data[i] >= palette_size:
                    block_data[i] = 0
                    fixed_blocks += 1
            
            fix_description = f"修复了 {fixed_blocks} 个超出调色板范围的方块ID"
            
        else:
            if "Version" not in nbt_file:
                nbt_file["Version"] = Int(2)
            if "DataVersion" not in nbt_file:
                nbt_file["DataVersion"] = Int(3100)
            
            fix_description = "添加了缺失的必要字段"
        
        backup_path = file_path.replace('.schem', '_backup.schem')
        os.rename(file_path, backup_path)
        nbt_file.save(file_path, gzipped=True)
        
        if use_color:
            print(f"{Color.GREEN.value}✅ 文件修复完成: {fix_description}{Color.RESET.value}")
            print(f"{Color.CYAN.value}📁 原始文件已备份为: {backup_path}{Color.RESET.value}")
        else:
            print(f"✅ 文件修复完成: {fix_description}")
            print(f"📁 原始文件已备份为: {backup_path}")
        
        return True, fix_description, backup_path
        
    except Exception as e:
        print(f"❌ 修复过程中发生错误: {e}")
        return False, f"修复失败: {str(e)}", None

def ask_auto_verification(config):
    use_color = config.getboolean('ui', 'colored_output', True)
    
    while True:
        if use_color:
            choice = input(f"\n{Color.CYAN.value}🔍 是否启用自动验证? (y/n, 回车默认为y):{Color.RESET.value} ").strip().lower()
        else:
            choice = input(f"\n🔍 是否启用自动验证? (y/n, 回车默认为y): ").strip().lower()
        
        if not choice or choice == 'y' or choice == 'yes':
            if use_color:
                print(f"{Color.GREEN.value}✅ 已启用自动验证{Color.RESET.value}")
            else:
                print("✅ 已启用自动验证")
            return True
        elif choice == 'n' or choice == 'no':
            if use_color:
                print(f"{Color.YELLOW.value}⚠️  已禁用自动验证{Color.RESET.value}")
            else:
                print("⚠️  已禁用自动验证")
            return False
        else:
            print(f"❌ 请输入 y 或 n")

def load_converter_module(converter_name):
    """动态加载转换器模块"""
    format_dir = Path("Format")
    module_file = format_dir / f"{converter_name}.py"
    
    if not module_file.exists():
        print(f"❌ 找不到转换器模块: {module_file}")
        return None
    
    # 动态导入模块
    import importlib.util
    spec = importlib.util.spec_from_file_location(converter_name, str(module_file))
    module = importlib.util.module_from_spec(spec)
    
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"❌ 加载转换器模块失败: {e}")
        return None

def show_settings_menu(config):
    """显示设置菜单"""
    use_color = config.getboolean('ui', 'colored_output', True)
    
    print("\n" + "="*50)
    if use_color:
        print(f"{Color.CYAN.value}⚙️  SunPixel 设置菜单{Color.RESET.value}")
    else:
        print("⚙️  SunPixel 设置菜单")
    print("="*50)
    
    while True:
        print(f"\n1. 查看当前配置")
        print(f"2. 修改输出目录")
        print(f"3. 切换控制台颜色 (当前: {'启用' if use_color else '禁用'})")
        print(f"4. 修改语言设置 (当前: {config.get('general', 'language', 'zh_CN')})")
        print(f"5. 重置为默认配置")
        print(f"6. 保存并退出")
        print(f"7. 不保存退出")
        print("-"*30)
        
        choice = input("请选择操作 (1-7): ").strip()
        
        if choice == "1":
            print(f"\n📋 当前配置:")
            print(f"   输出目录: {config.get('general', 'output_directory', 'output')}")
            print(f"   控制台颜色: {'启用' if use_color else '禁用'}")
            print(f"   语言设置: {config.get('general', 'language', 'zh_CN')}")
            
        elif choice == "2":
            new_dir = input("请输入新的输出目录路径: ").strip()
            if new_dir:
                config.set('general', 'output_directory', new_dir)
                print(f"✅ 输出目录已更新为: {new_dir}")
                
        elif choice == "3":
            current = config.getboolean('ui', 'colored_output', True)
            new_value = not current
            config.set('ui', 'colored_output', new_value)
            use_color = new_value
            print(f"✅ 控制台颜色已{'启用' if new_value else '禁用'}")
            
        elif choice == "4":
            print(f"\n🗣️  选择语言:")
            print(f"1. 中文 (zh_CN)")
            # 可以在这里添加更多语言选项
            lang_choice = input("请选择语言 (1): ").strip()
            if lang_choice == "1":
                config.set('general', 'language', 'zh_CN')
                print("✅ 语言已设置为中文")
            else:
                print("⚠️  保持当前语言设置")
                
        elif choice == "5":
            confirm = input("⚠️  确定要重置为默认配置吗? (y/n): ").strip().lower()
            if confirm == 'y' or confirm == 'yes':
                config.create_default()
                config.load()
                use_color = config.getboolean('ui', 'colored_output', True)
                print("✅ 配置已重置为默认值")
                
        elif choice == "6":
            config.save()
            print("✅ 配置已保存")
            print("👋 返回主程序...")
            break
            
        elif choice == "7":
            config.load()  # 重新加载配置，放弃更改
            print("⚠️  更改未保存")
            print("👋 返回主程序...")
            break
            
        else:
            print("❌ 无效的选择，请重新输入")

def main():
    """主程序入口"""
    # 检查命令行参数
    if '--set' in sys.argv:
        # 进入设置模式
        config = Config()
        show_settings_menu(config)
        return
    
    try:
        # 初始化配置
        config = Config()
        
        # 检查时间炸弹
        if not check_time_bomb():
            print(f"\n❌ 程序无法运行，请检查有效期。")
            input(f"按Enter键退出...")
            return
        
        # 启动资源监控
        global_monitor.start()
        
        # 显示彩色logo
        display_logo(config)
        
        # 显示最新公告
        display_announcement(config)
        
        # 询问是否启用自动验证
        enable_verification = ask_auto_verification(config)
        
        # 获取用户输入
        input_image, output_schem, width, height, selected_blocks, output_format = get_user_input(config)
        
        # 根据选择的格式加载对应的转换器模块
        # 获取格式名称（output_format现在是一个动态对象）
        format_name = output_format.value if hasattr(output_format, 'value') else str(output_format)
        
        # 加载转换器模块
        converter_module = load_converter_module(format_name)
        
        if converter_module is None:
            print(f"❌ 无法加载 {format_name} 转换器")
            sys.exit(1)
        
        print(f"\n🔄 开始转换...")
        start_time = time.time()
        
        # 执行转换并获取统计信息
        converter_class = None
        
        # 尝试获取不同的类名
        class_names = [
            f"{format_name.capitalize()}Converter",
            "Converter",
            "schemConverter" if format_name == "schem" else None,
            "LitematicaConverter" if format_name == "litematic" else None,
            "RunawayConverter" if format_name == "runaway" else None
        ]
        
        for class_name in class_names:
            if class_name and hasattr(converter_module, class_name):
                converter_class = getattr(converter_module, class_name)
                break
        
        if converter_class is None:
            # 如果找不到特定的类，尝试获取第一个类
            for attr_name in dir(converter_module):
                if not attr_name.startswith('__') and isinstance(getattr(converter_module, attr_name), type):
                    converter_class = getattr(converter_module, attr_name)
                    break
        
        if converter_class is None:
            print(f"❌ 在转换器模块中找不到转换器类")
            sys.exit(1)
        
        converter = converter_class(config)
        result = converter.convert(input_image, output_schem, width, height, selected_blocks)
        
        if result is not None:
            schem_width, schem_height, block_count = result
            elapsed = time.time() - start_time
            use_color = config.getboolean('ui', 'colored_output', True)
            
            # 显示转换统计信息
            if use_color:
                print(f"\n{Color.GREEN.value}✅ 转换成功完成! 耗时: {elapsed:.2f}秒{Color.RESET.value}")
                print(f"{Color.CYAN.value}{'='*50}{Color.RESET.value}")
                print(f"{Color.YELLOW.value}📐 生成结构尺寸: {schem_width} × {schem_height} 方块{Color.RESET.value}")
                print(f"{Color.YELLOW.value}🧱 总方块数量: {block_count} 个{Color.RESET.value}")
                print(f"{Color.YELLOW.value}💾 输出文件: {os.path.abspath(output_schem)}{Color.RESET.value}")
                
                # 显示使用的方块类型中文名
                blocks_info = get_available_blocks()
                selected_names = []
                for block in selected_blocks:
                    chinese_name = blocks_info.get(block, block)
                    selected_names.append(f"{Color.GREEN.value}{block}{Color.RESET.value}({chinese_name})")
                print(f"{Color.YELLOW.value}🎨 使用的方块类型: {', '.join(selected_names)}{Color.RESET.value}")
                print(f"{Color.CYAN.value}{'='*50}{Color.RESET.value}")
            else:
                print(f"\n✅ 转换成功完成! 耗时: {elapsed:.2f}秒")
                print(f"{'='*50}")
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
                print(f"{'='*50}")
            
            # 如果启用了自动验证，进行文件验证和修复
            if enable_verification and output_format == OutputFormat.SCHEMATIC:
                is_valid, message = verify_schem_file(output_schem, config)
                
                if not is_valid:
                    print(f"\n⚠️  文件验证发现问题: {message}")
                    
                    fix_choice = input(f"🔧 是否尝试自动修复? (y/n, 回车默认为y): ").strip().lower()
                    if not fix_choice or fix_choice == 'y' or fix_choice == 'yes':
                        fix_start_time = time.time()
                        fix_success, fix_message, backup_path = fix_schem_file(output_schem, message, config)
                        
                        if fix_success:
                            fix_elapsed = time.time() - fix_start_time
                            if use_color:
                                print(f"\n{Color.GREEN.value}✅ 自动验证并修复成功完成! 耗时: {fix_elapsed:.2f}秒{Color.RESET.value}")
                                print(f"{Color.CYAN.value}{'='*50}{Color.RESET.value}")
                                print(f"{Color.YELLOW.value}📐 生成结构尺寸: {schem_width} × {schem_height} 方块{Color.RESET.value}")
                                print(f"{Color.YELLOW.value}🧱 总方块数量: {block_count} 个{Color.RESET.value}")
                                print(f"{Color.CYAN.value}📁 原输出文件: {backup_path}{Color.RESET.value}")
                                print(f"{Color.YELLOW.value}💾 输出文件: {os.path.abspath(output_schem)}{Color.RESET.value}")
                                print(f"{Color.GREEN.value}🔧 修复内容: {fix_message}{Color.RESET.value}")
                                print(f"{Color.YELLOW.value}🎨 使用的方块类型: {', '.join(selected_names)}{Color.RESET.value}")
                                print(f"{Color.CYAN.value}{'='*50}{Color.RESET.value}")
                            else:
                                print(f"\n✅ 自动验证并修复成功完成! 耗时: {fix_elapsed:.2f}秒")
                                print(f"{'='*50}")
                                print(f"📐 生成结构尺寸: {schem_width} × {schem_height} 方块")
                                print(f"🧱 总方块数量: {block_count} 个")
                                print(f"📁 原输出文件: {backup_path}")
                                print(f"💾 输出文件: {os.path.abspath(output_schem)}")
                                print(f"🔧 修复内容: {fix_message}")
                                print(f"🎨 使用的方块类型: {', '.join(selected_names)}")
                                print(f"{'='*50}")
                            
                            print(f"\n🔍 验证修复后的文件...")
                            is_valid_after_fix, final_message = verify_schem_file(output_schem, config)
                            
                            if is_valid_after_fix:
                                if use_color:
                                    print(f"{Color.GREEN.value}✅ 修复后文件验证通过{Color.RESET.value}")
                                else:
                                    print(f"✅ 修复后文件验证通过")
                            else:
                                print(f"❌ 修复后文件仍然存在问题: {final_message}")
                        else:
                            print(f"❌ 修复失败: {fix_message}")
                    else:
                        print(f"⚠️  用户选择不进行修复")
                else:
                    if use_color:
                        print(f"{Color.GREEN.value}✅ 文件验证通过，无需修复{Color.RESET.value}")
                    else:
                        print(f"✅ 文件验证通过，无需修复")
            
        else:
            print(f"\n❌ 转换失败!")
            
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 执行退出清理
        bye()
        
        # 额外清理一次以确保所有临时文件都被清理
        cleanup_temp_files()
        
        input(f"\n按Enter键退出...")

# 主程序入口
if __name__ == "__main__":
    main()