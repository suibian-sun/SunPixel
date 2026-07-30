// Cloudflare Pages Function - 获取更新记录
const changelogData = [
  {
    date: '2026-07-30',
    content: `# SunPixel 最终版本\n\n> SunPixel 最终版本更新已于今日推送。\n>\n> 自2026年7月30日起，至2026年2月5日期间，我们将仅进行Bug修复，不再新增功能内容。\n>\n> 感谢大家一路以来的陪伴与支持。\n>\n> 山高路远，我们有缘再会。\n>\n> —— SunEcology · 2026年7月30日\n\n---\n\n## 版本号：V-2.0.0-final\n\n### ✨ 新增功能\n- [+] **Go 版本新增 Litematic 格式支持**：和 Python 版本一样，现在 Go 版本也支持输出 .litematic 格式文件\n- [+] **Web 版本新增 URL 快速转换**：支持直接粘贴图片 URL 链接进行快速转换\n- [+] **Web 版本新增转换统计信息展示**：转换完成后显示结构尺寸、总方块数、方块类型数、转换耗时等统计信息\n- [+] **Web 版本新增最终版本主题**：采用紫色渐变主题，展示最终版本公告横幅\n\n### 🔧 改进\n- [~] **Web 版本重构为纯 Vue 3 前端**：去除商店、分享圈、朋友圈、用户登录等功能，精简核心体验\n- [~] **精简 Web 后端 API**：仅保留核心图片转换相关接口，提升性能和稳定性\n- [~] **Python CLI 版本**：删除时间炸弹检查机制，优化资源监控模块\n- [~] **Go 版本**：修复 package 冲突问题，确保构建正常\n- [~] **修复 GitHub Actions 工作流构建问题**：删除 SMTP 邮件通知代码，优化工作流配置\n- [~] **完善各版本目录结构**：修复缺失文件，确保版本一致性\n\n### 🌐 版本信息\n- **CLI 版本 (Python)**: 功能完整，支持 .schem / .json / .litematic / .bdx / .mcfunction / .mcstructure / .mcworld 等多种格式\n- **Web 版本**: 基于 Vue 3 的现代化 Web 界面，支持文件上传和客户端转换\n- **Go 版本**: 高性能 Go 语言实现，支持 .schem / .json / .litematic 格式\n\n### 💌 致谢\n感谢所有使用 SunPixel 的用户，是你们的支持让这个项目变得有意义。`
  },
  {
    date: '2025-12-13',
    content: `2025-12-13 SunPixel 更新内容如下：\n\n[+] 新增文件夹"Format"用于存放不同格式的转换主程序，"message"用于存放系统语言文件\n[+] 新增配置文件\n[+] 新增多语言配置\n[~] 优化终端文字显示，使内容不这么枯燥\n[+] 新增文件输出目录自定义配置\n[+] 新增多文件格式转换，目前支持：.schem、.json［RunAway］、.litematic\n[~] 将代码拆分为积木形式，每个代码负责一个部分\n[~] 版本号变更为：V-1.3.1`
  },
  {
    date: '2025-11-28',
    content: `2025-11-28 SunPixel 更新内容如下：\n\n[~] 修复了元数据无法被其他导入器读取的问题\n[+] 新增 SunPixel Web 版本\n[+] 新增 SunPixel 网络 Web 版本\n[+] 新增 SunPixel 各版本使用说明\n[+] 新增文件夹"templates"用于存放网页文件\n[~] 版本号变更为：V1.2.0`
  },
  {
    date: '2025-11-27',
    content: `2025-11-24 SunPixel 更新内容如下：\n\n1. 修改公告文件的来源，从文件获取改为链接获取\n2. 增加彩色(渐变色)logo显示\n3. 添加文件，自动检测功能\n4. 自动检测功能会在自动检测前和自动检测后，两次询问用户是否启用\n5. 添加自动备份原始文件功能，防止用户误操作\n6. 更新区域边框采用自适应模式\n7. 增加开源地址和作者显示\n8. 显示更多转换过程内容提示\n9. 增加格式文件选择\n10. 增加格式文件目录"format"`
  },
  {
    date: '2025-11-14',
    content: `2025-11-14 SunPixel 更新内容如下：\n\n1. 修复 too many values to unpack (expected 3) 的bug\n2. 优化CIL显示\n3. 增加更多方块ID映射，并可自定义转换方块的类型\n4. 增加logo显示\n5. 将输出目录固定为"output"目录\n6. 增加公告目录"Changelog"。用于存放最新更新公告内容`
  }
];

export async function onRequest(context) {
  return new Response(JSON.stringify(changelogData), {
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}