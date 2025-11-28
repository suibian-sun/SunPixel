package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	_ "image/jpeg"
	_ "image/png"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/MachineMC/NBT"
)

type Color struct {
	R, G, B uint8
}

type BlockMapping struct {
	BlockName string `json:"block_name"`
	BlockData int    `json:"block_data"`
}

type ImageToSchem struct {
	colorToBlock    map[Color]BlockMapping
	blockPalette    []string
	blockData       [][][]int
	width           int
	height          int
	depth           int
	originalWidth   int
	originalHeight  int
	pixels          [][]Color
}

func NewImageToSchem() *ImageToSchem {
	return &ImageToSchem{
		colorToBlock: make(map[Color]BlockMapping),
		depth:        1,
	}
}

func (its *ImageToSchem) LoadBlockMappings(selectedBlocks []string) error {
	its.colorToBlock = make(map[Color]BlockMapping)
	blockDir := "block"

	if _, err := os.Stat(blockDir); os.IsNotExist(err) {
		return fmt.Errorf("block directory does not exist")
	}

	files, err := filepath.Glob(filepath.Join(blockDir, "*.json"))
	if err != nil {
		return err
	}

	for _, file := range files {
		blockName := strings.TrimSuffix(filepath.Base(file), ".json")
		
		// Check if this block is selected
		selected := false
		for _, selectedBlock := range selectedBlocks {
			if selectedBlock == blockName {
				selected = true
				break
			}
		}
		
		if !selected {
			continue
		}

		data, err := os.ReadFile(file)
		if err != nil {
			return fmt.Errorf("error reading %s: %v", file, err)
		}

		var blockData map[string]interface{}
		if err := json.Unmarshal(data, &blockData); err != nil {
			return fmt.Errorf("error parsing JSON in %s: %v", file, err)
		}

		for colorStr, blockInfo := range blockData {
			blockMap, ok := blockInfo.(map[string]interface{})
			if !ok {
				// Try as array
				blockArr, ok := blockInfo.([]interface{})
				if ok && len(blockArr) >= 2 {
					blockName := blockArr[0].(string)
					blockData := int(blockArr[1].(float64))
					
					// Parse color
					colorStr = strings.Trim(colorStr, "()")
					parts := strings.Split(colorStr, ",")
					if len(parts) >= 3 {
						r, _ := strconv.Atoi(strings.TrimSpace(parts[0]))
						g, _ := strconv.Atoi(strings.TrimSpace(parts[1]))
						b, _ := strconv.Atoi(strings.TrimSpace(parts[2]))
						
						its.colorToBlock[Color{uint8(r), uint8(g), uint8(b)}] = BlockMapping{
							BlockName: blockName,
							BlockData: blockData,
						}
					}
				}
				continue
			}

			blockName, ok1 := blockMap["block_name"].(string)
			blockData, ok2 := blockMap["block_data"].(float64)
			
			if ok1 && ok2 {
				// Parse color
				colorStr = strings.Trim(colorStr, "()")
				parts := strings.Split(colorStr, ",")
				if len(parts) >= 3 {
					r, _ := strconv.Atoi(strings.TrimSpace(parts[0]))
					g, _ := strconv.Atoi(strings.TrimSpace(parts[1]))
					b, _ := strconv.Atoi(strings.TrimSpace(parts[2]))
					
					its.colorToBlock[Color{uint8(r), uint8(g), uint8(b)}] = BlockMapping{
						BlockName: blockName,
						BlockData: int(blockData),
					}
				}
			}
		}
	}

	if len(its.colorToBlock) == 0 {
		return fmt.Errorf("no block mappings loaded")
	}

	return nil
}

func (its *ImageToSchem) ColorDistance(c1, c2 Color) float64 {
	r1, g1, b1 := float64(c1.R), float64(c1.G), float64(c1.B)
	r2, g2, b2 := float64(c2.R), float64(c2.G), float64(c2.B)
	rMean := (r1 + r2) / 2

	rDiff := r1 - r2
	gDiff := g1 - g2
	bDiff := b1 - b2

	return math.Sqrt(
		(2+rMean/256)*(rDiff*rDiff) +
			4*(gDiff*gDiff) +
			(2+(255-rMean)/256)*(bDiff*bDiff))
}

func (its *ImageToSchem) FindClosestColor(target Color) (BlockMapping, bool) {
	var closestColor Color
	minDistance := math.MaxFloat64
	found := false

	for colorKey := range its.colorToBlock {
		distance := its.ColorDistance(target, colorKey)
		if distance < minDistance {
			minDistance = distance
			closestColor = colorKey
			found = true
		}
	}

	if found {
		return its.colorToBlock[closestColor], true
	}
	return BlockMapping{"minecraft:white_concrete", 0}, false
}

func (its *ImageToSchem) LoadImage(imagePath string) error {
	file, err := os.Open(imagePath)
	if err != nil {
		return err
	}
	defer file.Close()

	img, _, err := image.Decode(file)
	if err != nil {
		return err
	}

	bounds := img.Bounds()
	its.originalWidth = bounds.Dx()
	its.originalHeight = bounds.Dy()

	// Convert image to Color matrix
	its.pixels = make([][]Color, its.originalHeight)
	for y := 0; y < its.originalHeight; y++ {
		its.pixels[y] = make([]Color, its.originalWidth)
		for x := 0; x < its.originalWidth; x++ {
			c := color.RGBAModel.Convert(img.At(x+bounds.Min.X, y+bounds.Min.Y)).(color.RGBA)
			its.pixels[y][x] = Color{c.R, c.G, c.B}
		}
	}

	return nil
}

func (its *ImageToSchem) SetSize(width, height int) {
	its.width = max(1, width)
	its.height = max(1, height)
}

func (its *ImageToSchem) GenerateSchem() error {
	// Initialize block palette
	paletteSet := make(map[string]bool)
	for _, mapping := range its.colorToBlock {
		paletteSet[mapping.BlockName] = true
	}
	
	its.blockPalette = make([]string, 0, len(paletteSet))
	for blockName := range paletteSet {
		its.blockPalette = append(its.blockPalette, blockName)
	}

	// Initialize block data
	its.blockData = make([][][]int, its.depth)
	for z := 0; z < its.depth; z++ {
		its.blockData[z] = make([][]int, its.height)
		for y := 0; y < its.height; y++ {
			its.blockData[z][y] = make([]int, its.width)
		}
	}

	// Calculate scale
	scaleX := float64(its.originalWidth) / float64(its.width)
	scaleY := float64(its.originalHeight) / float64(its.height)

	// Fill block data
	for y := 0; y < its.height; y++ {
		for x := 0; x < its.width; x++ {
			srcX := int(float64(x) * scaleX)
			srcY := int(float64(y) * scaleY)
			endX := min(int(float64(x+1)*scaleX), its.originalWidth)
			endY := min(int(float64(y+1)*scaleY), its.originalHeight)

			// Calculate average color in region
			var avgR, avgG, avgB float64
			count := 0

			for py := srcY; py < endY; py++ {
				for px := srcX; px < endX; px++ {
					c := its.pixels[py][px]
					avgR += float64(c.R)
					avgG += float64(c.G)
					avgB += float64(c.B)
					count++
				}
			}

			if count == 0 {
				avgR, avgG, avgB = 255, 255, 255
			} else {
				avgR /= float64(count)
				avgG /= float64(count)
				avgB /= float64(count)
			}

			avgColor := Color{uint8(avgR), uint8(avgG), uint8(avgB)}
			blockMapping, found := its.FindClosestColor(avgColor)
			
			var blockIndex int
			if found {
				// Find block index in palette
				for i, blockName := range its.blockPalette {
					if blockName == blockMapping.BlockName {
						blockIndex = i
						break
					}
				}
			}

			its.blockData[0][y][x] = blockIndex
		}
	}

	return nil
}

func (its *ImageToSchem) SaveSchem(outputPath string) error {
	if !strings.HasSuffix(strings.ToLower(outputPath), ".schem") {
		outputPath += ".schem"
	}

	// Create palette map for NBT
	paletteMap := make(map[string]int32)
	for i, blockName := range its.blockPalette {
		paletteMap[blockName] = int32(i)
	}

	// Flatten block data
	blockData := make([]byte, its.width*its.height*its.depth)
	index := 0
	for z := 0; z < its.depth; z++ {
		for y := 0; y < its.height; y++ {
			for x := 0; x < its.width; x++ {
				blockData[index] = byte(its.blockData[z][y][x])
				index++
			}
		}
	}

	// Create NBT structure
	schematic := map[string]interface{}{
		"Version":      int32(2),
		"DataVersion":  int32(3100),
		"Width":        int16(its.width),
		"Height":       int16(its.depth),
		"Length":       int16(its.height),
		"Offset":       []int32{0, 0, 0},
		"Palette":      paletteMap,
		"BlockData":    blockData,
		"BlockEntities": []interface{}{},
	}

	// Write NBT file
	file, err := os.Create(outputPath)
	if err != nil {
		return err
	}
	defer file.Close()

	encoder := nbt.NewEncoderWithEncoding(file, nbt.BigEndian)
	if err := encoder.Encode(schematic); err != nil {
		return err
	}

	return nil
}

func (its *ImageToSchem) Convert(inputImage, outputSchem string, width, height int, selectedBlocks []string) error {
	if err := its.LoadBlockMappings(selectedBlocks); err != nil {
		return err
	}

	if err := its.LoadImage(inputImage); err != nil {
		return err
	}

	if width == 0 || height == 0 {
		its.SetSize(its.originalWidth, its.originalHeight)
	} else {
		its.SetSize(width, height)
	}

	if err := its.GenerateSchem(); err != nil {
		return err
	}

	return its.SaveSchem(outputSchem)
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func main() {
	if len(os.Args) < 3 {
		fmt.Println("Usage: SunPixel <input_image> <output_schem> [width] [height]")
		fmt.Println("Example: SunPixel image.png output.schem 64 64")
		return
	}

	inputImage := os.Args[1]
	outputSchem := os.Args[2]
	
	var width, height int
	if len(os.Args) >= 5 {
		width, _ = strconv.Atoi(os.Args[3])
		height, _ = strconv.Atoi(os.Args[4])
	}

	// Default block selections
	selectedBlocks := []string{"wool", "concrete"}

	converter := NewImageToSchem()
	if err := converter.Convert(inputImage, outputSchem, width, height, selectedBlocks); err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Successfully converted %s to %s\n", inputImage, outputSchem)
	fmt.Printf("Dimensions: %d x %d blocks\n", converter.width, converter.height)
}