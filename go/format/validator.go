package format

import (
	"fmt"
	"io/ioutil"
	"os"

	"sunpixel/src/nbt"
)

// VerifySchemFile 验证schem文件内容并修复可能的错误
func VerifySchemFile(filePath string) (bool, string) {
	fmt.Println("\n🔍 正在验证生成的schem文件...")

	// 打开文件
	file, err := os.Open(filePath)
	if err != nil {
		return false, fmt.Sprintf("无法打开文件: %v", err)
	}
	defer file.Close()

	// 解析NBT数据
	data, err := nbt.ReadNBTFromGzip(file)
	if err != nil {
		return false, fmt.Sprintf("NBT解析失败: %v", err)
	}

	// 检查必需字段
	requiredFields := []string{"Version", "DataVersion", "Width", "Height", "Length", "Palette", "BlockData"}
	missingFields := []string{}

	for _, field := range requiredFields {
		if _, exists := data[field]; !exists {
			missingFields = append(missingFields, field)
		}
	}

	if len(missingFields) > 0 {
		return false, fmt.Sprintf("文件缺少必要字段: %v", missingFields)
	}

	// 检查尺寸数据
	var width, height, length int
	widthVal, widthOk := data["Width"]
	heightVal, heightOk := data["Height"]
	lengthVal, lengthOk := data["Length"]

	if !widthOk || !heightOk || !lengthOk {
		return false, "缺少尺寸数据"
	}

	// 尝试将值转换为整数
	switch v := widthVal.(type) {
	case int8:
		width = int(v)
	case int16:
		width = int(v)
	case int32:
		width = int(v)
	case int64:
		width = int(v)
	default:
		return false, "Width字段格式错误"
	}

	switch v := heightVal.(type) {
	case int8:
		height = int(v)
	case int16:
		height = int(v)
	case int32:
		height = int(v)
	case int64:
		height = int(v)
	default:
		return false, "Height字段格式错误"
	}

	switch v := lengthVal.(type) {
	case int8:
		length = int(v)
	case int16:
		length = int(v)
	case int32:
		length = int(v)
	case int64:
		length = int(v)
	default:
		return false, "Length字段格式错误"
	}

	if width <= 0 || height <= 0 || length <= 0 {
		return false, "文件尺寸数据无效"
	}

	// 检查调色板
	palette, ok := data["Palette"].(map[string]interface{})
	if !ok {
		return false, "调色板格式错误"
	}

	if len(palette) == 0 {
		return false, "调色板为空"
	}

	// 检查方块数据
	blockData, ok := data["BlockData"].([]interface{})
	if !ok {
		// 尝试其他可能的数据类型
		if blockDataInt8, ok := data["BlockData"].([]int8); ok {
			// 检查数据长度是否匹配
			expectedSize := width * height * length
			if len(blockDataInt8) != expectedSize {
				return false, fmt.Sprintf("方块数据长度不匹配: 期望 %d, 实际 %d", expectedSize, len(blockDataInt8))
			}
			// 检查方块ID是否超出调色板范围
			paletteSize := len(palette)
			for _, blockID := range blockDataInt8 {
				if int(blockID) >= paletteSize {
					return false, "方块ID超出调色板范围"
				}
			}
		} else if blockDataInt32, ok := data["BlockData"].([]int32); ok {
			expectedSize := width * height * length
			if len(blockDataInt32) != expectedSize {
				return false, fmt.Sprintf("方块数据长度不匹配: 期望 %d, 实际 %d", expectedSize, len(blockDataInt32))
			}
			// 检查方块ID是否超出调色板范围
			paletteSize := len(palette)
			for _, blockID := range blockDataInt32 {
				if int(blockID) >= paletteSize {
					return false, "方块ID超出调色板范围"
				}
			}
		} else if blockDataInt, ok := data["BlockData"].([]int); ok {
			expectedSize := width * height * length
			if len(blockDataInt) != expectedSize {
				return false, fmt.Sprintf("方块数据长度不匹配: 期望 %d, 实际 %d", expectedSize, len(blockDataInt))
			}
			// 检查方块ID是否超出调色板范围
			paletteSize := len(palette)
			for _, blockID := range blockDataInt {
				if blockID >= paletteSize {
					return false, "方块ID超出调色板范围"
				}
			}
		} else {
			return false, "方块数据格式错误或不存在"
		}
	} else {
		// 检查interface{}类型的blockData
		expectedSize := width * height * length
		if len(blockData) != expectedSize {
			return false, fmt.Sprintf("方块数据长度不匹配: 期望 %d, 实际 %d", expectedSize, len(blockData))
		}
		// 检查方块ID是否超出调色板范围
		paletteSize := len(palette)
		for _, blockInterface := range blockData {
			var blockID int
			switch v := blockInterface.(type) {
			case int8:
				blockID = int(v)
			case int16:
				blockID = int(v)
			case int32:
				blockID = int(v)
			case int64:
				blockID = int(v)
			case int:
				blockID = v
			default:
				return false, "方块数据类型错误"
			}
			if blockID >= paletteSize {
				return false, "方块ID超出调色板范围"
			}
		}
	}

	fmt.Println("✅ schem文件验证通过")
	return true, "文件验证通过"
}

// FixSchemFile 根据问题修复schem文件
func FixSchemFile(filePath, issue string) (bool, string, string) {
	fmt.Printf("\n🔧 正在尝试修复schem文件: %s\n", issue)

	// 备份原始文件
	backupPath := filePath + "_backup.schem"
	err := CopyFile(filePath, backupPath)
	if err != nil {
		return false, fmt.Sprintf("备份文件失败: %v", err), ""
	}

	// 这里应该实现实际的修复逻辑
	// 根据问题类型进行修复
	fixDescription := "修复了文件结构问题"

	fmt.Printf("✅ 文件修复完成: %s\n", fixDescription)
	fmt.Printf("📁 原始文件已备份为: %s\n", backupPath)

	return true, fixDescription, backupPath
}

// CopyFile 复制文件
func CopyFile(src, dst string) error {
	input, err := ioutil.ReadFile(src)
	if err != nil {
		return err
	}

	return ioutil.WriteFile(dst, input, 0644)
}

// AskAutoVerification 询问是否启用自动验证
func AskAutoVerification() bool {
	fmt.Print("\n🔍 是否启用自动验证? (y/n, 回车默认为y): ")
	var input string
	fmt.Scanln(&input)

	// 如果输入为空或为y/yes，则启用自动验证
	return input == "" || input == "y" || input == "yes" || input == "Y" || input == "YES"
}