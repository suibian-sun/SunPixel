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

// MCStructureConverter MCStructure格式转换器
type MCStructureConverter struct {
    colorToBlock BlockColorMap
    colorInfos    []ColorInfo
    width         int
    height        int
    depth         int
    pixels        [][]color.NRGBA
    originalWidth  int
    originalHeight int
    progressCallback ProgressCallback
}

// GetFormatName 获取格式名称
func (m *MCStructureConverter) GetFormatName() string {
    return "mcstructure"
}

// GetExtension 获取文件扩展名
func (m *MCStructureConverter) GetExtension() string {
    return ".mcstructure"
}

// LoadBlockMappings 加载方块映射
func (m *MCStructureConverter) LoadBlockMappings(selectedBlocks []string) error {
    m.colorToBlock = make(BlockColorMap)
    m.colorInfos = make([]ColorInfo, 0)
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
                m.colorToBlock[colorKey] = stringBlockInfo
                
                colorStr := strings.Trim(colorKey, "()")
                colorParts := strings.Split(colorStr, ",")
                
                if len(colorParts) >= 3 {
                    r, rErr := strconv.Atoi(strings.TrimSpace(colorParts[0]))
                    g, gErr := strconv.Atoi(strings.TrimSpace(colorParts[1]))
                    bv, bErr := strconv.Atoi(strings.TrimSpace(colorParts[2]))
                    
                    if rErr == nil && gErr == nil && bErr == nil {
                        var blockDataValue int8 = 0
                        if len(stringBlockInfo) >= 2 {
                            data, err := strconv.Atoi(stringBlockInfo[1])
                            if err == nil {
                                blockDataValue = int8(data)
                            }
                        }
                        
                        colorInfo := ColorInfo{
                            R: uint8(r), G: uint8(g), B: uint8(bv),
                            BlockName: stringBlockInfo[0],
                            BlockData: blockDataValue,
                        }
                        m.colorInfos = append(m.colorInfos, colorInfo)
                    }
                }
            }
        }
    }
    
    if len(m.colorToBlock) == 0 {
        fmt.Printf("%s⚠️  没有加载任何方块映射，使用默认映射%s\n", utils.Yellow, utils.Reset)
        m.setDefaultMappings()
    }
    
    fmt.Printf("%s✅ 加载完成: %d 种颜色映射%s\n", utils.Green, len(m.colorToBlock), utils.Reset)
    return nil
}

func (m *MCStructureConverter) setDefaultMappings() {
    m.colorToBlock = map[string][]string{
        "(255, 255, 255)": {"minecraft:white_concrete", "0"},
        "(0, 0, 0)":       {"minecraft:black_concrete", "0"},
        "(255, 0, 0)":     {"minecraft:red_concrete", "0"},
        "(0, 255, 0)":     {"minecraft:green_concrete", "0"},
        "(0, 0, 255)":     {"minecraft:blue_concrete", "0"},
    }
    m.colorInfos = []ColorInfo{
        {R: 255, G: 255, B: 255, BlockName: "minecraft:white_concrete", BlockData: 0},
        {R: 0, G: 0, B: 0, BlockName: "minecraft:black_concrete", BlockData: 0},
        {R: 255, G: 0, B: 0, BlockName: "minecraft:red_concrete", BlockData: 0},
        {R: 0, G: 255, B: 0, BlockName: "minecraft:green_concrete", BlockData: 0},
        {R: 0, G: 0, B: 255, BlockName: "minecraft:blue_concrete", BlockData: 0},
    }
}

func (m *MCStructureConverter) LoadImage(imagePath string) error {
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
    m.originalWidth = bounds.Dx()
    m.originalHeight = bounds.Dy()
    m.pixels = make([][]color.NRGBA, m.originalHeight)
    
    for y := 0; y < m.originalHeight; y++ {
        m.pixels[y] = make([]color.NRGBA, m.originalWidth)
        for x := 0; x < m.originalWidth; x++ {
            m.pixels[y][x] = color.NRGBAModel.Convert(img.At(x+bounds.Min.X, y+bounds.Min.Y)).(color.NRGBA)
        }
    }
    
    fmt.Printf("%s✅ 图片加载完成: %d × %d 像素%s\n", utils.Green, m.originalWidth, m.originalHeight, utils.Reset)
    return nil
}

func (m *MCStructureConverter) SetSize(width, height int) {
    m.width = width
    m.height = height
    m.depth = 1
    fmt.Printf("%s📐 设置生成尺寸: %d × %d 方块%s\n", utils.Blue, m.width, m.height, utils.Reset)
}

func (m *MCStructureConverter) FindClosestColor(target color.NRGBA) (string, int8) {
    minDistance := float64(1000000)
    closestBlock := "minecraft:white_concrete"
    closestData := int8(0)
    
    for _, colorInfo := range m.colorInfos {
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

// generateStructure 生成结构数据
func (m *MCStructureConverter) generateStructure() ([]int32, []string) {
    fmt.Printf("%s🔨 正在生成MCStructure数据...%s\n", utils.Yellow, utils.Reset)
    
    blockSet := make(map[string]bool)
    for _, blockInfo := range m.colorToBlock {
        if len(blockInfo) > 0 {
            blockSet[blockInfo[0]] = true
        }
    }
    
    blockPalette := make([]string, 0, len(blockSet))
    for blockName := range blockSet {
        blockPalette = append(blockPalette, blockName)
    }
    
    scaleX := float64(m.originalWidth) / float64(m.width)
    scaleY := float64(m.originalHeight) / float64(m.height)
    
    totalPixels := m.width * m.height
    blockIndices := make([]int32, totalPixels)
    processedPixels := 0
    lastUpdateProgress := 0
    updateInterval := utils.Max(1000, totalPixels/100)
    
    for y := 0; y < m.height; y++ {
        for x := 0; x < m.width; x++ {
            srcX := int(float64(x) * scaleX)
            srcY := int(float64(y) * scaleY)
            
            if srcX >= m.originalWidth {
                srcX = m.originalWidth - 1
            }
            if srcY >= m.originalHeight {
                srcY = m.originalHeight - 1
            }
            
            avgColor := m.pixels[srcY][srcX]
            blockName, _ := m.FindClosestColor(avgColor)
            
            blockIndex := int32(0)
            for i, name := range blockPalette {
                if name == blockName {
                    blockIndex = int32(i)
                    break
                }
            }
            
            blockIndices[y*m.width+x] = blockIndex
            processedPixels++
            
            if m.progressCallback != nil && processedPixels >= lastUpdateProgress+updateInterval {
                m.progressCallback(processedPixels, totalPixels, "生成MCStructure数据")
                lastUpdateProgress = processedPixels
            }
        }
    }
    
    if m.progressCallback != nil {
        m.progressCallback(totalPixels, totalPixels, "生成MCStructure数据")
    }
    
    fmt.Printf("%s✅ MCStructure数据生成完成%s\n", utils.Green, utils.Reset)
    return blockIndices, blockPalette
}

// saveMCStructureFile 保存MCStructure文件
func (m *MCStructureConverter) saveMCStructureFile(outputPath string, blockIndices []int32, blockPalette []string) error {
    fmt.Printf("%s💾 正在保存MCStructure文件...%s\n", utils.Cyan, utils.Reset)
    
    outputDir := filepath.Dir(outputPath)
    if err := os.MkdirAll(outputDir, 0755); err != nil {
        return err
    }
    
    if !strings.HasSuffix(strings.ToLower(outputPath), ".mcstructure") {
        outputPath += ".mcstructure"
    }
    
    // 构建MCStructure JSON格式
    palette := make([]map[string]interface{}, len(blockPalette))
    for i, name := range blockPalette {
        palette[i] = map[string]interface{}{
            "name": name,
            "states": map[string]interface{}{},
            "version": 17959425,
        }
    }
    
    // 构建block_indices (ZYX顺序)
    volume := m.depth * m.height * m.width
    indices0 := make([]int32, volume)
    indices1 := make([]int32, volume)
    
    for i, idx := range blockIndices {
        indices0[i] = idx
        indices1[i] = -1
    }
    
    structure := map[string]interface{}{
        "format_version": 1,
        "size": []int32{int32(m.width), int32(m.depth), int32(m.height)},
        "structure_world_origin": []int32{0, 0, 0},
        "structure": map[string]interface{}{
            "block_indices": [][]int32{indices0, indices1},
            "entities": []interface{}{},
            "palette": map[string]interface{}{
                "default": map[string]interface{}{
                    "block_palette": palette,
                    "block_position_data": map[string]interface{}{},
                },
            },
        },
    }
    
    file, err := os.Create(outputPath)
    if err != nil {
        return err
    }
    defer file.Close()
    
    encoder := json.NewEncoder(file)
    encoder.SetIndent("", "  ")
    if err := encoder.Encode(structure); err != nil {
        return err
    }
    
    fmt.Printf("%s✅ MCStructure文件保存完成: %s%s\n", utils.Green, outputPath, utils.Reset)
    return nil
}

// Convert 执行转换
func (m *MCStructureConverter) Convert(inputPath, outputPath string, width, height int, selectedBlocks []string) error {
    fmt.Printf("%s🚀 开始MCStructure格式转换...%s\n", utils.Blue, utils.Reset)
    
    if err := m.LoadBlockMappings(selectedBlocks); err != nil {
        return err
    }
    
    if err := m.LoadImage(inputPath); err != nil {
        return err
    }
    
    if width <= 0 || height <= 0 {
        m.SetSize(m.originalWidth, m.originalHeight)
    } else {
        m.SetSize(width, height)
    }
    
    blockIndices, blockPalette := m.generateStructure()
    
    return m.saveMCStructureFile(outputPath, blockIndices, blockPalette)
}

// SetProgressCallback 设置进度回调函数
func (m *MCStructureConverter) SetProgressCallback(callback ProgressCallback) {
    m.progressCallback = callback
}

// NewMCStructureConverter 创建新的MCStructure转换器
func NewMCStructureConverter() *MCStructureConverter {
    return &MCStructureConverter{
        depth: 1,
    }
}