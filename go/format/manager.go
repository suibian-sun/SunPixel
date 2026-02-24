package format

import "fmt"

// BlockColorMap 定义方块颜色映射
type BlockColorMap map[string][]string

// ConverterManager 转换器管理器
type ConverterManager struct {
    converters map[string]Converter
}

// NewConverterManager 创建新的转换器管理器
func NewConverterManager() *ConverterManager {
    manager := &ConverterManager{
        converters: make(map[string]Converter),
    }
    
    // 注册内置转换器
    manager.RegisterConverter("schem", NewSchemConverter())
    manager.RegisterConverter("json", NewJSONConverter())
    
    return manager
}

// RegisterConverter 注册转换器
func (cm *ConverterManager) RegisterConverter(formatName string, converter Converter) {
    cm.converters[formatName] = converter
}

// GetConverter 获取指定格式的转换器
func (cm *ConverterManager) GetConverter(formatName string) (Converter, error) {
    converter, exists := cm.converters[formatName]
    if !exists {
        return nil, fmt.Errorf("不支持的格式: %s", formatName)
    }
    return converter, nil
}

// GetAvailableFormats 获取所有可用格式
func (cm *ConverterManager) GetAvailableFormats() []string {
    formats := make([]string, 0, len(cm.converters))
    for formatName := range cm.converters {
        formats = append(formats, formatName)
    }
    return formats
}