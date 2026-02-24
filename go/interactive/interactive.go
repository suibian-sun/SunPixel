package interactive

import (
	"bufio"
	"fmt"
	"image"
	"image/color"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"sunpixel/config"
	"sunpixel/format"
	"sunpixel/utils"
)

// InteractiveConverter 交互式转换器（用于交互模式）
type InteractiveConverter struct {
	colorToBlock   format.BlockColorMap
	blockPalette   []string
	width          int
	height         int
	depth          int
	pixels         [][]color.NRGBA
	originalWidth  int
	originalHeight int
	useColor       bool
}

// GetUserInput 获取用户输入
func GetUserInput(cfg *config.Config) (string, string, int, int, []string, string) {
	useColor := cfg.UI.ColoredOutput

	fmt.Printf("%s%s%s\n", utils.Cyan, strings.Repeat("=", 50), utils.Reset)

	// 获取可用格式
	converterManager := format.NewConverterManager()
	availableFormats := converterManager.GetAvailableFormats()

	// 选择输出格式
	fmt.Printf("\n%s📁 请选择输出文件格式:%s\n", utils.Yellow, utils.Reset)

	// 动态生成格式选择菜单
	formatMap := make(map[string]string)
	colors := []utils.RGBColor{
		{R: 0, G: 255, B: 0}, // Green
		{R: 0, G: 0, B: 255}, // Blue
		{R: 255, G: 0, B: 255}, // Magenta
		{R: 0, G: 255, B: 255}, // Cyan
		{R: 255, G: 255, B: 0}, // Yellow
	}

	for i, formatName := range availableFormats {
		extension := GetExtensionForFormat(formatName)
		displayStr := fmt.Sprintf("%s", formatName)

		var color utils.RGBColor
		if i < len(colors) {
			color = colors[i]
		} else {
			// 如果颜色不够用，循环使用
			color = colors[i%len(colors)]
		}

		if useColor {
			fmt.Printf("  %s%d. %s (%s)%s\n", utils.RGBToANSIColor(color.R, color.G, color.B), i+1, extension, displayStr, utils.Reset)
		} else {
			fmt.Printf("  %d. %s (%s)\n", i+1, extension, displayStr)
		}
		formatMap[fmt.Sprintf("%d", i+1)] = formatName
	}

	var selectedFormat string
	for {
		var formatChoice string
		if useColor {
			fmt.Printf("%s请选择格式 (1-%d):%s ", utils.Cyan, len(availableFormats), utils.Reset)
		} else {
			fmt.Printf("请选择格式 (1-%d): ", len(availableFormats))
		}
		
		// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理输入
		scanner := bufio.NewScanner(os.Stdin)
		if scanner.Scan() {
			formatChoice = strings.TrimSpace(scanner.Text())
		} else {
			// 处理扫描错误
			fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
			continue
		}

		if selected, ok := formatMap[formatChoice]; ok {
			selectedFormat = selected
			break
		} else {
			fmt.Printf("%s❌ 请选择 1-%d 之间的数字%s\n", utils.Red, len(availableFormats), utils.Reset)
		}
	}

	// 获取输入文件路径
	var inputPath string
	for {
		if useColor {
			fmt.Printf("\n%s🖼️  请输入图片路径 (PNG或JPG):%s ", utils.Cyan, utils.Reset)
		} else {
			fmt.Printf("\n🖼️  请输入图片路径 (PNG或JPG): ")
		}
		
		// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理包含空格和中文字符的路径
		scanner := bufio.NewScanner(os.Stdin)
		if scanner.Scan() {
			inputPath = strings.TrimSpace(scanner.Text())
		} else {
			// 处理扫描错误
			fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
			continue
		}

		if inputPath == "" {
			fmt.Printf("%s❌ 路径不能为空%s\n", utils.Red, utils.Reset)
			continue
		}

		if _, err := os.Stat(inputPath); os.IsNotExist(err) {
			fmt.Printf("%s❌ 错误: 文件 '%s' 不存在%s\n", utils.Red, inputPath, utils.Reset)
			continue
		}

		ext := strings.ToLower(filepath.Ext(inputPath))
		if ext != ".png" && ext != ".jpg" && ext != ".jpeg" {
			fmt.Printf("%s❌ 错误: 只支持PNG和JPG格式的图片%s\n", utils.Red, utils.Reset)
			continue
		}

		// 验证图片文件
		file, err := os.Open(inputPath)
		if err != nil {
			fmt.Printf("%s❌ 无法打开文件: %s%s\n", utils.Red, err, utils.Reset)
			continue
		}

		_, _, err = image.DecodeConfig(file)
		file.Close()
		if err != nil {
			fmt.Printf("%s❌ 无法识别图片文件: %s%s\n", utils.Red, err, utils.Reset)
			continue
		}

		break
	}

	// 选择方块类型
	selectedBlocks := SelectBlocks(cfg)

	// 设置输出目录和文件名
	outputDir := filepath.FromSlash(cfg.General.OutputDirectory)
	os.MkdirAll(outputDir, 0755)

	baseName := strings.TrimSuffix(filepath.Base(inputPath), filepath.Ext(inputPath))
	defaultName := baseName + GetExtensionForFormat(selectedFormat)
	var outputPath string

	if useColor {
		fmt.Printf("\n%s💾 输出文件名 (回车使用 '%s'):%s ", utils.Cyan, defaultName, utils.Reset)
	} else {
		fmt.Printf("\n💾 输出文件名 (回车使用 '%s'): ", defaultName)
	}
	
	// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理包含空格和中文字符的文件名
	scanner := bufio.NewScanner(os.Stdin)
	if scanner.Scan() {
		outputPath = strings.TrimSpace(scanner.Text())
	} else {
		// 处理扫描错误
		fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
		outputPath = "" // 确保变量有默认值
	}

	if outputPath == "" {
		outputPath = defaultName
	} else if !strings.HasSuffix(strings.ToLower(outputPath), GetExtensionForFormat(selectedFormat)) {
		outputPath += GetExtensionForFormat(selectedFormat)
	}

	outputSchem := filepath.Join(outputDir, outputPath)

	// 获取生成尺寸
	var width, height int
	for {
		var sizeInput string
		if useColor {
			fmt.Printf("\n%s📐 请输入生成尺寸(格式: 宽x高，例如 64x64，留空则使用原图尺寸):%s ", utils.Cyan, utils.Reset)
		} else {
			fmt.Printf("\n📐 请输入生成尺寸(格式: 宽x高，例如 64x64，留空则使用原图尺寸): ")
		}
		
		// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理包含空格的输入
		scanner := bufio.NewScanner(os.Stdin)
		if scanner.Scan() {
			sizeInput = strings.TrimSpace(scanner.Text())
		} else {
			// 处理扫描错误
			fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
			continue
		}

		if sizeInput == "" {
			// 使用原图尺寸
			file, err := os.Open(inputPath)
			if err != nil {
				fmt.Printf("%s❌ 无法打开文件: %s%s\n", utils.Red, err, utils.Reset)
				continue
			}

			config, _, err := image.DecodeConfig(file)
			file.Close()
			if err != nil {
				fmt.Printf("%s❌ 无法获取图片尺寸: %s%s\n", utils.Red, err, utils.Reset)
				continue
			}

			width, height = config.Width, config.Height
			break
		}

		var w, h int
		if strings.Contains(sizeInput, "x") {
			fmt.Sscanf(sizeInput, "%dx%d", &w, &h)
		} else if strings.Contains(sizeInput, "×") {
			fmt.Sscanf(sizeInput, "%d×%d", &w, &h)
		} else {
			fmt.Printf("%s❌ 请输入有效的尺寸格式，例如 64x64%s\n", utils.Red, utils.Reset)
			continue
		}

		if w <= 0 || h <= 0 {
			fmt.Printf("%s❌ 尺寸必须大于0%s\n", utils.Red, utils.Reset)
			continue
		}

		width, height = w, h
		break
	}

	return inputPath, outputSchem, width, height, selectedBlocks, selectedFormat
}
// GetExtensionForFormat 获取格式的文件扩展名
func GetExtensionForFormat(formatName string) string {
	switch formatName {
	case "schem":
		return ".schem"
	case "json":
		return ".json"
	case "litematic":
		return ".litematic"
	default:
		return fmt.Sprintf(".%s", formatName)
	}
}

// SelectBlocks 让用户选择方块类型
func SelectBlocks(cfg *config.Config) []string {
	blocksInfo := GetAvailableBlocks()
	availableBlocks := make([]string, 0, len(blocksInfo))
	for block := range blocksInfo {
		availableBlocks = append(availableBlocks, block)
	}

	if len(availableBlocks) == 0 {
		fmt.Printf("%s❌ 没有找到任何方块映射文件!%s\n", utils.Red, utils.Reset)
		return []string{"wool", "concrete"} // 返回默认值
	}

	fmt.Printf("\n%s📦 请选择要使用的方块类型:%s\n", utils.Yellow, utils.Reset)
	fmt.Printf("%s%s%s\n", utils.Yellow, strings.Repeat("-", 50), utils.Reset)

	useColor := cfg.UI.ColoredOutput

	for i, block := range availableBlocks {
		chineseName := blocksInfo[block]
		if useColor {
			fmt.Printf("  %s%d. %s%s (%s)%s\n", utils.Cyan, i+1, block, utils.Reset, chineseName, utils.Reset)
		} else {
			fmt.Printf("  %d. %s (%s)\n", i+1, block, chineseName)
		}
	}

	if useColor {
		fmt.Printf("  %s%d. 全选%s\n", utils.Green, len(availableBlocks)+1, utils.Reset)
		fmt.Printf("  %s%d. 取消全选%s\n", utils.Yellow, len(availableBlocks)+2, utils.Reset)
	} else {
		fmt.Printf("  %d. 全选\n", len(availableBlocks)+1)
		fmt.Printf("  %d. 取消全选\n", len(availableBlocks)+2)
	}
	fmt.Printf("%s%s%s\n", utils.Yellow, strings.Repeat("-", 50), utils.Reset)

	var selected []string
	for {
		var choice string
		fmt.Printf("\n%s📦 请选择方块类型(输入编号，多个用逗号分隔，回车确认):%s ", utils.Cyan, utils.Reset)
		
		// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理输入
		scanner := bufio.NewScanner(os.Stdin)
		if scanner.Scan() {
			choice = strings.TrimSpace(scanner.Text())
		} else {
			// 处理扫描错误
			fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
			continue
		}

		if choice == "" {
			if len(selected) == 0 {
				fmt.Printf("%s⚠️  未选择任何方块，将使用默认方块%s\n", utils.Yellow, utils.Reset)
				return []string{"wool", "concrete"}
			}
			break
		}

		// 解析选择
		choices := strings.Split(choice, ",")
		selected = []string{}

		for _, c := range choices {
			c = strings.TrimSpace(c)
			if c == "" {
				continue
			}

			if cVal, err := strconv.Atoi(c); err == nil {
				if cVal == len(availableBlocks)+1 {
					// 全选
					selected = availableBlocks
					if useColor {
						fmt.Printf("%s✅ 已全选所有方块%s\n", utils.Green, utils.Reset)
					} else {
						fmt.Printf("✅ 已全选所有方块\n")
					}
					break
				} else if cVal == len(availableBlocks)+2 {
					// 取消全选
					selected = []string{}
					if useColor {
						fmt.Printf("%s✅ 已取消全选%s\n", utils.Yellow, utils.Reset)
					} else {
						fmt.Printf("✅ 已取消全选\n")
					}
					break
				} else if cVal >= 1 && cVal <= len(availableBlocks) {
					selected = append(selected, availableBlocks[cVal-1])
				} else {
					fmt.Printf("%s❌ 无效的选择: %s%s\n", utils.Red, c, utils.Reset)
				}
			} else {
				// 检查是否是块名
				found := false
				for _, block := range availableBlocks {
					if block == c {
						selected = append(selected, block)
						found = true
						break
					}
				}
				if !found {
					fmt.Printf("%s❌ 无效的方块类型: %s%s\n", utils.Red, c, utils.Reset)
				}
			}
		}

		if len(selected) > 0 {
			var selectedNames []string
			for _, block := range selected {
				chineseName := blocksInfo[block]
				if useColor {
					selectedNames = append(selectedNames, fmt.Sprintf("%s%s%s(%s)", utils.Green, block, utils.Reset, chineseName))
				} else {
					selectedNames = append(selectedNames, fmt.Sprintf("%s(%s)", block, chineseName))
				}
			}
			if useColor {
				fmt.Printf("%s✅ 已选择: %s%s\n", utils.Green, strings.Join(selectedNames, ", "), utils.Reset)
			} else {
				fmt.Printf("✅ 已选择: %s\n", strings.Join(selectedNames, ", "))
			}
			break
		}
	}

	return selected
}

// GetAvailableBlocks 获取可用的方块类型及其显示名称
func GetAvailableBlocks() map[string]string {
	blockDir := "block"
	blocksInfo := make(map[string]string)

	if _, err := os.Stat(blockDir); os.IsNotExist(err) {
		// 如果目录不存在，创建它并返回默认值
		os.MkdirAll(blockDir, 0755)
		CreateDefaultBlockFiles()
		return map[string]string{
			"wool":     "羊毛",
			"concrete": "混凝土",
		}
	}

	files, err := os.ReadDir(blockDir)
	if err != nil {
		return map[string]string{
			"wool":     "羊毛",
			"concrete": "混凝土",
		}
	}

	for _, file := range files {
		if strings.HasSuffix(file.Name(), ".json") {
			blockName := strings.TrimSuffix(file.Name(), ".json")
			displayName := GetBlockDisplayName(filepath.Join(blockDir, file.Name()))
			blocksInfo[blockName] = displayName
		}
	}

	return blocksInfo
}

// GetBlockDisplayName 从JSON文件的第一行注释中获取方块类型的中文名称
func GetBlockDisplayName(blockFile string) string {
	file, err := os.Open(blockFile)
	if err != nil {
		return filepath.Base(blockFile)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	if scanner.Scan() {
		firstLine := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(firstLine, "# ") {
			return firstLine[2:]
		}
	}

	return filepath.Base(blockFile)
}

// CreateDefaultBlockFiles 创建默认的方块映射文件
func CreateDefaultBlockFiles() {
	blockDir := "block"
	os.MkdirAll(blockDir, 0755)

	// 创建默认的wool.json
	woolContent := `# 羊毛方块
{
  "(255, 255, 255)": ["minecraft:white_wool", "0"],
  "(255, 255, 178)": ["minecraft:light_gray_wool", "0"],
  "(178, 178, 178)": ["minecraft:gray_wool", "0"],
  "(102, 102, 102)": ["minecraft:black_wool", "0"],
  "(255, 178, 178)": ["minecraft:pink_wool", "0"],
  "(255, 102, 102)": ["minecraft:red_wool", "0"],
  "(255, 178, 102)": ["minecraft:orange_wool", "0"],
  "(255, 255, 0)": ["minecraft:yellow_wool", "0"],
  "(178, 255, 102)": ["minecraft:lime_wool", "0"],
  "(102, 255, 102)": ["minecraft:green_wool", "0"],
  "(102, 255, 255)": ["minecraft:cyan_wool", "0"],
  "(102, 178, 255)": ["minecraft:light_blue_wool", "0"],
  "(102, 102, 255)": ["minecraft:blue_wool", "0"],
  "(178, 102, 255)": ["minecraft:purple_wool", "0"],
  "(255, 102, 255)": ["minecraft:magenta_wool", "0"],
  "(178, 76, 0)": ["minecraft:brown_wool", "0"]
}`

	concreteContent := `# 混凝土方块
{
  "(255, 255, 255)": ["minecraft:white_concrete", "0"],
  "(255, 255, 178)": ["minecraft:light_gray_concrete", "0"],
  "(178, 178, 178)": ["minecraft:gray_concrete", "0"],
  "(102, 102, 102)": ["minecraft:black_concrete", "0"],
  "(255, 178, 178)": ["minecraft:pink_concrete", "0"],
  "(255, 102, 102)": ["minecraft:red_concrete", "0"],
  "(255, 178, 102)": ["minecraft:orange_concrete", "0"],
  "(255, 255, 0)": ["minecraft:yellow_concrete", "0"],
  "(178, 255, 102)": ["minecraft:lime_concrete", "0"],
  "(102, 255, 102)": ["minecraft:green_concrete", "0"],
  "(102, 255, 255)": ["minecraft:cyan_concrete", "0"],
  "(102, 178, 255)": ["minecraft:light_blue_concrete", "0"],
  "(102, 102, 255)": ["minecraft:blue_concrete", "0"],
  "(178, 102, 255)": ["minecraft:purple_concrete", "0"],
  "(255, 102, 255)": ["minecraft:magenta_concrete", "0"],
  "(178, 76, 0)": ["minecraft:brown_concrete", "0"]
}`

	os.WriteFile(filepath.Join(blockDir, "wool.json"), []byte(woolContent), 0644)
	os.WriteFile(filepath.Join(blockDir, "concrete.json"), []byte(concreteContent), 0644)
}

// RunInteractiveMode 运行交互式模式
func RunInteractiveMode(resourceMonitor *utils.ResourceMonitor, showLogoAndAnnouncement bool) {
	converter := &InteractiveConverter{
		depth:    1,
		useColor: true, // 默认启用彩色输出
	}

	// 加载配置
	interactiveCfg, err := config.LoadConfig("config.json")
	if err != nil {
		fmt.Printf("⚠️  加载配置失败: %v\n", err)
		interactiveCfg = &config.Config{} // 使用默认配置
	}

	fmt.Printf("%s⚙️  使用配置: 语言=%s, 输出目录=%s%s\n", utils.Cyan, interactiveCfg.General.Language, interactiveCfg.General.OutputDirectory, utils.Reset)

	// 根据参数决定是否显示logo和公告
	if showLogoAndAnnouncement {
		// 显示logo
		DisplayLogo(interactiveCfg)

		// 显示最新公告（如果配置启用）
		if interactiveCfg.Features.ShowAnnouncement {
			utils.DisplayAnnouncement()
		}
	}

	// 询问是否启用自动验证
	enableVerification := format.AskAutoVerification()

	// 获取用户输入
	inputPath, outputSchem, width, height, selectedBlocks, outputFormat := GetUserInput(interactiveCfg)

	// 根据选择的格式获取转换器
	converterManager := format.NewConverterManager()
	converterInterface, err := converterManager.GetConverter(outputFormat)
	if err != nil {
		errorMsg := fmt.Sprintf("❌ 无法获取 %s 转换器: %v\n", outputFormat, err)
		utils.PrintColoredTextBlock(errorMsg, utils.RGBColor{R: 255, G: 0, B: 0}, converter.useColor)
		return
	}

	fmt.Println("\n🔄 开始转换...")
	startTime := time.Now()

	// 设置进度回调函数
	converterInterface.SetProgressCallback(func(current, total int, message string) {
		utils.DisplayProgressBar(current, total, message, interactiveCfg.UI.ColoredOutput)
	})

	// 执行转换
	err = converterInterface.Convert(inputPath, outputSchem, width, height, selectedBlocks)
	if err != nil {
		errorMsg := fmt.Sprintf("❌ 转换失败: %v\n", err)
		utils.PrintColoredTextBlock(errorMsg, utils.RGBColor{R: 255, G: 0, B: 0}, converter.useColor)
		return
	}

	elapsed := time.Since(startTime)
	useColor := interactiveCfg.UI.ColoredOutput

	// 显示转换统计信息
	var calculatedBlockCount int
	var calculatedSelectedNames []string
	
	if useColor {
		fmt.Printf("\n%s✅ 转换成功完成! 耗时: %.2f秒%s\n", utils.Green, elapsed.Seconds(), utils.Reset)
		fmt.Printf("%s%s%s\n", utils.Cyan, strings.Repeat("=", 50), utils.Reset)
		fmt.Printf("%s📐 生成结构尺寸: %d × %d 方块%s\n", utils.Yellow, width, height, utils.Reset)
		// 这里我们简单地计算方块数量，实际转换器可能需要返回这个信息
		calculatedBlockCount = width * height
		fmt.Printf("%s🧱 总方块数量: %d 个%s\n", utils.Yellow, calculatedBlockCount, utils.Reset)
		fmt.Printf("%s💾 输出文件: %s%s\n", utils.Yellow, outputSchem, utils.Reset)

		// 显示使用的方块类型中文名
		blocksInfo := GetAvailableBlocks()
		for _, block := range selectedBlocks {
			chineseName, exists := blocksInfo[block]
			if !exists {
				chineseName = block
			}
			calculatedSelectedNames = append(calculatedSelectedNames, fmt.Sprintf("%s%s%s(%s)", utils.Green, block, utils.Reset, chineseName))
		}
		fmt.Printf("%s🎨 使用的方块类型: %s%s\n", utils.Yellow, strings.Join(calculatedSelectedNames, ", "), utils.Reset)
		fmt.Printf("%s%s%s\n", utils.Cyan, strings.Repeat("=", 50), utils.Reset)
	} else {
		fmt.Printf("\n✅ 转换成功完成! 耗时: %.2f秒\n", elapsed.Seconds())
		fmt.Printf("%s\n", strings.Repeat("=", 50))
		fmt.Printf("📐 生成结构尺寸: %d × %d 方块\n", width, height)
		calculatedBlockCount = width * height
		fmt.Printf("🧱 总方块数量: %d 个\n", calculatedBlockCount)
		fmt.Printf("💾 输出文件: %s\n", outputSchem)

		// 显示使用的方块类型中文名
		blocksInfo := GetAvailableBlocks()
		for _, block := range selectedBlocks {
			chineseName, exists := blocksInfo[block]
			if !exists {
				chineseName = block
			}
			calculatedSelectedNames = append(calculatedSelectedNames, fmt.Sprintf("%s(%s)", block, chineseName))
		}
		fmt.Printf("🎨 使用的方块类型: %s\n", strings.Join(calculatedSelectedNames, ", "))
		fmt.Printf("%s\n", strings.Repeat("=", 50))
	}

	// 如果启用了验证且输出格式为schem，进行验证
	if enableVerification && outputFormat == "schem" {
		isValid, message := format.VerifySchemFile(outputSchem)

		if !isValid {
			fmt.Printf("\n⚠️  文件验证发现问题: %s\n", message)

			var fixChoice string
			fmt.Print("🔧 是否尝试自动修复? (y/n, 回车默认为y): ")
			
			// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理输入
			scanner := bufio.NewScanner(os.Stdin)
			if scanner.Scan() {
				fixChoice = strings.TrimSpace(scanner.Text())
			} else {
				// 处理扫描错误，使用默认值
				fixChoice = "y"
			}

			if fixChoice == "" || fixChoice == "y" || fixChoice == "yes" || fixChoice == "Yes" {
				fixStart := time.Now()
				fixSuccess, fixMessage, backupPath := format.FixSchemFile(outputSchem, message)

				if fixSuccess {
					fixElapsed := time.Since(fixStart)
					if useColor {
						fmt.Printf("\n%s✅ 自动验证并修复成功完成! 耗时: %.2f秒%s\n", utils.Green, fixElapsed.Seconds(), utils.Reset)
						fmt.Printf("%s%s%s\n", utils.Cyan, strings.Repeat("=", 50), utils.Reset)
						fmt.Printf("%s📐 生成结构尺寸: %d × %d 方块%s\n", utils.Yellow, width, height, utils.Reset)
						fmt.Printf("%s🧱 总方块数量: %d 个%s\n", utils.Yellow, calculatedBlockCount, utils.Reset)
						fmt.Printf("%s📁 原输出文件: %s%s\n", utils.Cyan, backupPath, utils.Reset)
						fmt.Printf("%s💾 输出文件: %s%s\n", utils.Yellow, outputSchem, utils.Reset)
						fmt.Printf("%s🔧 修复内容: %s%s\n", utils.Green, fixMessage, utils.Reset)
						fmt.Printf("%s🎨 使用的方块类型: %s%s\n", utils.Yellow, strings.Join(calculatedSelectedNames, ", "), utils.Reset)
						fmt.Printf("%s%s%s\n", utils.Cyan, strings.Repeat("=", 50), utils.Reset)
					} else {
						fmt.Printf("\n✅ 自动验证并修复成功完成! 耗时: %.2f秒\n", fixElapsed.Seconds())
						fmt.Printf("%s\n", strings.Repeat("=", 50))
						fmt.Printf("📐 生成结构尺寸: %d × %d 方块\n", width, height)
						fmt.Printf("🧱 总方块数量: %d 个\n", calculatedBlockCount)
						fmt.Printf("📁 原输出文件: %s\n", backupPath)
						fmt.Printf("💾 输出文件: %s\n", outputSchem)
						fmt.Printf("🔧 修复内容: %s\n", fixMessage)
						fmt.Printf("🎨 使用的方块类型: %s\n", strings.Join(calculatedSelectedNames, ", "))
						fmt.Printf("%s\n", strings.Repeat("=", 50))
					}

					fmt.Println("\n🔍 验证修复后的文件...")
					isAfterFixValid, finalMessage := format.VerifySchemFile(outputSchem)

					if isAfterFixValid {
						if useColor {
							fmt.Printf("%s✅ 修复后文件验证通过%s\n", utils.Green, utils.Reset)
						} else {
							fmt.Printf("✅ 修复后文件验证通过\n")
						}
					} else {
						fmt.Printf("❌ 修复后文件仍然存在问题: %s\n", finalMessage)
					}
				} else {
					fmt.Printf("❌ 修复失败: %s\n", fixMessage)
				}
			} else {
				fmt.Println("⚠️  用户选择不进行修复")
		}
		} else {
			if useColor {
				fmt.Printf("%s✅ 文件验证通过，无需修复%s\n", utils.Green, utils.Reset)
			} else {
				fmt.Printf("✅ 文件验证通过，无需修复\n")
			}
		}
	}

	successMsg := fmt.Sprintf("🎉 转换完成: %s", outputSchem)
	utils.PrintGradientText(successMsg, utils.RGBColor{R: 50, G: 205, B: 50}, utils.RGBColor{R: 30, G: 144, B: 255}, converter.useColor)
	fmt.Println()

	// 显示资源使用情况
	resourceMonitor.ShowMaxResourceUsage()
}

// DisplayLogo 显示程序logo
func DisplayLogo(cfg *config.Config) {
	// 获取用户偏好设置，但确保即使在无颜色模式下也显示logo（仅使用ASCII字符）
	useColor := cfg.UI.ColoredOutput

	logo := []string{
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
		"╚═════════════════════════════════════════════╝",
	}

	// 使用与Python版本一致的渐变色显示logo，如果支持彩色输出
	if useColor {
		gradient := utils.GetGradientColors256ColorMode(len(logo), useColor)
		resetColor := utils.Reset
		for i, line := range logo {
			if i < len(gradient) {
				fmt.Printf("%s%s%s\n", gradient[i], line, resetColor)
			} else {
				fmt.Println(line)
			}
		}
	} else {
		for _, line := range logo {
			fmt.Println(line)
		}
	}

	// 显示项目信息
	info := []string{
		"┌───────────────────────────────────────────┐",
		"│         Open source - SunPixel            │",
		"│ https://github.com/suibian-sun/SunPixel   │",
		"└───────────────────────────────────────────┘",
		"Authors: suibian-sun",
	}

	if useColor {
		infoGradient := utils.GetGradientColors256ColorMode(len(info), useColor)
		resetColor := utils.Reset
		for i, line := range info {
			if i < len(infoGradient) {
				fmt.Printf("%s%s%s\n", infoGradient[i], line, resetColor)
			} else {
				fmt.Println(line)
			}
		}
	} else {
		for _, line := range info {
			fmt.Println(line)
		}
	}
}

// ShowSettingsMenu 显示设置菜单
func ShowSettingsMenu(cfg *config.Config) {
	useColor := cfg.UI.ColoredOutput

	fmt.Println()
	fmt.Printf("%s%s%s\n", utils.Cyan, strings.Repeat("=", 50), utils.Reset)
	if useColor {
		fmt.Printf("%s⚙️  SunPixel 设置菜单%s\n", utils.Cyan, utils.Reset)
	} else {
		fmt.Println("⚙️  SunPixel 设置菜单")
	}
	fmt.Printf("%s%s%s\n", utils.Cyan, strings.Repeat("=", 50), utils.Reset)

	for {
		fmt.Printf("\n1. 查看当前配置\n")
		fmt.Printf("2. 修改输出目录\n")
		fmt.Printf("3. 切换控制台颜色 (当前: %s)\n", map[bool]string{true: "启用", false: "禁用"}[useColor])
		fmt.Printf("4. 修改语言设置 (当前: %s)\n", cfg.General.Language)
		fmt.Printf("5. 重置为默认配置\n")
		fmt.Printf("6. 保存并退出\n")
		fmt.Printf("7. 不保存退出\n")
		fmt.Printf("%s%s%s\n", utils.Yellow, strings.Repeat("-", 30), utils.Reset)

		var choice string
		fmt.Print("请选择操作 (1-7): ")
		
		// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理输入
		scanner := bufio.NewScanner(os.Stdin)
		if scanner.Scan() {
			choice = strings.TrimSpace(scanner.Text())
		} else {
			// 处理扫描错误
			fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
			continue
		}

		switch choice {
		case "1":
			fmt.Printf("\n%s📋 当前配置:%s\n", utils.Green, utils.Reset)
			fmt.Printf("   输出目录: %s\n", cfg.General.OutputDirectory)
			fmt.Printf("   控制台颜色: %s\n", map[bool]string{true: "启用", false: "禁用"}[useColor])
			fmt.Printf("   语言设置: %s\n", cfg.General.Language)

		case "2":
			var newDir string
			fmt.Print("请输入新的输出目录路径: ")
			
			// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理包含空格和中文字符的路径
			scanner := bufio.NewScanner(os.Stdin)
			if scanner.Scan() {
				newDir = strings.TrimSpace(scanner.Text())
			} else {
				// 处理扫描错误
				fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
				continue
			}
			if newDir != "" {
				cfg.General.OutputDirectory = newDir
				if useColor {
					fmt.Printf("%s✅ 输出目录已更新为: %s%s\n", utils.Green, newDir, utils.Reset)
				} else {
					fmt.Printf("✅ 输出目录已更新为: %s\n", newDir)
				}
			}

		case "3":
			cfg.UI.ColoredOutput = !cfg.UI.ColoredOutput
			useColor = cfg.UI.ColoredOutput
			if useColor {
				fmt.Printf("%s✅ 控制台颜色已启用%s\n", utils.Green, utils.Reset)
			} else {
				fmt.Printf("%s✅ 控制台颜色已禁用%s\n", utils.Green, utils.Reset)
			}

		case "4":
			fmt.Printf("\n%s🗣️  选择语言:%s\n", utils.Yellow, utils.Reset)
			fmt.Printf("1. 中文 (zh_CN)\n")
			fmt.Printf("2. English (en_US)\n")
			fmt.Printf("3. Français (fr_FR)\n")
			fmt.Printf("4. Русский (ru_RU)\n")

			var langChoice string
			fmt.Print("请选择语言 (1-4): ")
			
			// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理输入
			scanner := bufio.NewScanner(os.Stdin)
			if scanner.Scan() {
				langChoice = strings.TrimSpace(scanner.Text())
			} else {
				// 处理扫描错误
				fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
				continue
			}

			switch langChoice {
			case "1":
				cfg.General.Language = "zh_CN"
				fmt.Printf("✅ 语言已设置为中文\n")
			case "2":
				cfg.General.Language = "en_US"
				fmt.Printf("✅ 语言已设置为English\n")
			case "3":
				cfg.General.Language = "fr_FR"
				fmt.Printf("✅ 语言已设置为Français\n")
			case "4":
				cfg.General.Language = "ru_RU"
				fmt.Printf("✅ 语言已设置为Русский\n")
			default:
				fmt.Printf("⚠️  保持当前语言设置\n")
			}

		case "5":
			var confirm string
			fmt.Print("⚠️  确定要重置为默认配置吗? (y/n): ")
			
			// 使用 bufio.Scanner 替代 fmt.Scanln 以正确处理输入
			scanner := bufio.NewScanner(os.Stdin)
			if scanner.Scan() {
				confirm = strings.TrimSpace(scanner.Text())
			} else {
				// 处理扫描错误
				fmt.Printf("%s❌ 读取输入失败%s\n", utils.Red, utils.Reset)
				continue
			}
			if confirm == "y" || confirm == "Y" || confirm == "yes" || confirm == "Yes" {
				*cfg = config.Config{}
				cfg.General.Language = "zh_CN"
				cfg.General.OutputDirectory = "output"
				cfg.UI.ColoredOutput = true
				cfg.Features.AutoVerification = true
				cfg.Features.ShowAnnouncement = true
				useColor = cfg.UI.ColoredOutput
				fmt.Printf("✅ 配置已重置为默认值\n")
			}

		case "6":
			if err := cfg.SaveConfig("config.json"); err != nil {
				fmt.Printf("❌ 保存配置失败: %v\n", err)
			} else {
				fmt.Printf("✅ 配置已保存\n")
			}
			fmt.Printf("👋 返回主程序...\n")
			return

		case "7":
			// 重新加载配置，放弃更改
			loadedCfg, err := config.LoadConfig("config.json")
			if err != nil {
				fmt.Printf("⚠️  重新加载配置失败: %v\n", err)
			} else {
				*cfg = *loadedCfg
			}
			fmt.Printf("⚠️  更改未保存\n")
			fmt.Printf("👋 返回主程序...\n")
			return

		default:
			fmt.Printf("❌ 无效的选择，请重新输入\n")
		}
	}
}
