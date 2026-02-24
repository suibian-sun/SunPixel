package config

import (
    "encoding/json"
    "os"
)

// Config 应用配置
type Config struct {
    General struct {
        Language       string `json:"language"`
        OutputDirectory string `json:"output_directory"`
    } `json:"general"`
    UI struct {
        ColoredOutput bool `json:"colored_output"`
    } `json:"ui"`
    Features struct {
        AutoVerification bool `json:"auto_verification"`
        ShowAnnouncement bool `json:"show_announcement"`
    } `json:"features"`
}

// LoadConfig 从文件加载配置
func LoadConfig(configPath string) (*Config, error) {
    config := &Config{
        General: struct {
            Language       string `json:"language"`
            OutputDirectory string `json:"output_directory"`
        }{
            Language:       "zh_CN",
            OutputDirectory: "output",
        },
        UI: struct {
            ColoredOutput bool `json:"colored_output"`
        }{
            ColoredOutput: true,
        },
        Features: struct {
            AutoVerification bool `json:"auto_verification"`
            ShowAnnouncement bool `json:"show_announcement"`
        }{
            AutoVerification: true,
            ShowAnnouncement: true,
        },
    }
    
    if _, err := os.Stat(configPath); err == nil {
        data, err := os.ReadFile(configPath)
        if err == nil {
            json.Unmarshal(data, config)
        }
    }
    
    return config, nil
}

// SaveConfig 保存配置到文件
func (c *Config) SaveConfig(configPath string) error {
    data, err := json.MarshalIndent(c, "", "  ")
    if err != nil {
        return err
    }
    
    return os.WriteFile(configPath, data, 0644)
}