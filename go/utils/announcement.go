package utils

import (
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"
)

// GetLatestAnnouncement 获取最新公告
func GetLatestAnnouncement() (string, string, error) {
	announcementURL := "https://raw.githubusercontent.com/suibian-sun/SunPixel/refs/heads/main/app/Changelog/new.md"
	
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	
	resp, err := client.Get(announcementURL)
	if err != nil {
		return "", "", fmt.Errorf("无法获取最新公告: %v", err)
	}
	defer resp.Body.Close()
	
	content, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", "", fmt.Errorf("无法读取公告内容: %v", err)
	}
	
	contentStr := strings.TrimSpace(string(content))
	dateStr := extractDateFromContent(contentStr)
	
	return dateStr, contentStr, nil
}

// extractDateFromContent 从内容中提取日期
func extractDateFromContent(content string) string {
	datePattern := regexp.MustCompile(`\b(\d{4}-\d{1,2}-\d{1,2})\b`)
	matches := datePattern.FindStringSubmatch(content)
	
	if len(matches) > 1 {
		return matches[1]
	}
	
	// 如果没有找到日期，返回当前日期
	return time.Now().Format("2006-01-02")
}

// FormatAnnouncementContent 格式化公告内容
func FormatAnnouncementContent(content string) string {
	lines := strings.Split(content, "\n")
	var formattedLines []string
	
	for i, line := range lines {
		formattedLines = append(formattedLines, line)
		if strings.Contains(line, "更新内容如下") && i+1 < len(lines) && strings.TrimSpace(lines[i+1]) != "" {
			formattedLines = append(formattedLines, "")
		}
	}
	
	return strings.Join(formattedLines, "\n")
}

// DisplayAnnouncement 显示最新公告
func DisplayAnnouncement() {
	dateStr, content, err := GetLatestAnnouncement()
	if err != nil {
		fmt.Printf("%s⚠️  无法获取最新公告: %v%s\n", Red, err, Reset)
		return
	}
	
	formattedContent := FormatAnnouncementContent(content)
	lines := strings.Split(formattedContent, "\n")
	
	// 计算最大行长度以确定框宽度
	maxLineLength := 0
	for _, line := range lines {
		if len(line) > maxLineLength {
			maxLineLength = len(line)
		}
	}
	
	boxWidth := maxLineLength + 4
	if boxWidth < 60 {
		boxWidth = 60
	}
	
	// 使用边框字符
	topBorder := "╔" + strings.Repeat("═", boxWidth-2) + "╗"
	bottomBorder := "╚" + strings.Repeat("═", boxWidth-2) + "╝"
	
	var formattedLines []string
	
	// 创建标题行
	titleLine := fmt.Sprintf("║ 📅 发布日期: %s", dateStr)
	padding := boxWidth - len(titleLine) - 1
	if padding > 0 {
		titleLine += strings.Repeat(" ", padding) + "║"
	} else {
		titleLine += "║"
	}
	
	// 添加标题到格式化行中
	formattedLines = append(formattedLines, titleLine)
	
	for _, line := range lines {
		if strings.TrimSpace(line) != "" {
			// 处理长行，自动换行
			for len(line) > boxWidth-4 {
				segment := line[:boxWidth-4]
				formattedLine := fmt.Sprintf("║ %s", segment)
				padding := boxWidth - len(formattedLine) - 1
				if padding > 0 {
					formattedLines = append(formattedLines, formattedLine+strings.Repeat(" ", padding)+"║")
				} else {
					formattedLines = append(formattedLines, formattedLine+"║")
				}
				line = line[boxWidth-4:]
			}
			
			if strings.TrimSpace(line) != "" {
				formattedLine := fmt.Sprintf("║ %s", line)
				padding := boxWidth - len(formattedLine) - 1
				if padding > 0 {
					formattedLines = append(formattedLines, formattedLine+strings.Repeat(" ", padding)+"║")
				} else {
					formattedLines = append(formattedLines, formattedLine+"║")
				}
			}
		} else {
			formattedLine := fmt.Sprintf("║%s║", strings.Repeat(" ", boxWidth-2))
			formattedLines = append(formattedLines, formattedLine)
		}
	}
	
	// 打印公告标题和边框
	fmt.Printf("\n%s📢 最新公告%s\n", Cyan, Reset)
	fmt.Println(topBorder)
	for _, line := range formattedLines {
		fmt.Println(line)
	}
	fmt.Println(bottomBorder)
}