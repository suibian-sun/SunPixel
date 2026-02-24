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
    "sunpixel/src/nbt"
    "sunpixel/utils"
)



// FullSchemConverter 完整的Schem格式转换器
type FullSchemConverter struct {
    colorToBlock BlockColorMap
    colorInfos []ColorInfo  // 预解析的颜色信息，用于快速查找
    blockPalette []string
    blockData    []byte
    width        int
    height       int
    depth        int
    pixels       [][]color.NRGBA
    originalWidth  int
    originalHeight int
    progressCallback ProgressCallback
}

// GetFormatName 获取格式名称
func (s *FullSchemConverter) GetFormatName() string {
    return "schem"
}

// GetExtension 获取文件扩展名
func (s *FullSchemConverter) GetExtension() string {
    return ".schem"
}

// LoadBlockMappings 加载方块映射
func (s *FullSchemConverter) LoadBlockMappings(selectedBlocks []string) error {
    s.colorToBlock = make(BlockColorMap)
    s.colorInfos = make([]ColorInfo, 0)  // 初始化预解析颜色信息
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
                s.colorToBlock[colorKey] = stringBlockInfo
                
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
                        s.colorInfos = append(s.colorInfos, colorInfo)
                    }
                }
            }
        }
    }
    
    if len(s.colorToBlock) == 0 {
        fmt.Printf("%s⚠️  没有加载任何方块映射，使用默认映射%s\n", utils.Yellow, utils.Reset)
        s.setDefaultMappings()
    }
    
    fmt.Printf("%s✅ 加载完成: %d 种颜色映射%s\n", utils.Green, len(s.colorToBlock), utils.Reset)
    return nil
}

// setDefaultMappings 设置默认颜色映射
func (s *FullSchemConverter) setDefaultMappings() {
    s.colorToBlock = map[string][]string{
        "(255, 255, 255)": {"minecraft:white_concrete", "0"},
        "(0, 0, 0)":       {"minecraft:black_concrete", "0"},
        "(255, 0, 0)":     {"minecraft:red_concrete", "0"},
        "(0, 255, 0)":     {"minecraft:green_concrete", "0"},
        "(0, 0, 255)":     {"minecraft:blue_concrete", "0"},
    }
    
    // 设置默认的预解析颜色信息
    s.colorInfos = []ColorInfo{
        {R: 255, G: 255, B: 255, BlockName: "minecraft:white_concrete", BlockData: 0},
        {R: 0, G: 0, B: 0, BlockName: "minecraft:black_concrete", BlockData: 0},
        {R: 255, G: 0, B: 0, BlockName: "minecraft:red_concrete", BlockData: 0},
        {R: 0, G: 255, B: 0, BlockName: "minecraft:green_concrete", BlockData: 0},
        {R: 0, G: 0, B: 255, BlockName: "minecraft:blue_concrete", BlockData: 0},
    }
}

// LoadImage 从文件路径加载图片
func (s *FullSchemConverter) LoadImage(imagePath string) error {
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
    s.originalWidth = bounds.Dx()
    s.originalHeight = bounds.Dy()
    s.pixels = make([][]color.NRGBA, s.originalHeight)
    
    for y := 0; y < s.originalHeight; y++ {
        s.pixels[y] = make([]color.NRGBA, s.originalWidth)
        for x := 0; x < s.originalWidth; x++ {
            s.pixels[y][x] = color.NRGBAModel.Convert(img.At(x+bounds.Min.X, y+bounds.Min.Y)).(color.NRGBA)
        }
    }
    
    fmt.Printf("%s✅ 图片加载完成: %d × %d 像素%s\n", utils.Green, s.originalWidth, s.originalHeight, utils.Reset)
    return nil
}

// SetSize 设置生成结构的尺寸
func (s *FullSchemConverter) SetSize(width, height int) {
    s.width = width
    s.height = height
    s.depth = 1 // 默认深度为1
    fmt.Printf("%s📐 设置生成尺寸: %d × %d 方块%s\n", utils.Blue, s.width, s.height, utils.Reset)
}

// FindClosestColor 找到最接近的颜色（优化版本）
func (s *FullSchemConverter) FindClosestColor(target color.NRGBA) (string, int8) {
    minDistance := float64(1000000) // 使用较大初始值
    closestBlock := "minecraft:white_concrete"
    closestData := int8(0)
    
    // 使用预解析的颜色信息进行快速查找
    for _, colorInfo := range s.colorInfos {
        // 使用快速的欧几里得距离计算替代LAB色彩空间距离
        dr := int32(target.R) - int32(colorInfo.R)
        dg := int32(target.G) - int32(colorInfo.G)
        db := int32(target.B) - int32(colorInfo.B)
        distance := float64(dr*dr + dg*dg + db*db)  // 平方距离，避免开方运算
        
        if distance < minDistance {
            minDistance = distance
            closestBlock = colorInfo.BlockName
            closestData = colorInfo.BlockData
        }
    }
    
    return closestBlock, closestData
}

// GenerateStructure 生成结构数据
func (s *FullSchemConverter) GenerateStructure() {
    fmt.Printf("%s🔨 正在生成结构数据...%s\n", utils.Yellow, utils.Reset)
    
    // 初始化方块调色板
    blockSet := make(map[string]bool)
    for _, blockInfo := range s.colorToBlock {
        if len(blockInfo) > 0 {
            blockSet[blockInfo[0]] = true
        }
    }
    
    s.blockPalette = make([]string, 0, len(blockSet))
    for blockName := range blockSet {
        s.blockPalette = append(s.blockPalette, blockName)
    }
    
    // 创建方块数据数组
    totalSize := s.depth * s.height * s.width
    s.blockData = make([]byte, totalSize)
    
    // 计算缩放比例
    scaleX := float64(s.originalWidth) / float64(s.width)
    scaleY := float64(s.originalHeight) / float64(s.height)
    
    // 填充方块数据
    totalPixels := s.width * s.height
    processedPixels := 0
    lastUpdateProgress := 0
    updateInterval := utils.Max(1000, totalPixels/100) // 每1000个像素或每1%更新一次，取较大值
    
    for y := 0; y < s.height; y++ {
        for x := 0; x < s.width; x++ {
            srcX := int(float64(x) * scaleX)
            srcY := int(float64(y) * scaleY)
            
            // 确保不越界
            if srcX >= s.originalWidth {
                srcX = s.originalWidth - 1
            }
            if srcY >= s.originalHeight {
                srcY = s.originalHeight - 1
            }
            
            avgColor := s.pixels[srcY][srcX]
            blockName, _ := s.FindClosestColor(avgColor)
            
            // 查找方块在调色板中的索引
            blockIndex := byte(0)
            for i, name := range s.blockPalette {
                if name == blockName {
                    blockIndex = byte(i)
                    break
                }
            }
            
            // 计算在数据数组中的位置
            index := y*s.width + x
            if index < len(s.blockData) {
                s.blockData[index] = blockIndex
            }
            
            processedPixels++
            
            // 每处理1%的像素或每1000个像素更新一次进度（但受时间间隔限制）
            if s.progressCallback != nil && processedPixels >= lastUpdateProgress+updateInterval {
                s.progressCallback(processedPixels, totalPixels, "生成结构数据")
                lastUpdateProgress = processedPixels
            }
        }
    }
    
    // 确保进度条显示完成
    if s.progressCallback != nil {
        s.progressCallback(totalPixels, totalPixels, "生成结构数据")
    }
    
    fmt.Printf("%s✅ 结构数据生成完成%s\n", utils.Green, utils.Reset)
}



// SaveSchemFile 保存schem文件
func (s *FullSchemConverter) SaveSchemFile(outputPath string) error {
    fmt.Printf("%s💾 正在保存schem文件...%s\n", utils.Cyan, utils.Reset)
    
    // 创建输出目录
    outputDir := filepath.Dir(outputPath)
    if err := os.MkdirAll(outputDir, 0755); err != nil {
        return err
    }
    
    file, err := os.Create(outputPath)
    if err != nil {
        return err
    }
    defer file.Close()
    
    // 创建Schematic数据结构
    palette := make(map[string]interface{})
    for i, blockName := range s.blockPalette {
        palette[blockName] = int32(i)
    }
    
    schematic := map[string]interface{}{
        "Version":     int32(2),
        "DataVersion": int32(2730), // 1.16.5的版本号
        "Width":       int16(s.width),
        "Height":      int16(s.depth),
        "Length":      int16(s.height),
        "Offset":      []int32{int32(0), int32(0), int32(0)},
        "Palette":     palette,
        "BlockData":   s.convertBlockDataToIntArray(),
        "BlockEntities": []interface{}{},
    }
    
    // 写入NBT数据到gzip压缩文件
    err = nbt.WriteNBTToGzip(file, "", schematic)
    if err != nil {
        return err
    }
    
    fmt.Printf("%s✅ schem文件保存完成: %s%s\n", utils.Green, outputPath, utils.Reset)
    return nil
}

// convertBlockDataToIntArray converts the byte array to int array for NBT compatibility
func (s *FullSchemConverter) convertBlockDataToIntArray() []int32 {
    result := make([]int32, len(s.blockData))
    for i, v := range s.blockData {
        result[i] = int32(v)
    }
    return result
}

// Convert 执行转换
func (s *FullSchemConverter) Convert(inputPath, outputPath string, width, height int, selectedBlocks []string) error {
    fmt.Printf("%s🚀 开始转换流程...%s\n", utils.Blue, utils.Reset)
    
    // 加载方块映射
    if err := s.LoadBlockMappings(selectedBlocks); err != nil {
        return err
    }
    
    // 加载图片
    if err := s.LoadImage(inputPath); err != nil {
        return err
    }
    
    // 设置尺寸
    if width <= 0 || height <= 0 {
        s.SetSize(s.originalWidth, s.originalHeight)
    } else {
        s.SetSize(width, height)
    }
    
    // 生成结构
    s.GenerateStructure()
    
    // 保存文件
    return s.SaveSchemFile(outputPath)
}

// SetProgressCallback 设置进度回调函数
func (s *FullSchemConverter) SetProgressCallback(callback ProgressCallback) {
    s.progressCallback = callback
}

// NewSchemConverter 创建新的Schem转换器
func NewSchemConverter() *FullSchemConverter {
    return &FullSchemConverter{
        depth: 1,
    }
}