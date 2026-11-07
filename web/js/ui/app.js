import {
  BLOCK_NAMES,
  BLOCK_DISPLAY_NAMES,
  getImagePixels,
  processPixels,
  generatePreview
} from '../converter.js';
import { generateOutput, FORMAT_EXTENSIONS } from '../formatter.js';
import { renderTextToImageData, colorizeText } from '../core/text-art.js';

const { createApp, ref, computed, onMounted, watch } = Vue;

const COMMON_BLOCKS = ['wool', 'concrete', 'terracotta', 'glass'];

createApp({
  setup() {
    /* ---------------- 基础状态 ---------------- */
    const mode = ref('image');
    const format = ref('schem');
    const width = ref(128);
    const height = ref(128);
    const lockAspect = ref(true);
    const plane = ref('xz');
    const rotate = ref(0);
    const mirrorX = ref(false);
    const mirrorY = ref(false);

    const metric = ref('lab');
    const dither = ref('none');
    const serpentine = ref(true);
    const alphaThreshold = ref(128);
    const smoothScale = ref(true);

    const allBlocks = ref([...BLOCK_NAMES]);
    const selectedBlocks = ref(['wool', 'concrete']);

    /* ---------------- 文字模式 ---------------- */
    const text = ref('SunPixel');
    const fontFamily = ref('system');
    const fontSize = ref(96);
    const bold = ref(true);
    const italic = ref(false);
    const align = ref('center');
    const lineHeight = ref(1.1);
    const letterSpacing = ref(0);
    const textColor = ref('#1a1a1a');
    const textTransparent = ref(true);
    const textThreshold = ref(110);

    const FONT_STACKS = {
      system: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif',
      serif: '"Songti SC", "SimSun", "Noto Serif SC", serif',
      mono: '"JetBrains Mono", Consolas, "Courier New", monospace',
      heiti: '"Heiti SC", "Microsoft YaHei", "Noto Sans SC", sans-serif'
    };

    /* ---------------- 运行状态 ---------------- */
    const uploadedImage = ref(null);
    const hasImage = ref(false);
    const uploadedFileName = ref('');
    const imageUrl = ref('');
    const originalPreview = ref('');
    const resultPreview = ref('');
    const showPreview = ref(false);
    const showProgress = ref(false);
    const showResult = ref(false);
    const showChangelog = ref(false);
    const progress = ref(0);
    const progressMessage = ref('准备开始转换...');
    const logs = ref([]);
    const isConverting = ref(false);
    const changelogs = ref([]);
    const fileInput = ref(null);

    const stats = ref({ width: 0, height: 0, depth: 1, totalBlocks: 0, blockTypes: 0, airCount: 0, elapsed: 0, commands: 0 });
    const materials = ref([]);
    const downloadBlob = ref(null);
    const downloadFilename = ref('');
    let result = null;
    let imageElement = null;

    /* ---------------- 计算属性 ---------------- */
    const displayBlocks = computed(() =>
      allBlocks.value.map((id) => ({ id, name: BLOCK_DISPLAY_NAMES[id] || id }))
    );

    const aspect = ref(1);

    const progressBarClass = computed(() => {
      const p = progress.value;
      if (p < 30) return 'progress-bar bg-info';
      if (p < 70) return 'progress-bar bg-primary';
      return 'progress-bar bg-success';
    });

    const canConvert = computed(() => {
      if (selectedBlocks.value.length === 0) return false;
      if (mode.value === 'text') return text.value.trim().length > 0;
      return hasImage.value;
    });

    /* ---------------- 尺寸联动 ---------------- */
    let syncing = false;
    watch(width, (value) => {
      if (syncing || !lockAspect.value || mode.value !== 'image' || !imageElement) return;
      syncing = true;
      height.value = Math.max(1, Math.round(value / aspect.value));
      syncing = false;
    });
    watch(height, (value) => {
      if (syncing || !lockAspect.value || mode.value !== 'image' || !imageElement) return;
      syncing = true;
      width.value = Math.max(1, Math.round(value * aspect.value));
      syncing = false;
    });

    // 转换完成后切换输出格式，直接重算文件，不用再点一次「开始转换」
    watch(format, async () => {
      if (!result || isConverting.value) return;
      try {
        const output = await generateOutput(result, format.value, `sunpixel_${mode.value}`, {
          name: mode.value === 'text' ? `文字像素画 ${text.value.split('\n')[0].slice(0, 12)}` : 'SunPixel 像素画'
        });
        downloadBlob.value = output.blob;
        downloadFilename.value = output.filename;
        stats.value = { ...stats.value, commands: output.info.commands || 0 };
      } catch (error) {
        showMessage('生成失败', error.message, 'error');
      }
    });

    /* ---------------- 交互 ---------------- */
    function triggerFileInput() {
      fileInput.value?.click();
    }

    function handleDrop(event) {
      const file = event.dataTransfer.files[0];
      if (file) processFile(file);
    }

    function handleFileUpload(event) {
      const file = event.target.files[0];
      if (file) processFile(file);
    }

    function processFile(file) {
      if (!file.type.startsWith('image/')) {
        showMessage('提示', '请选择图片文件', 'warning');
        return;
      }
      const reader = new FileReader();
      reader.onload = (event) => {
        loadImage(event.target.result, file.name);
      };
      reader.readAsDataURL(file);
    }

    function loadImage(src, name) {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        imageElement = img;
        hasImage.value = true;
        aspect.value = img.naturalWidth / Math.max(1, img.naturalHeight);
        uploadedImage.value = true;
        uploadedFileName.value = name || '网络图片';
        originalPreview.value = src;
        showPreview.value = true;
        if (lockAspect.value) {
          height.value = Math.max(1, Math.round(width.value / aspect.value));
        }
        showMessage('图片已载入', `${img.naturalWidth} × ${img.naturalHeight}`, 'success');
      };
      img.onerror = () => showMessage('载入失败', '图片无法解析，或该地址不允许跨域读取', 'error');
      img.src = src;
    }

    function loadImageFromUrl() {
      const url = imageUrl.value.trim();
      if (!url) return;
      loadImage(url, url.split('/').pop() || '网络图片');
    }

    function toggleBlock(id) {
      const index = selectedBlocks.value.indexOf(id);
      if (index >= 0) selectedBlocks.value.splice(index, 1);
      else selectedBlocks.value.push(id);
    }

    function selectAll() {
      selectedBlocks.value = [...allBlocks.value];
    }

    function clearAll() {
      selectedBlocks.value = [];
    }

    function selectCommon() {
      selectedBlocks.value = COMMON_BLOCKS.filter((id) => allBlocks.value.includes(id));
    }

    async function loadAvailableBlocks() {
      try {
        const response = await fetch('/api/blocks');
        if (!response.ok) throw new Error('接口不可用');
        const list = await response.json();
        if (Array.isArray(list) && list.length) allBlocks.value = list.map((item) => item.id);
      } catch {
        allBlocks.value = [...BLOCK_NAMES];
      }
      if (!selectedBlocks.value.every((id) => allBlocks.value.includes(id))) {
        selectedBlocks.value = allBlocks.value.slice(0, 2);
      }
    }

    async function loadChangelog() {
      try {
        const response = await fetch('/api/changelog');
        changelogs.value = await response.json();
      } catch {
        changelogs.value = [];
      }
    }

    /* ---------------- 转换 ---------------- */
    function buildImageData() {
      if (mode.value === 'text') {
        const rendered = renderTextToImageData(text.value, {
          width: width.value,
          height: height.value,
          fontFamily: FONT_STACKS[fontFamily.value] || FONT_STACKS.system,
          fontSize: fontSize.value,
          bold: bold.value,
          italic: italic.value,
          align: align.value,
          lineHeight: Number(lineHeight.value),
          letterSpacing: Number(letterSpacing.value),
          padding: 2
        });
        return colorizeText(rendered, {
          threshold: Number(textThreshold.value),
          foreground: hexToRgb(textColor.value),
          background: textTransparent.value ? 'transparent' : [255, 255, 255]
        });
      }

      if (!imageElement) throw new Error('请先选择图片');
      return getImagePixels(imageElement, width.value, height.value, { smooth: smoothScale.value });
    }

    async function startConversion() {
      if (!canConvert.value) {
        showMessage('提示', mode.value === 'text' ? '请输入文字并选择方块' : '请先选择图片', 'warning');
        return;
      }

      isConverting.value = true;
      showProgress.value = true;
      showResult.value = false;
      logs.value = [];
      progress.value = 5;
      progressMessage.value = '准备素材...';
      const startTime = Date.now();

      try {
        await sleep(30);
        progress.value = 20;
        progressMessage.value = mode.value === 'text' ? '正在渲染文字...' : '正在读取像素...';
        const imageData = buildImageData();
        logs.value.push(`✅ 素材就绪：${imageData.width} × ${imageData.height}`);
        if (mode.value === 'image') originalPreview.value = originalPreview.value || '';

        progress.value = 45;
        progressMessage.value = '正在匹配方块颜色...';
        await sleep(30);
        result = processPixels(imageData, selectedBlocks.value, {
          metric: metric.value,
          dither: dither.value,
          serpentine: serpentine.value,
          alphaThreshold: Number(alphaThreshold.value),
          plane: plane.value,
          rotate: Number(rotate.value),
          mirrorX: mirrorX.value,
          mirrorY: mirrorY.value
        });
        logs.value.push(`🎨 调色板命中 ${result.counts.size} 种方块`);

        progress.value = 70;
        progressMessage.value = '正在生成投影文件...';
        await sleep(30);
        const output = await generateOutput(result, format.value, `sunpixel_${mode.value}`, {
          name: mode.value === 'text' ? `文字像素画 ${text.value.split('\n')[0].slice(0, 12)}` : 'SunPixel 像素画'
        });
        downloadBlob.value = output.blob;
        downloadFilename.value = output.filename;
        logs.value.push(`📦 已生成 ${output.filename}`);

        progress.value = 90;
        progressMessage.value = '正在绘制效果图...';
        await sleep(20);
        resultPreview.value = generatePreview(result);
        showPreview.value = true;

        const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
        stats.value = {
          width: result.size.x,
          height: plane.value === 'xy' ? result.size.y : result.size.z,
          depth: result.size.y,
          totalBlocks: result.totalBlocks,
          blockTypes: result.counts.size,
          airCount: result.airCount,
          elapsed,
          commands: output.info.commands || 0
        };
        materials.value = [...result.counts.entries()]
          .map(([block, count]) => ({ block: block.replace('minecraft:', ''), count }))
          .sort((a, b) => b.count - a.count);

        progress.value = 100;
        progressMessage.value = '转换完成';
        logs.value.push('✅ 完成');
        showResult.value = true;
      } catch (error) {
        progressMessage.value = `转换失败：${error.message}`;
        logs.value.push(`❌ ${error.message}`);
      } finally {
        isConverting.value = false;
      }
    }

    function downloadFile() {
      if (!downloadBlob.value) return;
      triggerDownload(downloadBlob.value, downloadFilename.value);
    }

    async function downloadExtra(kind) {
      if (!result) return;
      const names = { blueprint: '手动搭建图纸', csv: '材料清单' };
      try {
        const output = await generateOutput(result, kind, `sunpixel_${kind}`, {
          name: 'SunPixel 像素画'
        });
        triggerDownload(output.blob, output.filename);
      } catch (error) {
        showMessage('导出失败', `${names[kind] || kind}：${error.message}`, 'error');
      }
    }

    function triggerDownload(blob, filename) {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    }

    /* ---------------- 小工具 ---------------- */
    function hexToRgb(hex) {
      const value = String(hex).replace('#', '');
      const full = value.length === 3 ? value.split('').map((c) => c + c).join('') : value;
      const num = Number.parseInt(full, 16);
      return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    function logClass(log) {
      if (log.includes('✅')) return 'log-entry log-success';
      if (log.includes('❌')) return 'log-entry log-error';
      return 'log-entry log-info';
    }

    let notifyTimer = null;
    function showMessage(title, message, type = 'info') {
      if (notifyTimer) clearTimeout(notifyTimer);
      document.querySelectorAll('.notification').forEach((node) => node.remove());
      const node = document.createElement('div');
      node.className = 'notification';
      const colors = { success: '#2ecc71', error: '#e74c3c', warning: '#f39c12', info: '#3498db' };
      node.style.background = colors[type] || colors.info;
      node.innerHTML = `<strong>${title}</strong><br>${message}`;
      document.body.appendChild(node);
      notifyTimer = setTimeout(() => {
        node.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => node.remove(), 300);
      }, 2600);
    }

    function formatChangelog(content) {
      let html = String(content)
        .replace(/^### (.*$)/gm, '<h4>$1</h4>')
        .replace(/^## (.*$)/gm, '<h3>$1</h3>')
        .replace(/^# (.*$)/gm, '<h3>$1</h3>')
        .replace(/^> (.*$)/gm, '<blockquote>$1</blockquote>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
      html = html.replace(/^- (.*$)/gm, '<li>$1</li>');
      if (html.includes('<li>')) html = html.replace(/(<li>[\s\S]*?)(?=<br><br>|<h\d|$)/g, (m) => `<ul>${m}</ul>`);
      return html;
    }

    onMounted(() => {
      loadAvailableBlocks();
      loadChangelog();
    });

    return {
      mode, format, width, height, lockAspect, plane, rotate, mirrorX, mirrorY,
      metric, dither, serpentine, alphaThreshold, smoothScale,
      allBlocks, selectedBlocks, displayBlocks,
      text, fontFamily, fontSize, bold, italic, align, lineHeight, letterSpacing,
      textColor, textTransparent, textThreshold,
      uploadedImage, hasImage, uploadedFileName, imageUrl, originalPreview, resultPreview,
      showPreview, showProgress, showResult, showChangelog,
      progress, progressMessage, logs, isConverting, changelogs, fileInput,
      stats, materials, progressBarClass, canConvert, downloadFilename,
      triggerFileInput, handleDrop, handleFileUpload, loadImageFromUrl,
      toggleBlock, selectAll, clearAll, selectCommon,
      startConversion, downloadFile, downloadExtra,
      formatChangelog, logClass, showMessage, FORMAT_EXTENSIONS
    };
  }
}).mount('#app');
