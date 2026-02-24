# SunPixel 项目文档

## 项目概述

SunPixel 是一个将图片转换为 Minecraft 结构文件的多功能工具，支持多种输出格式和方块类型。项目包含三个主要实现版本：

- **CLI 版本（Python）**：功能完整的命令行工具，支持交互式菜单和批量处理
- **Web 版本（Python + Flask）**：基于 Web 的图形界面，支持在线使用和作品分享
- **Go 版本**：高性能的 Go 语言重写版，提供跨平台二进制文件支持

### 核心功能

- **图片转 Minecraft 结构**：将任意图片转换为 Minecraft 可用的结构文件
- **多种输出格式**：
  - `.schem` - Sponge Schematic 格式（原版结构方块）
  - `.litematic` - Litematica 模组格式
  - `.json` - RunAway 格式
  - `.bdx` - BDX 格式
  - `.mcfunction` - 命令函数格式
  - `.mcstructure` - 基岩版结构格式
  - `.mcworld` - 基岩版世界格式
- **丰富方块类型**：支持 15+ 种方块类型，包括羊毛、混凝土、陶瓦、玻璃、地毯、木材等
- **增强功能**：
  - 2D 像素画制作
  - 3D 雕塑制作
  - 红石音乐制作
  - 强化地图画（支持 177 种地图色）
  - Floyd-Steinberg 抖动算法
  - 图片旋转、镜像功能
- **多语言支持**：中文、英文、法文、俄文
- **用户系统**：支持作品分享、历史记录、点赞点踩等功能

## 项目结构

```
SunPixel/
├── cli/                    # Python CLI 版本
│   ├── SunPixel.py         # 主程序入口
│   ├── format/             # 格式转换器
│   │   ├── schem.py        # Schem 格式转换
│   │   ├── litematica.py   # Litematica 格式转换
│   │   ├── runaway.py      # RunAway 格式转换
│   │   └── ...
│   ├── block/              # 方块颜色映射配置
│   │   ├── wool.json       # 羊毛方块
│   │   ├── concrete.json   # 混凝土方块
│   │   ├── terracotta.json # 陶瓦方块
│   │   └── ...
│   ├── message/            # 国际化消息
│   ├── output/             # 输出文件目录
│   └── config.json         # 配置文件
│
├── web/                    # Web 版本
│   ├── SunPixelWeb.py      # Web 服务器入口
│   ├── assets/             # 静态资源
│   │   ├── data/           # 数据文件（版本、方块映射等）
│   │   ├── img/            # 图片资源
│   │   └── svg/            # SVG 图标
│   ├── templates/          # HTML 模板
│   ├── Format/             # 格式转换器（同 CLI）
│   ├── block/              # 方块配置（同 CLI）
│   ├── message/            # 国际化消息
│   ├── output/             # 输出文件目录
│   └── temp_downloads/     # 临时下载文件
│
├── go/                     # Go 版本
│   ├── cmd/
│   │   └── main.go         # 主程序入口
│   ├── format/             # 格式转换器
│   │   ├── schem.go        # Schem 格式转换
│   │   ├── manager.go      # 转换器管理器
│   │   └── validator.go    # 格式验证器
│   ├── config/             # 配置管理
│   │   └── config.go       # 配置加载器
│   ├── src/
│   │   ├── converter.go    # 核心转换逻辑
│   │   └── nbt/            # NBT 格式处理
│   ├── interactive/        # 交互式界面
│   ├── utils/              # 工具函数
│   ├── block/              # 方块配置（同 CLI）
│   ├── message/            # 国际化消息
│   ├── go.mod              # Go 模块定义
│   └── go.sum              # Go 模块校验
│
├── .github/
│   └── workflows/
│       └── build.yml       # CI/CD 构建配置
│
└── AGENTS.md               # 本文档
```

## 技术栈

### Python 版本（CLI 和 Web）
- **核心库**：
  - `numpy` - 数值计算和图像处理
  - `pillow` - 图像处理
  - `pypng` - PNG 图像读写
  - `nbtlib` - NBT 格式解析
  - `psutil` - 系统资源监控
  - `requests` - HTTP 请求
- **Web 特有**：
  - `flask` - Web 框架
  - 前端使用 Vue3

### Go 版本
- **Go 版本**：1.21+
- **核心依赖**：
  - `github.com/spf13/cobra` - CLI 框架
  - `github.com/disintegration/imaging` - 图像处理
  - `github.com/lucasb-eyer/go-colorful` - 颜色处理
  - `github.com/schollz/progressbar/v3` - 进度条显示

## 构建和运行

### Python CLI 版本

```bash
# 安装依赖
pip install numpy pypng pillow nbtlib psutil requests

# 运行程序
python cli/SunPixel.py
```

### Python Web 版本

```bash
# 安装依赖
pip install flask numpy pypng pillow nbtlib psutil requests

# 运行服务器
python web/SunPixelWeb.py

# 在浏览器中访问
http://127.0.0.1:5000
```

### Go 版本

```bash
# 进入 Go 目录
cd go

# 下载依赖
go mod download

# 构建程序
go build -o sunpixel ./cmd/main

# 运行程序
./sunpixel
```

### 跨平台构建（Go 版本）

项目使用 GitHub Actions 自动构建多平台二进制文件：

- `linux_amd64` - Linux x86_64
- `linux_arm64` - Linux ARM64
- `android_arm64` - Android ARM64
- `darwin_amd64` - macOS Intel
- `darwin_arm64` - macOS Apple Silicon
- `windows_amd64.exe` - Windows x86_64
- `windows_arm64.exe` - Windows ARM64

构建产物会上传到 `suibian-sun/SunPixel-Release` 仓库的 GitHub Release。

## 开发规范

### 代码风格

**Python 代码**：
- 遵循 PEP 8 规范
- 使用 4 空格缩进
- 函数和类使用文档字符串说明
- 类型注解用于函数参数和返回值

**Go 代码**：
- 遵循 Go 官方代码规范
- 使用 `gofmt` 格式化代码
- 错误处理优先使用显式返回
- 包名使用小写单词

### 目录组织规范

- `format/` 目录存放所有格式转换器，每种格式一个文件
- `block/` 目录存放方块颜色映射配置，JSON 格式
- `message/` 目录存放国际化消息，使用 `.properties` 文件
- `output/` 目录存放生成的输出文件
- `temp_downloads/` 目录存放临时下载文件（Web 版本）

### 配置文件规范

- 方块映射文件使用 JSON 格式，键为 RGB 颜色元组，值为 `[方块ID, 数据值]`
- 国际化消息使用 `.properties` 格式，键值对形式
- 配置文件使用 JSON 格式，包含 `general`、`ui` 等配置节

### 版本管理

- 使用语义化版本号（如 v26.2.24）
- 版本信息存储在 `web/assets/data/version.json`
- 变更日志记录在 `changelog/` 目录，按日期命名

### 测试规范

- 添加新功能时需要添加相应的测试用例
- 测试文件与源文件放在同一目录，命名为 `*_test.go`（Go）或 `test_*.py`（Python）
- 运行测试：
  - Python: `python -m pytest`
  - Go: `go test ./...`

## 常见任务

### 添加新的方块类型

1. 在 `block/` 目录创建新的 JSON 配置文件
2. 定义颜色到方块的映射关系
3. 在配置文件中添加新方块选项
4. 更新版本信息和变更日志

### 添加新的输出格式

1. 在 `format/` 目录创建新的转换器文件
2. 实现转换逻辑，遵循现有接口规范
3. 在格式管理器中注册新格式
4. 添加格式验证器（如果需要）
5. 更新文档和使用说明

### 修复 Bug

1. 在对应的 `format/` 文件中定位问题
2. 添加修复并确保不影响其他功能
3. 运行测试验证修复
4. 更新变更日志

### 添加新功能

1. 在主程序或相应的模块中添加功能代码
2. 更新配置文件以支持新参数
3. 添加国际化消息
4. 更新版本信息和变更日志
5. 测试新功能在不同平台上的表现

## 依赖管理

### Python 依赖

- 使用 `requirements.txt` 管理依赖（Web 版本）
- CLI 版本依赖在 `Instructions.md` 中说明

### Go 依赖

- 使用 `go.mod` 和 `go.sum` 管理依赖
- 添加新依赖：`go get <package>`
- 更新依赖：`go get -u <package>`

## 持续集成/持续部署

项目使用 GitHub Actions 进行 CI/CD：

- **触发条件**：push 到任何分支、pull request、手动触发
- **构建流程**：
  1. 准备发布环境
  2. 为多个平台构建二进制文件
  3. 使用 garble 进行代码混淆
  4. 使用 UPX 压缩二进制文件
  5. 计算 SHA512 校验和
  6. 上传到 Release 仓库
  7. 发送邮件通知构建状态

## 相关资源

- **主仓库**：https://github.com/suibian-sun/SunPixel
- **Release 仓库**：https://github.com/suibian-sun/SunPixel-Release
- **在线服务**：https://SunPixel.520cti.shop（不定时开放）

## 注意事项

1. **方块颜色映射**：确保 RGB 颜色值与 Minecraft 方块颜色匹配
2. **格式兼容性**：不同 Minecraft 版本可能对格式有不同要求
3. **性能优化**：处理大图片时注意内存使用，考虑分块处理
4. **错误处理**：所有外部操作（文件读写、网络请求）都需要适当的错误处理
5. **国际化**：添加新功能时记得更新所有语言的消息文件

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

MIT License
