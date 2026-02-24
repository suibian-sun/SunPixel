package format

// ColorInfo 存储颜色信息的结构
type ColorInfo struct {
    R, G, B uint8
    BlockName string
    BlockData int8
}

// ProgressCallback 定义进度回调函数类型
type ProgressCallback func(current, total int, message string)

// Converter 定义转换器接口
type Converter interface {
    Convert(inputPath, outputPath string, width, height int, selectedBlocks []string) error
    GetFormatName() string
    GetExtension() string
    // SetProgressCallback 设置进度回调函数
    SetProgressCallback(callback ProgressCallback)
}