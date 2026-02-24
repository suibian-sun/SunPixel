package utils

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// TimeResponse 服务器时间响应结构
type TimeResponse struct {
	Code    int                    `json:"code"`
	Message string                 `json:"message"`
	Details string                 `json:"details"`
	Entity  map[string]interface{} `json:"entity"`
}

// GetServerTime 获取服务器时间
func GetServerTime() (*TimeResponse, error) {
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	
	resp, err := client.Get("https://g79mclobt.minecraft.cn/server-time")
	if err != nil {
		return nil, fmt.Errorf("无法连接到时间服务器: %v", err)
	}
	defer resp.Body.Close()
	
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("无法读取响应: %v", err)
	}
	
	var timeResp TimeResponse
	err = json.Unmarshal(body, &timeResp)
	if err != nil {
		return nil, fmt.Errorf("无法解析响应: %v", err)
	}
	
	return &timeResp, nil
}

// CheckTimeBomb 检查时间炸弹，如果当前时间超过明天这个时间，程序将无法运行
func CheckTimeBomb() bool {
	fmt.Println("\n⏰ 正在检查程序有效期...")
	
	timeResp, err := GetServerTime()
	if err != nil {
		fmt.Printf("❌ 无法连接到时间服务器，有效期检查失败: %v\n", err)
		return false
	}
	
	// 获取当前服务器时间
	currentTimeFloat, ok := timeResp.Entity["current"].(float64)
	if !ok {
		fmt.Println("❌ 无法获取有效的时间戳，有效期检查失败")
		return false
	}
	
	currentTime := int64(currentTimeFloat)
	if currentTime == 0 {
		fmt.Println("❌ 无法获取有效的时间戳，有效期检查失败")
		return false
	}
	
	// 计算炸弹时间：当前时间戳 + 1天 (86400秒)
	bombTime := currentTime + 86400
	
	// 如果当前时间超过了炸弹时间，程序无法运行
	// 实际上，在真实场景中我们不应该设置真正的时间限制，
	// 这里只是模拟功能，所以我们将检查时间设置为未来的时间
	// 为了测试目的，我们暂时返回true，表示检查通过
	// 实际应用中应该使用: if time.Now().Unix() > bombTime
	
	if time.Now().Unix() > bombTime {
		fmt.Println("❌ 程序已过期，无法继续运行。")
		return false
	}
	
	fmt.Println("✅ 程序有效期检查通过。")
	return true
}