package format

import (
    "bytes"
    "encoding/binary"
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
    
    "github.com/andybalholm/brotli"
    "github.com/disintegration/imaging"
    "golang.org/x/image/webp"
    "sunpixel/utils"
)

// BDXConverter BDX格式转换器
type BDXConverter struct {
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
func (b *BDXConverter) GetFormatName() string {
    return "bdx"
}

// GetExtension 获取文件扩展名
func (b *BDXConverter) GetExtension() string {
    return ".bdx"
}

// LoadBlockMappings 加载方块映射
func (b *BDXConverter) LoadBlockMappings(selectedBlocks []string) error {
    b.colorToBlock = make(BlockColorMap)
    b.colorInfos = make([]ColorInfo, 0)
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
                b.colorToBlock[colorKey] = stringBlockInfo
                
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
                        b.colorInfos = append(b.colorInfos, colorInfo)
                    }
                }
            }
        }
    }
    
    if len(b.colorToBlock) == 0 {
        fmt.Printf("%s⚠️  没有加载任何方块映射，使用默认映射%s\n", utils.Yellow, utils.Reset)
        b.setDefaultMappings()
    }
    
    fmt.Printf("%s✅ 加载完成: %d 种颜色映射%s\n", utils.Green, len(b.colorToBlock), utils.Reset)
    return nil
}

func (b *BDXConverter) setDefaultMappings() {
    b.colorToBlock = map[string][]string{
        "(255, 255, 255)": {"minecraft:white_concrete", "0"},
        "(0, 0, 0)":       {"minecraft:black_concrete", "0"},
        "(255, 0, 0)":     {"minecraft:red_concrete", "0"},
        "(0, 255, 0)":     {"minecraft:green_concrete", "0"},
        "(0, 0, 255)":     {"minecraft:blue_concrete", "0"},
    }
    b.colorInfos = []ColorInfo{
        {R: 255, G: 255, B: 255, BlockName: "minecraft:white_concrete", BlockData: 0},
        {R: 0, G: 0, B: 0, BlockName: "minecraft:black_concrete", BlockData: 0},
        {R: 255, G: 0, B: 0, BlockName: "minecraft:red_concrete", BlockData: 0},
        {R: 0, G: 255, B: 0, BlockName: "minecraft:green_concrete", BlockData: 0},
        {R: 0, G: 0, B: 255, BlockName: "minecraft:blue_concrete", BlockData: 0},
    }
}

func (b *BDXConverter) LoadImage(imagePath string) error {
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
    b.originalWidth = bounds.Dx()
    b.originalHeight = bounds.Dy()
    b.pixels = make([][]color.NRGBA, b.originalHeight)
    
    for y := 0; y < b.originalHeight; y++ {
        b.pixels[y] = make([]color.NRGBA, b.originalWidth)
        for x := 0; x < b.originalWidth; x++ {
            b.pixels[y][x] = color.NRGBAModel.Convert(img.At(x+bounds.Min.X, y+bounds.Min.Y)).(color.NRGBA)
        }
    }
    
    fmt.Printf("%s✅ 图片加载完成: %d × %d 像素%s\n", utils.Green, b.originalWidth, b.originalHeight, utils.Reset)
    return nil
}

func (b *BDXConverter) SetSize(width, height int) {
    b.width = width
    b.height = height
    b.depth = 1
    fmt.Printf("%s📐 设置生成尺寸: %d × %d 方块%s\n", utils.Blue, b.width, b.height, utils.Reset)
}

func (b *BDXConverter) FindClosestColor(target color.NRGBA) (string, int8) {
    minDistance := float64(1000000)
    closestBlock := "minecraft:white_concrete"
    closestData := int8(0)
    
    for _, colorInfo := range b.colorInfos {
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

// generateBlockData 生成方块数据
func (b *BDXConverter) generateBlockData() []map[string]interface{} {
    fmt.Printf("%s🔨 正在生成BDX方块数据...%s\n", utils.Yellow, utils.Reset)
    
    scaleX := float64(b.originalWidth) / float64(b.width)
    scaleY := float64(b.originalHeight) / float64(b.height)
    
    totalPixels := b.width * b.height
    blocks := make([]map[string]interface{}, 0, totalPixels)
    processedPixels := 0
    lastUpdateProgress := 0
    updateInterval := utils.Max(1000, totalPixels/100)
    
    for y := 0; y < b.height; y++ {
        for x := 0; x < b.width; x++ {
            srcX := int(float64(x) * scaleX)
            srcY := int(float64(y) * scaleY)
            
            if srcX >= b.originalWidth {
                srcX = b.originalWidth - 1
            }
            if srcY >= b.originalHeight {
                srcY = b.originalHeight - 1
            }
            
            avgColor := b.pixels[srcY][srcX]
            blockName, blockData := b.FindClosestColor(avgColor)
            
            blocks = append(blocks, map[string]interface{}{
                "x":    x,
                "y":    0,
                "z":    y,
                "name": blockName,
                "data": int(blockData),
            })
            
            processedPixels++
            
            if b.progressCallback != nil && processedPixels >= lastUpdateProgress+updateInterval {
                b.progressCallback(processedPixels, totalPixels, "生成BDX方块数据")
                lastUpdateProgress = processedPixels
            }
        }
    }
    
    if b.progressCallback != nil {
        b.progressCallback(totalPixels, totalPixels, "生成BDX方块数据")
    }
    
    fmt.Printf("%s✅ BDX方块数据生成完成: %d 个方块%s\n", utils.Green, len(blocks), utils.Reset)
    return blocks
}

// saveBDXFile 保存BDX文件
func (b *BDXConverter) saveBDXFile(outputPath string, blocks []map[string]interface{}) error {
    fmt.Printf("%s💾 正在保存BDX文件...%s\n", utils.Cyan, utils.Reset)
    
    outputDir := filepath.Dir(outputPath)
    if err := os.MkdirAll(outputDir, 0755); err != nil {
        return err
    }
    
    if !strings.HasSuffix(strings.ToLower(outputPath), ".bdx") {
        outputPath += ".bdx"
    }
    
    // 收集所有方块名称
    blockNames := make(map[string]bool)
    for _, block := range blocks {
        name := block["name"].(string)
        blockNames[name] = true
    }
    
    // 构建BDX命令数据
    cmdBuf := new(bytes.Buffer)
    
    // 创建常量字符串（方块名称）
    stringIDs := make(map[string]uint16)
    stringID := uint16(0)
    for name := range blockNames {
        // 写入CreateConstantString命令 (0x0f)
        nameBytes := []byte(name)
        cmdBuf.WriteByte(0x0f)
        // 写入字符串长度（变长uint32）
        writeVarUint32(cmdBuf, uint32(len(nameBytes)))
        cmdBuf.Write(nameBytes)
        stringIDs[name] = stringID
        stringID++
    }
    
    // 创建空状态字符串
    cmdBuf.WriteByte(0x0f)
    writeVarUint32(cmdBuf, 0)
    emptyStringID := stringID
    stringIDs[""] = emptyStringID
    stringID++
    
    // 使用运行时ID池命令 (0x10)
    cmdBuf.WriteByte(0x10)
    cmdBuf.WriteByte(0) // pool ID = 0
    
    // 放置方块
    posX, posY, posZ := 0, 0, 0
    for _, block := range blocks {
        x := block["x"].(int)
        y := block["y"].(int)
        z := block["z"].(int)
        name := block["name"].(string)
        
        // 移动X
        moveX := x - posX
        if moveX != 0 {
            writeMoveCommand(cmdBuf, 0, moveX)
        }
        
        // 移动Y
        moveY := y - posY
        if moveY != 0 {
            writeMoveCommand(cmdBuf, 1, moveY)
        }
        
        // 移动Z
        moveZ := z - posZ
        if moveZ != 0 {
            writeMoveCommand(cmdBuf, 2, moveZ)
        }
        
        posX, posY, posZ = x, y, z
        
        // PlaceBlockWithBlockStates命令 (0x15)
        nameID := stringIDs[name]
        emptyID := stringIDs[""]
        cmdBuf.WriteByte(0x15)
        writeVarUint32(cmdBuf, uint32(nameID))
        writeVarUint32(cmdBuf, uint32(emptyID))
    }
    
    // 终止命令 (0x21)
    cmdBuf.WriteByte(0x21)
    
    // 构建BDX元数据 + 命令数据
    metaBuf := new(bytes.Buffer)
    metaBuf.WriteString("BDX")
    author := "SunPixel"
    metaBuf.Write([]byte(author))
    metaBuf.WriteByte(0)
    metaBuf.WriteByte(0)
    metaBuf.Write(cmdBuf.Bytes())
    
    // Brotli压缩
    var compressedBuf bytes.Buffer
    bw := brotli.NewWriter(&compressedBuf)
    if _, err := bw.Write(metaBuf.Bytes()); err != nil {
        return err
    }
    if err := bw.Close(); err != nil {
        return err
    }
    compressed := compressedBuf.Bytes()
    
    // 写入文件：BD@头 + 压缩数据
    file, err := os.Create(outputPath)
    if err != nil {
        return err
    }
    defer file.Close()
    
    file.WriteString("BD@")
    file.Write(compressed)
    
    fileSize, _ := file.Seek(0, io.SeekEnd)
    fmt.Printf("%s✅ BDX文件保存完成: %s (%d 字节)%s\n", utils.Green, outputPath, fileSize, utils.Reset)
    return nil
}

// writeVarUint32 写入变长uint32
func writeVarUint32(buf *bytes.Buffer, value uint32) {
    for {
        if value < 128 {
            buf.WriteByte(byte(value))
            return
        }
        buf.WriteByte(byte(value&0x7f) | 0x80)
        value >>= 7
    }
}

// writeMoveCommand 写入移动命令
func writeMoveCommand(buf *bytes.Buffer, axis int, delta int) {
    switch axis {
    case 0: // X
        switch {
        case delta == 1:
            buf.WriteByte(0x01) // AddXValue
        case delta == -1:
            buf.WriteByte(0x05) // SubtractXValue
        case delta >= -128 && delta <= 127:
            buf.WriteByte(0x07) // AddInt8XValue
            binary.Write(buf, binary.LittleEndian, int8(delta))
        case delta >= -32768 && delta <= 32767:
            buf.WriteByte(0x0b) // AddInt16XValue
            binary.Write(buf, binary.LittleEndian, int16(delta))
        }
    case 1: // Y
        switch {
        case delta == 1:
            buf.WriteByte(0x02) // AddYValue
        case delta == -1:
            buf.WriteByte(0x06) // SubtractYValue
        case delta >= -128 && delta <= 127:
            buf.WriteByte(0x08) // AddInt8YValue
            binary.Write(buf, binary.LittleEndian, int8(delta))
        case delta >= -32768 && delta <= 32767:
            buf.WriteByte(0x0c) // AddInt16YValue
            binary.Write(buf, binary.LittleEndian, int16(delta))
        }
    case 2: // Z
        switch {
        case delta == 1:
            buf.WriteByte(0x03) // AddZValue
        case delta == -1:
            buf.WriteByte(0x04) // SubtractZValue
        case delta >= -128 && delta <= 127:
            buf.WriteByte(0x09) // AddInt8ZValue
            binary.Write(buf, binary.LittleEndian, int8(delta))
        case delta >= -32768 && delta <= 32767:
            buf.WriteByte(0x0d) // AddInt16ZValue
            binary.Write(buf, binary.LittleEndian, int16(delta))
        }
    }
}

// Convert 执行转换
func (b *BDXConverter) Convert(inputPath, outputPath string, width, height int, selectedBlocks []string) error {
    fmt.Printf("%s🚀 开始BDX格式转换...%s\n", utils.Blue, utils.Reset)
    
    if err := b.LoadBlockMappings(selectedBlocks); err != nil {
        return err
    }
    
    if err := b.LoadImage(inputPath); err != nil {
        return err
    }
    
    if width <= 0 || height <= 0 {
        b.SetSize(b.originalWidth, b.originalHeight)
    } else {
        b.SetSize(width, height)
    }
    
    blocks := b.generateBlockData()
    
    return b.saveBDXFile(outputPath, blocks)
}

// SetProgressCallback 设置进度回调函数
func (b *BDXConverter) SetProgressCallback(callback ProgressCallback) {
    b.progressCallback = callback
}

// NewBDXConverter 创建新的BDX转换器
func NewBDXConverter() *BDXConverter {
    return &BDXConverter{
        depth: 1,
    }
}