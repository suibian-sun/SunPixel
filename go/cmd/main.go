package main

import (
    "fmt"
    "os"
    "path/filepath"
    "strings"
    "time"
    
    "github.com/spf13/cobra"
    "sunpixel/config"
    "sunpixel/format"
    "sunpixel/interactive"
    "sunpixel/utils"
)

func main() {
    var inputFile string
    var outputFile string
    var outputFormat string
    var width, height int
    var selectedBlocks []string
    var interactiveMode bool
    
    var rootCmd = &cobra.Command{
        Use:   "sunpixel",
        Short: "SunPixel - 将图片转换为Minecraft结构文件",
        Long:  `SunPixel 是一个将图片转换为Minecraft结构文件（如schem、litematic等格式）的工具`,
        Run: func(cmd *cobra.Command, args []string) {
            // 检查命令行参数
            if contains(os.Args, "--set") {
                // 进入设置模式
                cfg, err := config.LoadConfig("config.json")
                if err != nil {
                    fmt.Printf("⚠️  加载配置失败: %v\n", err)
                    cfg = &config.Config{} // 使用默认配置
                }
                interactive.ShowSettingsMenu(cfg)
                return
            }
            
            // 创建资源监控器
            resourceMonitor := utils.NewResourceMonitor()
            
            // 初始化配置
            cfg, err := config.LoadConfig("config.json")
            if err != nil {
                fmt.Printf("⚠️  加载配置失败: %v\n", err)
                cfg = &config.Config{} // 使用默认配置
            }
            
            // 检查时间炸弹
            if !utils.CheckTimeBomb() {
                fmt.Println("\n❌ 程序无法运行，请检查有效期。")
                input := ""
                fmt.Print("按Enter键退出...")
                fmt.Scanln(&input)
                return
            }
            
            // 启动资源监控
            resourceMonitor.Start()
            
            // 检查是否启用交互模式，或者没有提供输入文件
            if interactiveMode || inputFile == "" {
                // 在交互模式中显示logo和公告，避免重复
                interactive.RunInteractiveMode(resourceMonitor, true) // 显示logo和公告
                return
            }
            
            // 非交互模式下显示logo和公告
            // 显示彩色logo
            interactive.DisplayLogo(cfg)
            
            // 显示最新公告（如果配置启用）
            if cfg.Features.ShowAnnouncement {
                utils.DisplayAnnouncement()
            }
            
            fmt.Printf("%s⚙️  使用配置: 语言=%s, 输出目录=%s%s\n", utils.Cyan, cfg.General.Language, cfg.General.OutputDirectory, utils.Reset)
            
            // 验证输入文件
            if _, err := os.Stat(inputFile); os.IsNotExist(err) {
                fmt.Printf("%s❌ 输入文件不存在: %s%s\n", utils.Red, inputFile, utils.Reset)
                os.Exit(1)
            }
            
            // 获取转换器管理器
            converterManager := format.NewConverterManager()
            
            // 获取可用格式列表
            availableFormats := converterManager.GetAvailableFormats()
            fmt.Printf("%s📦 可用格式: %v%s\n", utils.Yellow, availableFormats, utils.Reset)
            
            // 如果没有指定输出格式，默认为schem
            if outputFormat == "" {
                outputFormat = "schem"
            }
            
            // 获取指定格式的转换器
            converter, err := converterManager.GetConverter(outputFormat)
            if err != nil {
                fmt.Printf("%s❌ 不支持的格式: %s%s\n", utils.Red, outputFormat, utils.Reset)
                os.Exit(1)
            }
            
            // 设置输出文件路径
            if outputFile == "" {
                baseName := strings.TrimSuffix(filepath.Base(inputFile), filepath.Ext(inputFile))
                outputDir := cfg.General.OutputDirectory
                os.MkdirAll(outputDir, 0755)
                outputFile = filepath.Join(outputDir, baseName+converter.GetExtension())
            }
            
            // 如果没有选择方块类型，使用默认值
            if len(selectedBlocks) == 0 {
                selectedBlocks = []string{"wool", "concrete"}
            }
            
            fmt.Println("\n🔄 开始转换...")
            startTime := time.Now()
            
            // 设置进度回调函数
            converter.SetProgressCallback(func(current, total int, message string) {
                utils.DisplayProgressBar(current, total, message, cfg.UI.ColoredOutput)
            })
            
            // 执行转换
            err = converter.Convert(inputFile, outputFile, width, height, selectedBlocks)
            if err != nil {
                fmt.Printf("%s❌ 转换失败: %v%s\n", utils.Red, err, utils.Reset)
                os.Exit(1)
            }
            
            elapsed := time.Since(startTime)
            fmt.Printf("%s✅ 转换成功完成! 耗时: %.2f秒%s\n", utils.Green, elapsed.Seconds(), utils.Reset)
            
            // 询问是否启用自动验证（如果配置未设置默认值或用户选择启用）
            enableVerification := cfg.Features.AutoVerification
            if !cfg.Features.AutoVerification {
                enableVerification = format.AskAutoVerification()
            }
            
            if enableVerification && outputFormat == "schem" {
                // 验证schem文件
                isValid, message := format.VerifySchemFile(outputFile)
                
                if !isValid {
                    fmt.Printf("\n⚠️  文件验证发现问题: %s\n", message)
                    
                    var fixChoice string
                    fmt.Print("🔧 是否尝试自动修复? (y/n, 回车默认为y): ")
                    fmt.Scanln(&fixChoice)
                    
                    if fixChoice == "" || fixChoice == "y" || fixChoice == "yes" {
                        fixSuccess, fixMessage, backupPath := format.FixSchemFile(outputFile, message)
                        
                        if fixSuccess {
                            fmt.Printf("\n✅ 自动验证并修复成功完成!\n")
                            fmt.Printf("📁 原输出文件: %s\n", backupPath)
                            fmt.Printf("💾 输出文件: %s\n", outputFile)
                            fmt.Printf("🔧 修复内容: %s\n", fixMessage)
                            
                            // 验证修复后的文件
                            fmt.Println("\n🔍 验证修复后的文件...")
                            isAfterFixValid, finalMessage := format.VerifySchemFile(outputFile)
                            
                            if isAfterFixValid {
                                fmt.Printf("✅ 修复后文件验证通过\n")
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
                    fmt.Printf("✅ 文件验证通过，无需修复\n")
                }
            }
            
            fmt.Printf("%s✅ 转换完成: %s%s\n", utils.Green, outputFile, utils.Reset)
            
            // 显示资源使用情况
            resourceMonitor.ShowMaxResourceUsage()
        },
    }
    
    // 添加命令行标志
    rootCmd.Flags().StringVarP(&inputFile, "input", "i", "", "输入图片文件路径")
    rootCmd.Flags().StringVarP(&outputFile, "output", "o", "", "输出文件路径")
    rootCmd.Flags().StringVarP(&outputFormat, "format", "f", "schem", "输出格式 (schem, json)")
    rootCmd.Flags().IntVarP(&width, "width", "w", 0, "输出宽度")
    rootCmd.Flags().IntVarP(&height, "height", "H", 0, "输出高度")
    rootCmd.Flags().StringSliceVarP(&selectedBlocks, "blocks", "b", []string{}, "选择的方块类型 (如 wool,concrete)")
    rootCmd.Flags().BoolVarP(&interactiveMode, "interactive", "I", false, "启用交互式模式")
    rootCmd.Flags().Bool("set", false, "进入设置模式")
    
    if err := rootCmd.Execute(); err != nil {
        fmt.Printf("❌ 命令执行失败: %v\n", err)
        os.Exit(1)
    }
}

// Helper function to check if a slice contains a string
func contains(slice []string, item string) bool {
    for _, s := range slice {
        if s == item {
            return true
        }
    }
    return false
}
