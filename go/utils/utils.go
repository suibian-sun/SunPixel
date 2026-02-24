package utils

import (
    "fmt"
    "math"
    "bufio"
    "os"
    "strconv"
    "strings"
    "time"
)

// ANSI颜色代码
const (
    Reset     = "\033[0m"
    Red       = "\033[31m"
    Green     = "\033[32m"
    Yellow    = "\033[33m"
    Blue      = "\033[34m"
    Magenta   = "\033[35m"
    Cyan      = "\033[36m"
    White     = "\033[37m"
    Bold      = "\033[1m"
    BackgroundReset = "\033[49m"
)

// 进度条更新时间间隔（毫秒）
const ProgressBarUpdateInterval = 100 // 100毫秒，即每0.1秒最多更新一次

// 全局变量跟踪进度条最后更新时间
var lastProgressBarUpdate time.Time

// RGBColor 表示RGB颜色
type RGBColor struct {
    R, G, B uint8
}

// RGBToANSIColor 将RGB颜色转换为ANSI颜色代码
func RGBToANSIColor(r, g, b uint8) string {
    return fmt.Sprintf("\033[38;2;%d;%d;%dm", r, g, b)
}

// RGBToANSIBackground 将RGB颜色转换为ANSI背景色代码
func RGBToANSIBackground(r, g, b uint8) string {
    return fmt.Sprintf("\033[48;2;%d;%d;%dm", r, g, b)
}

// ColoredPrint 使用指定颜色输出文本
func ColoredPrint(colorCode, text string, useColor bool) string {
    if useColor {
        return fmt.Sprintf("%s%s%s", colorCode, text, Reset)
    }
    return text
}

// ColoredPrintf 使用颜色格式化输出
func ColoredPrintf(colorCode, format string, useColor bool, a ...interface{}) string {
    if useColor {
        return fmt.Sprintf("%s%s%s", colorCode, fmt.Sprintf(format, a...), Reset)
    }
    return fmt.Sprintf(format, a...)
}

// ColoredBackgroundPrint 使用指定背景色输出文本
func ColoredBackgroundPrint(colorCode, text string, useColor bool) string {
    if useColor {
        return fmt.Sprintf("%s%s%s", colorCode, text, BackgroundReset)
    }
    return text
}

// GenerateGradientColors 生成从start到end的渐变颜色序列
func GenerateGradientColors(start, end RGBColor, steps int) []RGBColor {
    if steps <= 0 {
        return []RGBColor{}
    }
    if steps == 1 {
        return []RGBColor{start}
    }
    
    colors := make([]RGBColor, steps)
    for i := 0; i < steps; i++ {
        ratio := float64(i) / float64(steps-1)
        r := uint8(float64(start.R) + ratio*float64(end.R-start.R))
        g := uint8(float64(start.G) + ratio*float64(end.G-start.G))
        b := uint8(float64(start.B) + ratio*float64(end.B-start.B))
        colors[i] = RGBColor{R: r, G: g, B: b}
    }
    return colors
}

// GetGradientColors256ColorMode 生成256色模式的渐变颜色序列（与Python版本保持一致）
func GetGradientColors256ColorMode(numColors int, useColor bool) []string {
    if !useColor {
        return make([]string, numColors)
    }

    gradientColors := []string{
        "\033[38;5;27m",   // 深蓝
        "\033[38;5;33m",   // 蓝色
        "\033[38;5;39m",   // 亮蓝
        "\033[38;5;45m",   // 青蓝
        "\033[38;5;51m",   // 青色
        "\033[38;5;50m",   // 蓝绿
        "\033[38;5;49m",   // 绿青
        "\033[38;5;48m",   // 青色
        "\033[38;5;129m",  // 紫色
        "\033[38;5;165m",  // 亮紫
        "\033[38;5;201m",  // 粉紫
        "\033[38;5;207m",  // 粉色
        "\033[38;5;213m",  // 亮粉
        "\033[38;5;219m",  // 浅粉
    }

    if numColors <= len(gradientColors) {
        return gradientColors[:numColors]
    }

    result := make([]string, numColors)
    for i := 0; i < numColors; i++ {
        pos := float64(i) / float64(numColors-1) * float64(len(gradientColors)-1)
        idx := int(pos)
        if idx >= len(gradientColors) {
            idx = len(gradientColors) - 1
        }
        result[i] = gradientColors[idx]
    }

    return result
}

// GenerateRainbowColors 生成彩虹渐变色
func GenerateRainbowColors(steps int) []RGBColor {
    if steps <= 0 {
        return []RGBColor{}
    }
    
    colors := make([]RGBColor, steps)
    for i := 0; i < steps; i++ {
        hue := float64(i) / float64(steps)
        r, g, b := HSLToRGB(hue, 1.0, 0.5)
        colors[i] = RGBColor{R: uint8(r * 255), G: uint8(g * 255), B: uint8(b * 255)}
    }
    return colors
}

// HSLToRGB 将HSL颜色空间转换为RGB
func HSLToRGB(h, s, l float64) (float64, float64, float64) {
    var r, g, b float64

    if s == 0 {
        r, g, b = l, l, l
    } else {
        var hue2rgb = func(p, q, t float64) float64 {
            if t < 0 {
                t += 1
            }
            if t > 1 {
                t -= 1
            }
            if t < 1.0/6.0 {
                return p + (q-p)*6*t
            }
            if t < 1.0/2.0 {
                return q
            }
            if t < 2.0/3.0 {
                return p + (q-p)*(2.0/3.0-t)*6
            }
            return p
        }

        var q float64
        if l < 0.5 {
            q = l * (1 + s)
        } else {
            q = l + s - l*s
        }
        p := 2*l - q
        r = hue2rgb(p, q, h+1.0/3.0)
        g = hue2rgb(p, q, h)
        b = hue2rgb(p, q, h-1.0/3.0)
    }

    return r, g, b
}

// ColorDistance 计算两个颜色之间的距离
func ColorDistance(c1, c2 RGBColor) float64 {
    dr := float64(c1.R - c2.R)
    dg := float64(c1.G - c2.G)
    db := float64(c1.B - c2.B)
    return math.Sqrt(dr*dr + dg*dg + db*db)
}

// FindClosestColor 在颜色列表中找到最接近目标颜色的颜色
func FindClosestColor(target RGBColor, colorList []RGBColor) RGBColor {
    if len(colorList) == 0 {
        return RGBColor{0, 0, 0}
    }
    
    minDistance := ColorDistance(target, colorList[0])
    closestColor := colorList[0]
    
    for _, c := range colorList[1:] {
        distance := ColorDistance(target, c)
        if distance < minDistance {
            minDistance = distance
            closestColor = c
        }
    }
    
    return closestColor
}

// PrintColoredTextBlock 使用彩色背景打印文本块
func PrintColoredTextBlock(text string, bgColor RGBColor, useColor bool) {
    if useColor {
        bgCode := RGBToANSIBackground(bgColor.R, bgColor.G, bgColor.B)
        fmt.Printf("%s%s%s", bgCode, text, BackgroundReset)
    } else {
        fmt.Print(text)
    }
}

// PrintGradientText 打印渐变色文本
func PrintGradientText(text string, startColor, endColor RGBColor, useColor bool) {
    if !useColor || len(text) == 0 {
        fmt.Print(text)
        return
    }
    
    gradientColors := GenerateGradientColors(startColor, endColor, len(text))
    for i, char := range text {
        colorCode := RGBToANSIColor(gradientColors[i].R, gradientColors[i].G, gradientColors[i].B)
        fmt.Printf("%s%c%s", colorCode, char, Reset)
    }
}

// PrintRainbowText 打印彩虹色文本
func PrintRainbowText(text string, useColor bool) {
    if !useColor || len(text) == 0 {
        fmt.Print(text)
        return
    }
    
    rainbowColors := GenerateRainbowColors(len(text))
    for i, char := range text {
        colorCode := RGBToANSIColor(rainbowColors[i].R, rainbowColors[i].G, rainbowColors[i].B)
        fmt.Printf("%s%c%s", colorCode, char, Reset)
    }
}

// GetUserInput 获取用户输入，带有默认值
func GetUserInput(prompt string, defaultValue string, useColor bool) string {
    if useColor {
        startColor := RGBColor{R: 135, G: 206, B: 250} // Light Sky Blue
        endColor := RGBColor{R: 70, G: 130, B: 180}   // Steel Blue
        PrintGradientText(prompt, startColor, endColor, useColor)
    } else {
        fmt.Print(prompt)
    }
    
    if defaultValue != "" {
        if useColor {
            gray := RGBColor{R: 128, G: 128, B: 128}
            defaultText := fmt.Sprintf(" (默认: %s)", defaultValue)
            PrintColoredTextBlock(defaultText, gray, useColor)
        } else {
            fmt.Printf(" (默认: %s)", defaultValue)
        }
    }
    
    if useColor {
        fmt.Print(Reset)
    }
    fmt.Print(": ")
    
    scanner := bufio.NewScanner(os.Stdin)
    scanner.Scan()
    input := strings.TrimSpace(scanner.Text())
    
    if input == "" && defaultValue != "" {
        return defaultValue
    }
    
    return input
}

// GetUserInputInt 获取用户输入的整数，带有默认值
func GetUserInputInt(prompt string, defaultValue int, useColor bool) int {
    for {
        inputStr := GetUserInput(prompt, strconv.Itoa(defaultValue), useColor)
        
        if inputStr == "" {
            return defaultValue
        }
        
        value, err := strconv.Atoi(inputStr)
        if err != nil {
            if useColor {
                red := RGBColor{R: 255, G: 0, B: 0}
                errorMsg := "输入无效，请输入一个整数\n"
                PrintColoredTextBlock(errorMsg, red, useColor)
            } else {
                fmt.Println("输入无效，请输入一个整数")
            }
            continue
        }
        
        return value
    }
}

// GetUserInputBool 获取用户输入的布尔值
func GetUserInputBool(prompt string, defaultValue bool, useColor bool) bool {
    defaultStr := "n"
    if defaultValue {
        defaultStr = "y"
    }
    
    for {
        input := GetUserInput(prompt, defaultStr, useColor)
        input = strings.ToLower(input)
        
        switch input {
        case "y", "yes", "是", "1", "true", "t":
            return true
        case "n", "no", "否", "0", "false", "f", "":
            return defaultValue // Return default if empty
        default:
            if useColor {
                red := RGBColor{R: 255, G: 0, B: 0}
                errorMsg := "输入无效，请输入 y(是) 或 n(否)\n"
                PrintColoredTextBlock(errorMsg, red, useColor)
            } else {
                fmt.Println("输入无效，请输入 y(是) 或 n(否)")
            }
        }
    }
}

// GetUserInputList 获取用户输入的列表（逗号分隔）
func GetUserInputList(prompt string, defaultValue []string, useColor bool) []string {
    defaultStr := strings.Join(defaultValue, ",")
    input := GetUserInput(prompt, defaultStr, useColor)
    
    if input == "" {
        return defaultValue
    }
    
    items := strings.Split(input, ",")
    for i, item := range items {
        items[i] = strings.TrimSpace(item)
    }
    
    return items
}

// PrintSectionTitle 打印带渐变色的章节标题
func PrintSectionTitle(title string, useColor bool) {
    if useColor {
        startColor := RGBColor{R: 50, G: 205, B: 50}   // LimeGreen
        endColor := RGBColor{R: 34, G: 139, B: 34}    // ForestGreen
        fmt.Println()
        PrintGradientText("════════════════════════════════════════", startColor, endColor, useColor)
        fmt.Println()
        PrintGradientText(title, startColor, endColor, useColor)
        fmt.Println()
        PrintGradientText("════════════════════════════════════════", startColor, endColor, useColor)
        fmt.Println()
    } else {
        fmt.Printf("\n════════════════════════════════════════\n")
        fmt.Printf("%s\n", title)
        fmt.Printf("════════════════════════════════════════\n\n")
    }
}

// PrintChoiceOption 打印选择选项
func PrintChoiceOption(index int, option string, useColor bool) {
    if useColor {
        cyan := RGBColor{R: 0, G: 255, B: 255}
        optionText := fmt.Sprintf("%d. %s", index, option)
        PrintColoredTextBlock(optionText, cyan, useColor)
        fmt.Println()
    } else {
        fmt.Printf("%d. %s\n", index, option)
    }
}

// GetUserChoice 让用户从多个选项中选择一个
func GetUserChoice(prompt string, options []string, defaultValue int, useColor bool) int {
    if useColor {
        yellow := RGBColor{R: 255, G: 255, B: 0}
        PrintColoredTextBlock(prompt, yellow, useColor)
    } else {
        fmt.Print(prompt)
    }
    
    if defaultValue >= 0 && defaultValue < len(options) {
        if useColor {
            gray := RGBColor{R: 128, G: 128, B: 128}
            defaultText := fmt.Sprintf(" (默认: %d - %s)", defaultValue+1, options[defaultValue])
            PrintColoredTextBlock(defaultText, gray, useColor)
        } else {
            fmt.Printf(" (默认: %d - %s)", defaultValue+1, options[defaultValue])
        }
    }
    
    fmt.Println(":")
    
    for i, option := range options {
        PrintChoiceOption(i+1, option, useColor)
    }
    
    for {
        input := GetUserInput("请输入选项编号", "", useColor)
        
        if input == "" && defaultValue >= 0 {
            return defaultValue
        }
        
        choice, err := strconv.Atoi(input)
        if err != nil || choice < 1 || choice > len(options) {
            if useColor {
                red := RGBColor{R: 255, G: 0, B: 0}
                errorMsg := "输入无效，请输入一个有效的选项编号\n"
                PrintColoredTextBlock(errorMsg, red, useColor)
            } else {
                fmt.Println("输入无效，请输入一个有效的选项编号")
            }
            continue
        }
        
        return choice - 1
    }
}

// Max 返回两个整数中的较大值
func Max(a, b int) int {
    if a > b {
        return a
    }
    return b
}

// DisplayProgressBar 显示进度条
func DisplayProgressBar(current, total int, message string, useColor bool) {
    if total <= 0 {
        return
    }
    
    // 限制更新频率，防止刷屏
    now := time.Now()
    if current < total { // 只有在未完成时才限制更新频率
        if now.Sub(lastProgressBarUpdate) < time.Duration(ProgressBarUpdateInterval)*time.Millisecond {
            // 如果未达到更新间隔，但进度完成，则仍然显示
            if current < total {
                return
            }
        }
    }
    
    // 更新最后更新时间
    lastProgressBarUpdate = now
    
    percentage := float64(current) / float64(total) * 100
    barLength := 50
    filledLength := int(float64(barLength) * float64(current) / float64(total))
    
    var bar string
    if useColor {
        bar = fmt.Sprintf("%s[%s%s%s]%s", 
            Cyan,
            Green+strings.Repeat("█", filledLength),
            Yellow+strings.Repeat("░", barLength-filledLength),
            Cyan,
            Reset)
    } else {
        bar = fmt.Sprintf("[%s%s]", 
            strings.Repeat("█", filledLength),
            strings.Repeat("░", barLength-filledLength))
    }
    
    // 清除当前行并显示进度条
    fmt.Printf("\r%s %s %.1f%% (%d/%d)", bar, message, percentage, current, total)
    
    // 如果完成，换行
    if current >= total {
        fmt.Println()
    }
}
