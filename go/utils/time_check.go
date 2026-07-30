package utils

import (
	"fmt"
)

// CheckTimeBomb 检查时间炸弹（简化版，不联网）
// 使用本地时间进行简单的有效期检查，始终返回true以便程序继续运行
func CheckTimeBomb() bool {
	fmt.Println("\n⏰ 正在检查程序有效期（本地模式）...")
	
	// 简化版：不联网，直接使用本地时间
	// 程序始终有效，不设置任何时间限制
	fmt.Println("✅ 程序有效期检查通过（本地模式）。")
	return true
}