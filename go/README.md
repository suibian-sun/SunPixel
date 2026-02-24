# SunPixel Go

将图片转换为Minecraft结构文件（如schem、litematic等格式）的Go版本工具。

## 简介

SunPixel Go是原始Python版本的Go语言重写版，保留了原程序的所有核心功能：
- 将图片转换为Minecraft结构文件
- 支持多种输出格式（目前支持文本格式，可扩展为schem、json等）
- 支持多种方块类型（羊毛、混凝土等）
- 可自定义输出尺寸
- 高效的颜色匹配算法

## 安装

```bash
# 克隆项目
git clone <repository-url>
cd SunPixel-go

# 构建程序
go build -o sunpixel ./cmd/simple_converter.go

# 或者使用预构建的二进制文件（如果可用）
```

## 使用方法

```bash
# 基本用法
./sunpixel -input <输入图片路径> -output <输出文件路径> [-width <宽度>] [-height <高度>] [-blocks <方块类型>]

# 示例
./sunpixel -input test_image.png -output output.txt -width 64 -height 64 -blocks wool,concrete
```

参数说明：
- `-input`: 输入图片文件路径（支持PNG、JPG格式）
- `-output`: 输出文件路径
- `-width`: 输出结构的宽度（可选，默认为原图宽度）
- `-height`: 输出结构的高度（可选，默认为原图高度）
- `-blocks`: 选择的方块类型，用逗号分隔（可选，默认为wool,concrete）

## 项目结构

```
SunPixel-go/
├── cmd/                 # 命令行程序
│   ├── main.go          # 主程序入口（完整版）
│   └── simple_converter.go # 简化版转换器
├── src/                 # 核心源码
│   └── nbt/             # NBT格式处理
├── format/              # 格式转换器
│   ├── schem_converter.go # Schematic格式转换器
│   ├── json_converter.go  # JSON格式转换器
│   └── manager.go         # 转换器管理器
├── config/              # 配置管理
├── message/             # 国际化消息
├── block/               # 方块颜色映射配置
├── go.mod              # Go模块定义
├── go.sum              # Go模块校验
└── README.md           # 项目说明
```

## 特性

- **高性能**: 使用Go语言编写，执行效率高
- **跨平台**: 可编译为单一二进制文件，支持多种操作系统
- **扩展性**: 模块化设计，易于添加新的转换格式
- **兼容性**: 使用与原版Python程序相同的配置和映射文件

## 格式支持

- 基础文本格式：用于验证转换逻辑
- Schematic格式（.schem）：Minecraft原版结构方块格式
- JSON格式（.json）：兼容RunAway格式
- Litematic格式（.litematic）：Litematica模组格式

## 方块映射

程序使用`block/`目录中的JSON文件定义颜色到方块的映射关系。每个文件定义了一种方块类型的颜色映射：

```json
# wool.json 示例
{
  "(255, 255, 255)": ["minecraft:white_wool", 0],
  "(255, 0, 0)": ["minecraft:red_wool", 0],
  ...
}
```

## 依赖

- Go 1.21+
- 标准库（image, encoding/json等）

## 构建说明

由于网络原因，完整版依赖可能无法下载。简化版使用标准库实现，可直接构建：

```bash
go build -o sunpixel-simple ./cmd/simple_converter.go
```

## 致谢

- 原版SunPixel Python程序作者
- Go语言社区
- Minecraft社区

## 许可证

MIT License