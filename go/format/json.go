package format

import (
    "encoding/json"
    "fmt"
    "image"
    "image/color"
    "image/jpeg"
    "image/png"
    "io"
    "net/http"
    "os"
    "path/filepath"
    "strconv"
    "strings"
    
    "github.com/disintegration/imaging"
    "golang.org/x/image/webp"
    "sunpixel/utils"
)

// JSONConverter JSON格式转换器 (用于RunAway格式)
type JSONConverter struct {
    colorToBlock BlockColorMap
    colorInfos []ColorInfo  // 预解析的颜色信息，用于快速查找
    width        int
    height       int
    depth        int
    pixels       [][]color.NRGBA
    originalWidth  int
    originalHeight int
    progressCallback ProgressCallback
}

// GetFormatName 获取格式名称
func (j *JSONConverter) GetFormatName() string {
    return "json"
}

// GetExtension 获取文件扩展名
func (j *JSONConverter) GetExtension() string {
    return ".json"
}

// Convert 执行转换
func (j *JSONConverter) Convert(inputPath, outputPath string, width, height int, selectedBlocks []string) error {
    fmt.Printf("%s🚀 开始JSON格式转换...%s\n", utils.Blue, utils.Reset)
    
    // 加载方块映射
    if err := j.LoadBlockMappings(selectedBlocks); err != nil {
        return err
    }
    
    // 加载图片
    if err := j.LoadImage(inputPath); err != nil {
        return err
    }
    
    // 设置尺寸
    if width <= 0 || height <= 0 {
        j.SetSize(j.originalWidth, j.originalHeight)
    } else {
        j.SetSize(width, height)
    }
    
    // 生成结构数据
    structureData := j.generateJSONStructure()
    
    // 创建输出目录
    outputDir := filepath.Dir(outputPath)
    if err := os.MkdirAll(outputDir, 0755); err != nil {
        return err
    }
    
    // 保存JSON文件
    file, err := os.Create(outputPath)
    if err != nil {
        return err
    }
    defer file.Close()
    
    encoder := json.NewEncoder(file)
    encoder.SetIndent("", "  ")
    if err := encoder.Encode(structureData); err != nil {
        return err
    }
    
    fmt.Printf("%s✅ JSON文件保存完成: %s%s\n", utils.Green, outputPath, utils.Reset)
    return nil
}

// LoadBlockMappings 加载方块映射
func (j *JSONConverter) LoadBlockMappings(selectedBlocks []string) error {
    j.colorToBlock = make(BlockColorMap)
    j.colorInfos = make([]ColorInfo, 0)  // 初始化预解析颜色信息
    blockDir := "block"
    
    if _, err := os.Stat(blockDir); os.IsNotExist(err) {
        fmt.Printf("%s❌ 错误: block目录不存在!%s\n", utils.Red, utils.Reset)
        return err
    }
    
    // 读取所有JSON文件
    files, err := os.ReadDir(blockDir)
    if err != nil {
        return err
    }
    
    for _, file := range files {
        if strings.HasSuffix(file.Name(), ".json") {
            blockName := strings.TrimSuffix(file.Name(), ".json")
            
            // 检查是否在选中的方块列表中
            if len(selectedBlocks) > 0 {
                found := false
                for _, selected := range selectedBlocks {
                    if selected == blockName {
                        found = true
                        break
                    }
                }
                if !found {
                    continue
                }
            }
            
            filePath := filepath.Join(blockDir, file.Name())
            data, err := os.ReadFile(filePath)
            if err != nil {
                fmt.Printf("%s⚠️  无法读取文件 %s: %v%s\n", utils.Yellow, filePath, err, utils.Reset)
                continue
            }
            
            // 解析JSON，跳过注释行
            lines := strings.Split(string(data), "\n")
            var jsonData strings.Builder
            for _, line := range lines {
                if !strings.HasPrefix(strings.TrimSpace(line), "#") {
                    jsonData.WriteString(line)
                    jsonData.WriteString("\n")
                }
            }
            
            var blockData map[string][]interface{}
            if err := json.Unmarshal([]byte(jsonData.String()), &blockData); err != nil {
                fmt.Printf("%s⚠️  无法解析JSON文件 %s: %v%s\n", utils.Yellow, filePath, err, utils.Reset)
                continue
            }
            
            // Convert to string map to maintain compatibility and pre-parse color info
            for colorKey, blockInfo := range blockData {
                stringBlockInfo := make([]string, len(blockInfo))
                for i, val := range blockInfo {
                    switch v := val.(type) {
                    case string:
                        stringBlockInfo[i] = v
                    case float64: // JSON numbers are unmarshaled as float64
                        stringBlockInfo[i] = fmt.Sprintf("%.0f", v)
                    case int:
                        stringBlockInfo[i] = fmt.Sprintf("%d", v)
                    case bool:
                        stringBlockInfo[i] = fmt.Sprintf("%t", v)
                    default:
                        stringBlockInfo[i] = fmt.Sprintf("%v", v)
                    }
                }
                j.colorToBlock[colorKey] = stringBlockInfo
                
                // 预解析颜色信息
                colorStr := strings.Trim(colorKey, "()")
                colorParts := strings.Split(colorStr, ",")
                
                if len(colorParts) >= 3 {
                    r, rErr := strconv.Atoi(strings.TrimSpace(colorParts[0]))
                    g, gErr := strconv.Atoi(strings.TrimSpace(colorParts[1]))
                    b, bErr := strconv.Atoi(strings.TrimSpace(colorParts[2]))
                    
                    if rErr == nil && gErr == nil && bErr == nil {
                        var blockDataValue int8 = 0
                        if len(stringBlockInfo) >= 2 {
                            data, err := strconv.Atoi(stringBlockInfo[1])
                            if err == nil {
                                blockDataValue = int8(data)
                            }
                        }
                        
                        colorInfo := ColorInfo{
                            R: uint8(r),
                            G: uint8(g),
                            B: uint8(b),
                            BlockName: stringBlockInfo[0],
                            BlockData: blockDataValue,
                        }
                        j.colorInfos = append(j.colorInfos, colorInfo)
                    }
                }
            }
        }
    }
    
    if len(j.colorToBlock) == 0 {
        fmt.Printf("%s⚠️  没有加载任何方块映射，使用默认映射%s\n", utils.Yellow, utils.Reset)
        j.setDefaultMappings()
    }
    
    fmt.Printf("%s✅ 加载完成: %d 种颜色映射%s\n", utils.Green, len(j.colorToBlock), utils.Reset)
    return nil
}

// setDefaultMappings 设置默认颜色映射
func (j *JSONConverter) setDefaultMappings() {
    j.colorToBlock = map[string][]string{
        "(255, 255, 255)": {"minecraft:white_concrete", "0"},
        "(0, 0, 0)":       {"minecraft:black_concrete", "0"},
        "(255, 0, 0)":     {"minecraft:red_concrete", "0"},
        "(0, 255, 0)":     {"minecraft:green_concrete", "0"},
        "(0, 0, 255)":     {"minecraft:blue_concrete", "0"},
    }
    
    // 设置默认的预解析颜色信息
    j.colorInfos = []ColorInfo{
        {R: 255, G: 255, B: 255, BlockName: "minecraft:white_concrete", BlockData: 0},
        {R: 0, G: 0, B: 0, BlockName: "minecraft:black_concrete", BlockData: 0},
        {R: 255, G: 0, B: 0, BlockName: "minecraft:red_concrete", BlockData: 0},
        {R: 0, G: 255, B: 0, BlockName: "minecraft:green_concrete", BlockData: 0},
        {R: 0, G: 0, B: 255, BlockName: "minecraft:blue_concrete", BlockData: 0},
    }
}

// LoadImage 从文件路径加载图片
func (j *JSONConverter) LoadImage(imagePath string) error {
    file, err := os.Open(imagePath)
    if err != nil {
        return err
    }
    defer file.Close()
    
    var img image.Image
    
    // 读取文件头部以确定实际格式
    buffer := make([]byte, 512) // 读取前512字节用于检测
    _, err = file.Read(buffer)
    if err != nil && err != io.EOF {
        return fmt.Errorf("读取文件头部失败: %v", err)
    }
    
    // 重置文件指针到开头
    _, err = file.Seek(0, 0)
    if err != nil {
        return fmt.Errorf("重置文件指针失败: %v", err)
    }
    
    // 检测文件实际格式
    actualFormat := http.DetectContentType(buffer)
    
    // 根据检测到的实际格式解码
    switch actualFormat {
    case "image/png":
        img, err = png.Decode(file)
    case "image/jpeg":
        img, err = jpeg.Decode(file)
    case "image/webp":
        img, err = webp.Decode(file)
    default:
        // 如果无法检测到格式，使用imaging库尝试
        // 重置文件指针到开头
        _, err = file.Seek(0, 0)
        if err != nil {
            return fmt.Errorf("重置文件指针失败: %v", err)
        }
        img, err = imaging.Decode(file)
    }
    
    if err != nil {
        return fmt.Errorf("解码图片失败: %v (文件路径: %s, 检测格式: %s)", err, imagePath, actualFormat)
    }
    
    // 转换为NRGBA格式
    bounds := img.Bounds()
    j.originalWidth = bounds.Dx()
    j.originalHeight = bounds.Dy()
    j.pixels = make([][]color.NRGBA, j.originalHeight)
    
    for y := 0; y < j.originalHeight; y++ {
        j.pixels[y] = make([]color.NRGBA, j.originalWidth)
        for x := 0; x < j.originalWidth; x++ {
            j.pixels[y][x] = color.NRGBAModel.Convert(img.At(x+bounds.Min.X, y+bounds.Min.Y)).(color.NRGBA)
        }
    }
    
    fmt.Printf("%s✅ 图片加载完成: %d × %d 像素%s\n", utils.Green, j.originalWidth, j.originalHeight, utils.Reset)
    return nil
}

// SetSize 设置生成结构的尺寸
func (j *JSONConverter) SetSize(width, height int) {
    j.width = width
    j.height = height
    j.depth = 1 // 默认深度为1
    fmt.Printf("%s📐 设置生成尺寸: %d × %d 方块%s\n", utils.Blue, j.width, j.height, utils.Reset)
}

// FindClosestColor 找到最接近的颜色（优化版本）
func (j *JSONConverter) FindClosestColor(target color.NRGBA) (string, int) {
    minDistance := float64(1000000) // 使用较大初始值
    closestBlock := "minecraft:white_concrete"
    closestData := 0
    
    // 使用预解析的颜色信息进行快速查找
    for _, colorInfo := range j.colorInfos {
        // 使用快速的欧几里得距离计算替代LAB色彩空间距离
        dr := int32(target.R) - int32(colorInfo.R)
        dg := int32(target.G) - int32(colorInfo.G)
        db := int32(target.B) - int32(colorInfo.B)
        distance := float64(dr*dr + dg*dg + db*db)  // 平方距离，避免开方运算
        
        if distance < minDistance {
            minDistance = distance
            closestBlock = colorInfo.BlockName
            closestData = int(colorInfo.BlockData)
        }
    }
    
    return closestBlock, closestData
}

// generateJSONStructure 生成JSON结构数据
func (j *JSONConverter) generateJSONStructure() map[string]interface{} {
    fmt.Printf("%s🔨 正在生成JSON结构数据...%s\n", utils.Yellow, utils.Reset)
    
    // 计算缩放比例
    scaleX := float64(j.originalWidth) / float64(j.width)
    scaleY := float64(j.originalHeight) / float64(j.height)
    
    // 创建结构数据
    structure := map[string]interface{}{
        "name":   "Generated Structure",
        "author": "SunPixel Go",
        "version": "1.0",
        "size": map[string]int{
            "width":  j.width,
            "height": j.depth,
            "length": j.height,
        },
        "blocks": make([]interface{}, 0),
    }
    
    blocks := structure["blocks"].([]interface{})
    
    // 填充方块数据
    totalPixels := j.width * j.height
    processedPixels := 0
    
    for y := 0; y < j.height; y++ {
        for x := 0; x < j.width; x++ {
            srcX := int(float64(x) * scaleX)
            srcY := int(float64(y) * scaleY)
            
            // 确保不越界
            if srcX >= j.originalWidth {
                srcX = j.originalWidth - 1
            }
            if srcY >= j.originalHeight {
                srcY = j.originalHeight - 1
            }
            
            avgColor := j.pixels[srcY][srcX]
            blockName, blockData := j.FindClosestColor(avgColor)
            
            block := map[string]interface{}{
                "x":    x,
                "y":    0, // 固定高度为0
                "z":    y,
                "block": blockName,
                "data":  blockData,
            }
            
            blocks = append(blocks, block)
            
            processedPixels++
            
            // 每处理1%的像素或每1000个像素更新一次进度
            if j.progressCallback != nil && processedPixels%utils.Max(1000, totalPixels/100) == 0 {
                j.progressCallback(processedPixels, totalPixels, "生成JSON结构数据")
            }
        }
    }
    
    // 确保进度条显示完成
    if j.progressCallback != nil {
        j.progressCallback(totalPixels, totalPixels, "生成JSON结构数据")
    }
    
    structure["blocks"] = blocks
    fmt.Printf("%s✅ JSON结构数据生成完成%s\n", utils.Green, utils.Reset)
    return structure
}

// SetProgressCallback 设置进度回调函数
func (j *JSONConverter) SetProgressCallback(callback ProgressCallback) {
    j.progressCallback = callback
}

// NewJSONConverter 创建新的JSON转换器
func NewJSONConverter() *JSONConverter {
    return &JSONConverter{
        depth: 1,
    }
}