package message

import (
    "encoding/json"
    "os"
)

// Messages 国际化消息
type Messages struct {
    LangCode string            `json:"lang_code"`
    Messages map[string]string `json:"messages"`
}

// LoadMessages 加载指定语言的消息
func LoadMessages(langCode string) (*Messages, error) {
    // 默认消息
    defaultMessages := map[string]string{
        "welcome":          "欢迎使用 SunPixel!",
        "input_file":       "请输入图片文件路径",
        "output_file":      "输出文件",
        "conversion_start": "开始转换...",
        "conversion_done":  "转换完成!",
        "error":            "错误",
        "success":          "成功",
        "block_not_found":  "未找到方块文件",
        "image_load_fail":  "图片加载失败",
    }
    
    msg := &Messages{
        LangCode: langCode,
        Messages: defaultMessages,
    }
    
    // 尝试从文件加载特定语言的消息
    filePath := "message/" + langCode + ".json"
    if _, err := os.Stat(filePath); err == nil {
        data, err := os.ReadFile(filePath)
        if err == nil {
            var fileMsg map[string]string
            if json.Unmarshal(data, &fileMsg) == nil {
                for k, v := range fileMsg {
                    msg.Messages[k] = v
                }
            }
        }
    }
    
    return msg, nil
}

// Get 获取指定键的消息
func (m *Messages) Get(key string) string {
    if msg, exists := m.Messages[key]; exists {
        return msg
    }
    return key // 返回键名作为默认值
}