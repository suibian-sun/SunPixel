package utils

import (
	"fmt"
	"runtime"
	"sync"
	"time"
)

// ResourceMonitor 资源监控器
type ResourceMonitor struct {
	maxMemoryMB float64
	running     bool
	mutex       sync.RWMutex
}

// NewResourceMonitor 创建新的资源监控器
func NewResourceMonitor() *ResourceMonitor {
	return &ResourceMonitor{
		maxMemoryMB: 0,
		running:     false,
	}
}

// Start 启动资源监控
func (rm *ResourceMonitor) Start() {
	if rm.running {
		return
	}

	rm.running = true
	go rm.monitorLoop()
	fmt.Println("📊 资源监控已启动")
}

// Stop 停止资源监控
func (rm *ResourceMonitor) Stop() {
	rm.running = false
	fmt.Println("📊 资源监控已停止")
}

// monitorLoop 监控循环
func (rm *ResourceMonitor) monitorLoop() {
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for rm.running {
		select {
		case <-ticker.C:
			var m runtime.MemStats
			runtime.ReadMemStats(&m)
			
			// 获取内存使用（MB）
			currentMB := float64(m.Alloc) / 1024 / 1024
			
			rm.mutex.Lock()
			if currentMB > rm.maxMemoryMB {
				rm.maxMemoryMB = currentMB
			}
			rm.mutex.Unlock()
		}
	}
}

// GetMaxMemoryUsage 获取最高内存占用
func (rm *ResourceMonitor) GetMaxMemoryUsage() float64 {
	rm.mutex.RLock()
	defer rm.mutex.RUnlock()
	return rm.maxMemoryMB
}

// ShowMaxResourceUsage 展示最高资源占用
func (rm *ResourceMonitor) ShowMaxResourceUsage() {
	rm.Stop()
	
	maxMemory := rm.GetMaxMemoryUsage()
	
	fmt.Println()
	fmt.Println("==================================================")
	fmt.Println("📊 程序运行资源统计")
	fmt.Println("==================================================")
	fmt.Printf("最高内存占用: %.2f MB\n", maxMemory)
	fmt.Println("==================================================")
}