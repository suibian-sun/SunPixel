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
    "time"
    
    "github.com/disintegration/imaging"
    "golang.org/x/image/webp"
    "sunpixel/utils"
)

// LitematicConverter Litematica格式转换器
type LitematicConverter struct {
    colorToBlock BlockColorMap
    colorInfos    []ColorInfo
    blockPalette  []string
    width         int
    height        int
    depth         int
    pixels        [][]color.NRGBA
    originalWidth  int
    originalHeight int
    progressCallback ProgressCallback
}

// GetFormatName 获取格式名称
func (l *LitematicConverter) GetFormatName() string {
    return "litematic"
}

// GetExtension 获取文件扩展名
func (l *LitematicConverter) GetExtension() string {
    return ".litematic"
}

// LoadBlockMappings 加载方块映射
func (l *LitematicConverter) LoadBlockMappings(selectedBlocks []string) error {
    l.colorToBlock = make(BlockColorMap)
    l.colorInfos = make([]ColorInfo, 0)
    blockDir := "block"
    
    if _, err := os.Stat(blockDir); os.IsNotExist(err) {
        fmt.Printf("%s❌ 错误: block目录不存在!%s\n", utils.Red, utils.Reset)
        return err
    }
    
    files, err := os.ReadDir(blockDir)
    if err != nil {
        return err
    }
    
    for _, file := range files {
        if strings.HasSuffix(file.Name(), ".json") {
            blockName := strings.TrimSuffix(file.Name(), ".json")
            
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
            
            for colorKey, blockInfo := range blockData {
                stringBlockInfo := make([]string, len(blockInfo))
                for i, val := range blockInfo {
                    switch v := val.(type) {
                    case string:
                        stringBlockInfo[i] = v
                    case float64:
                        stringBlockInfo[i] = fmt.Sprintf("%.0f", v)
                    case int:
                        stringBlockInfo[i] = fmt.Sprintf("%d", v)
                    case bool:
                        stringBlockInfo[i] = fmt.Sprintf("%t", v)
                    default:
                        stringBlockInfo[i] = fmt.Sprintf("%v", v)
                    }
                }
                l.colorToBlock[colorKey] = stringBlockInfo
                
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
                            R: uint8(r), G: uint8(g), B: uint8(b),
                            BlockName: stringBlockInfo[0],
                            BlockData: blockDataValue,
                        }
                        l.colorInfos = append(l.colorInfos, colorInfo)
                    }
                }
            }
        }
    }
    
    if len(l.colorToBlock) == 0 {
        fmt.Printf("%s⚠️  没有加载任何方块映射，使用默认映射%s\n", utils.Yellow, utils.Reset)
        l.setDefaultMappings()
    }
    
    fmt.Printf("%s✅ 加载完成: %d 种颜色映射%s\n", utils.Green, len(l.colorToBlock), utils.Reset)
    return nil
}

func (l *LitematicConverter) setDefaultMappings() {
    l.colorToBlock = map[string][]string{
        "(255, 255, 255)": {"minecraft:white_concrete", "0"},
        "(0, 0, 0)":       {"minecraft:black_concrete", "0"},
        "(255, 0, 0)":     {"minecraft:red_concrete", "0"},
        "(0, 255, 0)":     {"minecraft:green_concrete", "0"},
        "(0, 0, 255)":     {"minecraft:blue_concrete", "0"},
    }
    l.colorInfos = []ColorInfo{
        {R: 255, G: 255, B: 255, BlockName: "minecraft:white_concrete", BlockData: 0},
        {R: 0, G: 0, B: 0, BlockName: "minecraft:black_concrete", BlockData: 0},
        {R: 255, G: 0, B: 0, BlockName: "minecraft:red_concrete", BlockData: 0},
        {R: 0, G: 255, B: 0, BlockName: "minecraft:green_concrete", BlockData: 0},
        {R: 0, G: 0, B: 255, BlockName: "minecraft:blue_concrete", BlockData: 0},
    }
}

func (l *LitematicConverter) LoadImage(imagePath string) error {
    file, err := os.Open(imagePath)
    if err != nil {
        return err
    }
    defer file.Close()
    
    var img image.Image
    
    buffer := make([]byte, 512)
    _, err = file.Read(buffer)
    if err != nil && err != io.EOF {
        return fmt.Errorf("读取文件头部失败: %v", err)
    }
    
    _, err = file.Seek(0, 0)
    if err != nil {
        return fmt.Errorf("重置文件指针失败: %v", err)
    }
    
    actualFormat := http.DetectContentType(buffer)
    
    switch actualFormat {
    case "image/png":
        img, err = png.Decode(file)
    case "image/jpeg":
        img, err = jpeg.Decode(file)
    case "image/webp":
        img, err = webp.Decode(file)
    default:
        _, err = file.Seek(0, 0)
        if err != nil {
            return fmt.Errorf("重置文件指针失败: %v", err)
        }
        img, err = imaging.Decode(file)
    }
    
    if err != nil {
        return fmt.Errorf("解码图片失败: %v", err)
    }
    
    bounds := img.Bounds()
    l.originalWidth = bounds.Dx()
    l.originalHeight = bounds.Dy()
    l.pixels = make([][]color.NRGBA, l.originalHeight)
    
    for y := 0; y < l.originalHeight; y++ {
        l.pixels[y] = make([]color.NRGBA, l.originalWidth)
        for x := 0; x < l.originalWidth; x++ {
            l.pixels[y][x] = color.NRGBAModel.Convert(img.At(x+bounds.Min.X, y+bounds.Min.Y)).(color.NRGBA)
        }
    }
    
    fmt.Printf("%s✅ 图片加载完成: %d × %d 像素%s\n", utils.Green, l.originalWidth, l.originalHeight, utils.Reset)
    return nil
}

func (l *LitematicConverter) SetSize(width, height int) {
    l.width = width
    l.height = height
    l.depth = 1
    fmt.Printf("%s📐 设置生成尺寸: %d × %d 方块%s\n", utils.Blue, l.width, l.height, utils.Reset)
}

func (l *LitematicConverter) FindClosestColor(target color.NRGBA) (string, int8) {
    minDistance := float64(1000000)
    closestBlock := "minecraft:white_concrete"
    closestData := int8(0)
    
    for _, colorInfo := range l.colorInfos {
        dr := int32(target.R) - int32(colorInfo.R)
        dg := int32(target.G) - int32(colorInfo.G)
        db := int32(target.B) - int32(colorInfo.B)
        distance := float64(dr*dr + dg*dg + db*db)
        
        if distance < minDistance {
            minDistance = distance
            closestBlock = colorInfo.BlockName
            closestData = colorInfo.BlockData
        }
    }
    
    return closestBlock, closestData
}

func (l *LitematicConverter) generateStructure() ([]int32, []string) {
    fmt.Printf("%s🔨 正在生成Litematic结构数据...%s\n", utils.Yellow, utils.Reset)
    
    blockSet := make(map[string]bool)
    for _, blockInfo := range l.colorToBlock {
        if len(blockInfo) > 0 {
            blockSet[blockInfo[0]] = true
        }
    }
    
    blockPalette := make([]string, 0, len(blockSet))
    for blockName := range blockSet {
        blockPalette = append(blockPalette, blockName)
    }
    
    scaleX := float64(l.originalWidth) / float64(l.width)
    scaleY := float64(l.originalHeight) / float64(l.height)
    
    totalPixels := l.width * l.height
    blockIndices := make([]int32, totalPixels)
    processedPixels := 0
    lastUpdateProgress := 0
    updateInterval := utils.Max(1000, totalPixels/100)
    
    for y := 0; y < l.height; y++ {
        for x := 0; x < l.width; x++ {
            srcX := int(float64(x) * scaleX)
            srcY := int(float64(y) * scaleY)
            
            if srcX >= l.originalWidth {
                srcX = l.originalWidth - 1
            }
            if srcY >= l.originalHeight {
                srcY = l.originalHeight - 1
            }
            
            avgColor := l.pixels[srcY][srcX]
            blockName, _ := l.FindClosestColor(avgColor)
            
            blockIndex := int32(0)
            for i, name := range blockPalette {
                if name == blockName {
                    blockIndex = int32(i)
                    break
                }
            }
            
            blockIndices[y*l.width+x] = blockIndex
            processedPixels++
            
            if l.progressCallback != nil && processedPixels >= lastUpdateProgress+updateInterval {
                l.progressCallback(processedPixels, totalPixels, "生成Litematic结构数据")
                lastUpdateProgress = processedPixels
            }
        }
    }
    
    if l.progressCallback != nil {
        l.progressCallback(totalPixels, totalPixels, "生成Litematic结构数据")
    }
    
    fmt.Printf("%s✅ Litematic结构数据生成完成%s\n", utils.Green, utils.Reset)
    return blockIndices, blockPalette
}

// packBitsToLongArray 将方块索引打包为LongArray格式(Litematica v6)
func packBitsToLongArray(indices []int32, bitsPerEntry int) []int64 {
    if len(indices) == 0 {
        return []int64{}
    }
    
    mask := int64((1 << bitsPerEntry) - 1)
    totalBits := len(indices) * bitsPerEntry
    numLongs := (totalBits + 63) / 64
    
    longBits := make([]int64, numLongs)
    
    for i, index := range indices {
        idxValue := int64(index) & mask
        bitPos := i * bitsPerEntry
        longIdx := bitPos / 64
        bitOffset := bitPos % 64
        
        remainingBits := bitsPerEntry
        value := idxValue
        currentLongIdx := longIdx
        currentOffset := bitOffset
        
        for remainingBits > 0 {
            bitsInThisLong := remainingBits
            if currentOffset+bitsInThisLong > 64 {
                bitsInThisLong = 64 - currentOffset
            }
            
            partMask := int64((1 << bitsInThisLong) - 1)
            part := value & partMask
            
            if currentLongIdx < len(longBits) {
                longBits[currentLongIdx] |= (part << currentOffset)
            }
            
            value >>= bitsInThisLong
            remainingBits -= bitsInThisLong
            currentOffset = 0
            currentLongIdx++
        }
    }
    
    return longBits
}

func (l *LitematicConverter) saveLitematicFile(outputPath string, blockIndices []int32, blockPalette []string) error {
    fmt.Printf("%s💾 正在保存litematic文件...%s\n", utils.Cyan, utils.Reset)
    
    outputDir := filepath.Dir(outputPath)
    if err := os.MkdirAll(outputDir, 0755); err != nil {
        return err
    }
    
    if !strings.HasSuffix(strings.ToLower(outputPath), ".litematic") {
        outputPath += ".litematic"
    }
    
    // 计算bits per entry
    paletteSize := len(blockPalette)
    bitsPerEntry := 4
    if paletteSize > 16 {
        for (1 << bitsPerEntry) < paletteSize {
            bitsPerEntry++
        }
    }
    
    // 打包方块索引
    blockStates := packBitsToLongArray(blockIndices, bitsPerEntry)
    
    // 构建BlockStatePalette
    paletteEntries := make([]map[string]interface{}, len(blockPalette))
    for i, name := range blockPalette {
        paletteEntries[i] = map[string]interface{}{
            "Name": name,
        }
    }
    
    // 构建Litematica数据结构
    now := time.Now().UnixMilli()
    litematicData := map[string]interface{}{
        "Version":            int32(6),
        "MinecraftDataVersion": int32(3100),
        "SubVersion":         int32(1),
        "Metadata": map[string]interface{}{
            "Author":        "SunPixel",
            "Description":   "Generated by SunPixel",
            "Name":          filepath.Base(outputPath),
            "EnclosingSize": map[string]interface{}{
                "x": int32(l.width),
                "y": int32(l.depth),
                "z": int32(l.height),
            },
            "RegionCount":  int32(1),
            "TimeCreated":  now,
            "TimeModified": now,
            "TotalBlocks":  int32(len(blockIndices)),
            "TotalVolume":  int32(len(blockIndices)),
        },
        "Regions": map[string]interface{}{
            "region": map[string]interface{}{
                "Position": map[string]interface{}{
                    "x": int32(0),
                    "y": int32(0),
                    "z": int32(0),
                },
                "Size": map[string]interface{}{
                    "x": int32(l.width),
                    "y": int32(l.depth),
                    "z": int32(l.height),
                },
                "BlockStatePalette": paletteEntries,
                "BlockStates":       blockStates,
                "Entities":          []interface{}{},
                "TileEntities":      []interface{}{},
            },
        },
    }
    
    // 保存为JSON格式的litematic文件
    file, err := os.Create(outputPath)
    if err != nil {
        return err
    }
    defer file.Close()
    
    encoder := json.NewEncoder(file)
    encoder.SetIndent("", "  ")
    if err := encoder.Encode(litematicData); err != nil {
        return err
    }
    
    fmt.Printf("%s✅ litematic文件保存完成: %s%s\n", utils.Green, outputPath, utils.Reset)
    return nil
}

// Convert 执行转换
func (l *LitematicConverter) Convert(inputPath, outputPath string, width, height int, selectedBlocks []string) error {
    fmt.Printf("%s🚀 开始Litematic格式转换...%s\n", utils.Blue, utils.Reset)
    
    if err := l.LoadBlockMappings(selectedBlocks); err != nil {
        return err
    }
    
    if err := l.LoadImage(inputPath); err != nil {
        return err
    }
    
    if width <= 0 || height <= 0 {
        l.SetSize(l.originalWidth, l.originalHeight)
    } else {
        l.SetSize(width, height)
    }
    
    blockIndices, blockPalette := l.generateStructure()
    
    return l.saveLitematicFile(outputPath, blockIndices, blockPalette)
}

// SetProgressCallback 设置进度回调函数
func (l *LitematicConverter) SetProgressCallback(callback ProgressCallback) {
    l.progressCallback = callback
}

// NewLitematicConverter 创建新的Litematic转换器
func NewLitematicConverter() *LitematicConverter {
    return &LitematicConverter{
        depth: 1,
    }
}