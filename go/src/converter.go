package converter

import (
    "encoding/json"
    "fmt"
    "image"
    "image/color"
    "image/jpeg"
    "image/png"
    "io"
    "net/http"
    "math"
    "os"
    "path/filepath"
    "strconv"
    "strings"
    
    "github.com/disintegration/imaging"
    "github.com/lucasb-eyer/go-colorful"
    "github.com/schollz/progressbar/v3"
    "golang.org/x/image/webp"
    "sunpixel/src/nbt"
)

// BlockColorMap 定义方块颜色映射
type BlockColorMap map[string][]string

// ImageConverter 图片转换器
type ImageConverter struct {
    colorToBlock BlockColorMap
    blockPalette []string
    blockData    []int
    width        int
    height       int
    depth        int
    pixels       [][]color.NRGBA
    originalWidth  int
    originalHeight int
}

// NewImageConverter 创建新的图片转换器
func NewImageConverter() *ImageConverter {
    return &ImageConverter{
        depth: 1,
    }
}

// LoadBlockMappings 加载方块映射
func (ic *ImageConverter) LoadBlockMappings(selectedBlocks []string) error {
    ic.colorToBlock = make(BlockColorMap)
    blockDir := "block"
    
    if _, err := os.Stat(blockDir); os.IsNotExist(err) {
        fmt.Println("❌ 错误: block目录不存在!")
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
                fmt.Printf("⚠️  无法读取文件 %s: %v\n", filePath, err)
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
                fmt.Printf("⚠️  无法解析JSON文件 %s: %v\n", filePath, err)
                continue
            }
            
            // Convert to string map to maintain compatibility
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
                ic.colorToBlock[colorKey] = stringBlockInfo
            }
        }
    }
    
    if len(ic.colorToBlock) == 0 {
        fmt.Println("⚠️  没有加载任何方块映射，使用默认映射")
        ic.setDefaultMappings()
    }
    
    fmt.Printf("✅ 加载完成: %d 种颜色映射\n", len(ic.colorToBlock))
    return nil
}

// setDefaultMappings 设置默认颜色映射
func (ic *ImageConverter) setDefaultMappings() {
    ic.colorToBlock = map[string][]string{
        "(255, 255, 255)": {"minecraft:white_concrete", "0"},
        "(0, 0, 0)":       {"minecraft:black_concrete", "0"},
        "(255, 0, 0)":     {"minecraft:red_concrete", "0"},
        "(0, 255, 0)":     {"minecraft:green_concrete", "0"},
        "(0, 0, 255)":     {"minecraft:blue_concrete", "0"},
    }
}

// LoadImage 从文件路径加载图片
func (ic *ImageConverter) LoadImage(imagePath string) error {
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
    ic.originalWidth = bounds.Dx()
    ic.originalHeight = bounds.Dy()
    ic.pixels = make([][]color.NRGBA, ic.originalHeight)
    
    for y := 0; y < ic.originalHeight; y++ {
        ic.pixels[y] = make([]color.NRGBA, ic.originalWidth)
        for x := 0; x < ic.originalWidth; x++ {
            ic.pixels[y][x] = color.NRGBAModel.Convert(img.At(x+bounds.Min.X, y+bounds.Min.Y)).(color.NRGBA)
        }
    }
    
    fmt.Printf("✅ 图片加载完成: %d × %d 像素\n", ic.originalWidth, ic.originalHeight)
    return nil
}

// SetSize 设置生成结构的尺寸
func (ic *ImageConverter) SetSize(width, height int) {
    ic.width = width
    ic.height = height
    fmt.Printf("📐 设置生成尺寸: %d × %d 方块\n", ic.width, ic.height)
}

// FindClosestColor 找到最接近的颜色
func (ic *ImageConverter) FindClosestColor(target color.NRGBA) (string, string) {
    targetColor := colorful.Color{R: float64(target.R) / 255.0, G: float64(target.G) / 255.0, B: float64(target.B) / 255.0}
    minDistance := math.Inf(1)
    closestBlock := "minecraft:white_concrete"
    closestData := "0"
    
    for colorStr, blockInfo := range ic.colorToBlock {
        // 解析颜色字符串，例如 "(255, 255, 255)"
        colorStr = strings.Trim(colorStr, "()")
        colorParts := strings.Split(colorStr, ",")
        
        if len(colorParts) >= 3 {
            r, rErr := strconv.Atoi(strings.TrimSpace(colorParts[0]))
            g, gErr := strconv.Atoi(strings.TrimSpace(colorParts[1]))
            b, bErr := strconv.Atoi(strings.TrimSpace(colorParts[2]))
            
            if rErr == nil && gErr == nil && bErr == nil {
                blockColor := colorful.Color{R: float64(r) / 255.0, G: float64(g) / 255.0, B: float64(b) / 255.0}
                distance := targetColor.DistanceLab(blockColor)
                
                if distance < minDistance {
                    minDistance = distance
                    if len(blockInfo) >= 2 {
                        closestBlock = blockInfo[0]
                        closestData = blockInfo[1]
                    }
                }
            }
        }
    }
    
    return closestBlock, closestData
}

// GenerateStructure 生成结构数据
func (ic *ImageConverter) GenerateStructure() {
    fmt.Println("🔨 正在生成结构数据...")
    
    // 初始化方块调色板
    blockSet := make(map[string]bool)
    for _, blockInfo := range ic.colorToBlock {
        if len(blockInfo) > 0 {
            blockSet[blockInfo[0]] = true
        }
    }
    
    ic.blockPalette = make([]string, 0, len(blockSet))
    for blockName := range blockSet {
        ic.blockPalette = append(ic.blockPalette, blockName)
    }
    
    // 创建方块数据数组
    ic.blockData = make([]int, ic.depth*ic.height*ic.width)
    
    // 计算缩放比例
    scaleX := float64(ic.originalWidth) / float64(ic.width)
    scaleY := float64(ic.originalHeight) / float64(ic.height)
    
    totalPixels := ic.width * ic.height
    bar := progressbar.Default(int64(totalPixels), "📊 处理像素")
    
    // 填充方块数据
    for y := 0; y < ic.height; y++ {
        for x := 0; x < ic.width; x++ {
            srcX := int(float64(x) * scaleX)
            srcY := int(float64(y) * scaleY)
            
            // 确保不越界
            if srcX >= ic.originalWidth {
                srcX = ic.originalWidth - 1
            }
            if srcY >= ic.originalHeight {
                srcY = ic.originalHeight - 1
            }
            
            avgColor := ic.pixels[srcY][srcX]
            blockName, _ := ic.FindClosestColor(avgColor)
            
            // 查找方块在调色板中的索引
            blockIndex := 0
            for i, name := range ic.blockPalette {
                if name == blockName {
                    blockIndex = i
                    break
                }
            }
            
            // 计算在数据数组中的位置
            index := y*ic.width + x
            if index < len(ic.blockData) {
                ic.blockData[index] = blockIndex
            }
            
            bar.Add(1)
        }
    }
    
    fmt.Println("\n✅ 结构数据生成完成")
}

// SaveSchemFile 保存schem文件
func (ic *ImageConverter) SaveSchemFile(outputPath string) error {
    fmt.Println("💾 正在保存schem文件...")
    
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
    schematic := map[string]interface{}{
        "Version":     int32(2),
        "DataVersion": int32(3100),
        "Width":       int16(ic.width),
        "Height":      int16(ic.depth),
        "Length":      int16(ic.height),
        "Offset":      []int32{0, 0, 0},
        "Palette":     ic.createPalette(),
        "BlockData":   ic.blockData,
        "BlockEntities": []interface{}{},
    }
    
    // 写入NBT数据到gzip压缩文件
    err = nbt.WriteNBTToGzip(file, "", schematic)
    if err != nil {
        return err
    }
    
    fmt.Printf("✅ schem文件保存完成: %s\n", outputPath)
    return nil
}

// createPalette 创建方块调色板
func (ic *ImageConverter) createPalette() map[string]interface{} {
    palette := make(map[string]interface{})
    for i, blockName := range ic.blockPalette {
        palette[blockName] = int32(i)
    }
    return palette
}

// Convert 执行转换
func (ic *ImageConverter) Convert(inputImage, outputPath string, width, height int, selectedBlocks []string) error {
    fmt.Println("🚀 开始转换流程...")
    
    // 加载方块映射
    if err := ic.LoadBlockMappings(selectedBlocks); err != nil {
        return err
    }
    
    // 加载图片
    if err := ic.LoadImage(inputImage); err != nil {
        return err
    }
    
    // 设置尺寸
    if width <= 0 || height <= 0 {
        ic.SetSize(ic.originalWidth, ic.originalHeight)
    } else {
        ic.SetSize(width, height)
    }
    
    // 生成结构
    ic.GenerateStructure()
    
    // 保存文件
    return ic.SaveSchemFile(outputPath)
}