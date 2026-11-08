# SunPixel 项目文档

> ## 🗺 V-2.2.0 地图画与图像调节
>
> **本次吸收了 vue3-mcpixelart 与 minecraft-block-letter 的更多能力**：强化地图画用柱子高低差
> 把 16 色方块扩成 48 档明暗；图片可先调亮度、对比度、饱和度、伽马；文字支持自定义字体、
> 横向纵向缩放与描边加粗，并能逐字导出；备料可以限制到指定方块种类。
>
> 详细说明见 [web/Changelog/2026-11-08.md](web/Changelog/2026-11-08.md)。
>
> —— SunEcology · 2026年11月8日

## 项目概述

SunPixel 是一个将图片转换为 Minecraft 结构文件的多功能工具，支持多种输出格式和方块类型。项目包含三个主要实现版本：

- **Web 版本（纯前端）**：零构建静态站，浏览器内完成全部转换，可部署到 Cloudflare Pages
- **CLI 版本（Python）**：功能完整的命令行工具，支持交互式菜单和批量处理
- **Go 版本**：高性能的 Go 语言重写版，提供跨平台二进制文件支持

### 核心功能

- **图片转 Minecraft 结构**：将任意图片转换为 Minecraft 可用的结构文件
- **文字像素画**：输入文字直接生成像素画，支持多行、字体、字号、行高、字距、对齐与描边锐化
- **强化地图画**：用柱子高低差换取明暗，把 16 色方块扩成 48 档，可选 4 / 8 / 16 层起伏
- **逐字导出**：每个字符单独生成结构并打包成 zip，方便做字库或逐字搭建
- **多种输出格式**：
  - `.schem` - Sponge Schematic v2（VarInt 编码，WorldEdit / 投影台可直接读取）
  - `.litematic` - Litematica 模组投影（位打包 BlockStates）
  - `.mcstructure` - 基岩版结构文件
  - `.mcfunction` - 命令函数（连续方块自动合并为 fill）
  - `.json` - RunAway 交换格式
  - `.md` / `.csv` - 手动搭建图纸与材料清单
- **丰富方块类型**：15 种方块类目、200+ 种方块可选
- **画质选项**：
  - CIE Lab / RGB 加权两种颜色距离
  - Floyd–Steinberg 抖动（可选蛇形扫描）
  - 透明像素识别（阈值可调，镂空处输出空气）
  - 平铺（地面）/ 竖立（贴墙）、旋转 90°/180°/270°、水平 / 垂直镜像
  - 锁定原图比例、缩放平滑开关
  - 图片调节：亮度、对比度、饱和度、伽马、灰度、反色
  - 备料优化：把调色板限制到 8 / 12 / 16 / 24 种方块
- **文字样式**：自定义字体（TTF / OTF / WOFF）、横向纵向缩放、X/Y 偏移、描边式加粗
- **多语言支持**：中文、英文、法文、俄文（CLI 与 Go 版本）


## 项目结构

```
SunPixel/
├── cli/                    # Python CLI 版本
│   ├── SunPixel.py         # 主程序入口
│   ├── Format/             # 格式转换器（CLI 运行时实际加载的目录）
│   │   ├── schem.py        # Schem 格式转换
│   │   ├── litematic.py    # Litematica 格式转换
│   │   ├── runaway.py      # RunAway 格式转换
│   │   └── ...
│   ├── format/             # Web/Go 共用资源（含 bdx_runtimeIds 等数据）
│   ├── block/              # 方块颜色映射配置
│   │   ├── wool.json       # 羊毛方块
│   │   ├── concrete.json   # 混凝土方块
│   │   └── ...
│   ├── message/            # 国际化消息
│   └── config.json         # 配置文件
│
├── web/                    # Web 版本（纯前端静态站）
│   ├── index.html          # 页面结构与样式
│   ├── js/
│   │   ├── ui/app.js       # Vue 应用
│   │   ├── converter.js    # 图片 → 像素画
│   │   ├── formatter.js    # 输出格式分发
│   │   ├── nbt-writer.js   # NBT 二进制编码
│   │   ├── core/
│   │   │   ├── color.js    # CIE Lab 颜色匹配
│   │   │   ├── pixelate.js # 抖动、几何变换、体素化
│   │   │   └── text-art.js # 文字渲染
│   │   └── format/         # schem / litematic / mcstructure / mcfunction / runaway / blueprint
│   ├── functions/api/      # Cloudflare Pages Functions（方块列表、更新记录）
│   ├── dev-server.mjs      # 本地开发服务器（同时托管静态文件与接口）
│   ├── tests/              # 单元测试、格式校验、浏览器端到端测试
│   └── assets/             # 静态资源与版本数据
│
├── go/                     # Go 版本
│   ├── cmd/main.go         # 主程序入口
│   ├── format/             # 格式转换器
│   ├── config/             # 配置管理
│   ├── src/                # 核心转换逻辑与 NBT 处理
│   ├── interactive/        # 交互式界面
│   ├── block/              # 方块配置（同 CLI）
│   └── message/            # 国际化消息
│
└── .github/workflows/       # CI/CD 构建配置（发布到 Release 仓库）
```

## 技术栈

### Python 版本（CLI）
- **核心库**：
  - `numpy` - 数值计算和图像处理
  - `pillow` - 图像处理
  - `pypng` - PNG 图像读写
  - `nbtlib` - NBT 格式解析
  - `psutil` - 系统资源监控
  - `requests` - HTTP 请求

### Web 版本
- **运行环境**：现代浏览器，零构建
- **核心**：
  - `Vue 3`（`web/vendor/vue.global.prod.js`，随仓库发布，不依赖 CDN） - 界面
  - `Canvas 2D` - 缩放、取像素、文字渲染、效果图预览
  - `CompressionStream` - gzip 压缩 NBT
  - 自研 NBT 编码器 - 生成 `.schem` / `.litematic` / `.mcstructure`
- **托管**：Cloudflare Pages（`functions/` 提供方块列表与更新记录接口）

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

### Web 版本

Web 版是零依赖静态站，转换全部在浏览器内完成。本地开发需要一个同时托管页面与 `/api/*` 的小服务：

```bash
cd web
npm run dev          # http://127.0.0.1:8788
```

不做任何事也可以直接部署：`wrangler pages deploy` 或把 `web/` 目录丢给任意静态托管（此时 `/api/blocks` 不可用，页面会自动回退到内置方块表）。

### 测试（Web 版本）

```bash
cd web
npm test             # 单元测试 + 导出文件用 nbtlib 独立校验
npm run test:e2e     # 真浏览器跑完整流程（需 playwright）
```

- `tests/unit.test.mjs`：颜色匹配、抖动、透明、旋转镜像、摆放方向
- `tests/formats.test.mjs`：把 `.schem` / `.litematic` / `.mcstructure` 等真实导出到临时目录，再用 Python 的 `nbtlib`（独立实现）解析回来逐体素比对
- `tests/e2e.mjs`：启动本地服务 → 打开页面 → 文字模式与图片模式各转一次 → 下载文件 → 校验

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
- Web 版本的测试放在 `web/tests/`，统一用 `*.test.mjs`
- 运行测试：
  - Web: `cd web && npm test`（导出文件会用 `nbtlib` 独立复核）
  - Web 端到端: `cd web && npm run test:e2e`
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
- **Release 仓库**：https://github.com/suibian-sun/SunPixel-Release（已删库）
- **在线服务**：https://SunPixel.suibian114.top & https://sunpixel.pages.dev（开放中2026.07.30）

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

## 致谢

- [TgkRuobin/vue3-mcpixelart](https://github.com/TgkRuobin/vue3-mcpixelart)（Apache-2.0）：强化地图画的思路，以及地图色数据 —— `web/js/data/map-colors.js` 由其 `blocksArt.json` 提取，只保留颜色值，算法为本项目重新实现
- [TgkRuobin/minecraft-block-letter](https://github.com/TgkRuobin/minecraft-block-letter)（MIT）：字符投影、字形缩放与逐字导出的思路

## 许可证

MIT License
