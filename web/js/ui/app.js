import {
  BLOCK_NAMES,
  BLOCK_DISPLAY_NAMES,
  getImagePixels,
  processPixels
} from '../converter.js';
import { generateOutput, FORMAT_EXTENSIONS } from '../formatter.js';
import { renderTextToImageData, colorizeText } from '../core/text-art.js';

const { createApp, ref, computed, onMounted, onBeforeUnmount, watch, nextTick } = Vue;

const COMMON_BLOCKS = ['wool', 'concrete', 'terracotta', 'glass'];

/** 单边最大像素与单文件最大体积，避免超大图把主线程卡死 */
const MAX_IMAGE_DIMENSION = 8192;
const MAX_IMAGE_BYTES = 40 * 1024 * 1024;
const PREVIEW_BOX_HEIGHT = 240;

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
    const textColor = ref('#111111');
    const textTransparent = ref(true);
    const textThreshold = ref(110);

    const FONT_STACKS = {
      system: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif',
      serif: '"Songti SC", "SimSun", "Noto Serif SC", serif',
      mono: '"JetBrains Mono", Consolas, "Courier New", monospace',
      heiti: '"Heiti SC", "Microsoft YaHei", "Noto Sans SC", sans-serif'
    };

    /* ---------------- 运行状态 ---------------- */
    const hasImage = ref(false);
    const uploadedFileName = ref('');
    const imageUrl = ref('');
    const originalPreview = ref('');
    const imageSize = ref('');
    const showPreview = ref(false);
    const showResult = ref(false);
    const showChangelog = ref(false);
    const progress = ref(0);
    const progressMessage = ref('');
    const errorMessage = ref('');
    const isConverting = ref(false);
    const changelogs = ref([]);
    const fileInput = ref(null);
    const previewCanvas = ref(null);
    const originalImg = ref(null);
    const hasPreview = ref(false);
    const previewSize = ref('');

    const stats = ref({ width: 0, height: 0, totalBlocks: 0, blockTypes: 0, elapsed: '—' });
    const materials = ref([]);
    const downloadBlob = ref(null);
    const downloadFilename = ref('');
    const toast = ref(null);
    // 每完成一轮转换 +1，外部（自动化测试）可据此判断本轮是否结束。
    // 根容器上的属性绑定不会生效（#app 只是挂载点），所以写在 <html> 的 dataset 上。
    const runCount = ref(0);
    document.documentElement.dataset.run = '0';

    let result = null;
    let imageElement = null;
    let imageNatural = { width: 0, height: 0 };
    let aspect = 1;
    let runToken = 0;
    let debounceTimer = null;
    let toastTimer = null;

    /* ---------------- 计算属性 ---------------- */
    const displayBlocks = computed(() =>
      allBlocks.value.map((id) => ({ id, name: BLOCK_DISPLAY_NAMES[id] || id }))
    );

    const hasSource = computed(() => {
      if (mode.value === 'text') return text.value.trim().length > 0;
      return hasImage.value;
    });

    const canConvert = computed(() => hasSource.value && selectedBlocks.value.length > 0);

    /* ---------------- 尺寸联动 ---------------- */
    let syncing = false;
    watch(width, (value) => {
      if (syncing || !lockAspect.value || mode.value !== 'image' || !hasImage.value) return;
      syncing = true;
      height.value = clampSize(Math.round(value / aspect));
      syncing = false;
    });
    watch(height, (value) => {
      if (syncing || !lockAspect.value || mode.value !== 'image' || !hasImage.value) return;
      syncing = true;
      width.value = clampSize(Math.round(value * aspect));
      syncing = false;
    });

    /* ---------------- 交互 ---------------- */
    function clampSize(value) {
      if (!Number.isFinite(value)) return 1;
      return Math.min(512, Math.max(1, value));
    }

    function triggerFileInput() {
      fileInput.value?.click();
    }

    function handleDrop(event) {
      const file = event.dataTransfer?.files?.[0];
      if (file) processFile(file);
    }

    function handleFileUpload(event) {
      const file = event.target.files?.[0];
      if (file) processFile(file);
      // 允许重复选择同一文件
      event.target.value = '';
    }

    function processFile(file) {
      if (!file.type.startsWith('image/')) {
        notify('请选择图片文件', 'error');
        return;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        notify('图片过大，请压缩到 40MB 以内', 'error');
        return;
      }
      const reader = new FileReader();
      reader.onload = (event) => loadImage(event.target.result, file.name);
      reader.onerror = () => notify('读取文件失败', 'error');
      reader.readAsDataURL(file);
    }

    function loadImage(src, name) {
      const img = new Image();
      // 必须在设置 src 前声明跨域，否则外部图片会污染 canvas
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        if (img.naturalWidth > MAX_IMAGE_DIMENSION || img.naturalHeight > MAX_IMAGE_DIMENSION) {
          notify(`图片尺寸超过 ${MAX_IMAGE_DIMENSION}px，请先缩小`, 'error');
          return;
        }
        imageElement = img;
        imageNatural = { width: img.naturalWidth, height: img.naturalHeight };
        hasImage.value = true;
        aspect = img.naturalWidth / Math.max(1, img.naturalHeight);
        uploadedFileName.value = name || '网络图片';
        originalPreview.value = src;
        imageSize.value = `${img.naturalWidth} × ${img.naturalHeight}`;
        showPreview.value = true;
        if (lockAspect.value) {
          const nextHeight = clampSize(Math.round(width.value / aspect));
          if (nextHeight !== height.value) {
            syncing = true;
            height.value = nextHeight;
            syncing = false;
          }
        }
        notify('图片已载入', 'success');
        nextTick(() => fitMedia(originalImg.value, imageNatural.width, imageNatural.height));
        scheduleRun(0);
      };
      img.onerror = () => {
        notify('图片载入失败：地址无效，或对方服务器不允许跨域读取', 'error');
      };
      img.src = src;
    }

    function loadImageFromUrl() {
      const url = imageUrl.value.trim();
      if (!url) return;
      if (!/^(https?:|data:image\/)/i.test(url)) {
        notify('请填写 http(s) 开头的图片链接', 'error');
        return;
      }
      loadImage(url, url.split('/').pop()?.split('?')[0] || '网络图片');
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
        const ids = Array.isArray(list)
          ? list.map((item) => (typeof item === 'string' ? item : item?.id)).filter((id) => id && BLOCK_NAMES.includes(id))
          : [];
        if (ids.length) allBlocks.value = ids;
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
        if (!response.ok) throw new Error('接口不可用');
        const list = await response.json();
        changelogs.value = Array.isArray(list) ? list : [];
      } catch {
        changelogs.value = [];
      }
    }

    /* ---------------- 素材 ---------------- */
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

    /* ---------------- 主流程 ---------------- */
    function scheduleRun(delay = 280) {
      if (!hasSource.value || !selectedBlocks.value.length) return;
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        debounceTimer = null;
        run({ silent: true });
      }, delay);
    }

    async function startConversion() {
      if (!canConvert.value) {
        notify(mode.value === 'text' ? '请输入文字并选择方块' : '请先选择图片', 'error');
        return;
      }
      await run({ silent: false });
    }

    /**
     * 完整流程：取像素 → 量化 → 生成文件 → 画效果图
     * silent 为 true 时（参数变化触发的自动刷新）不显示进度，避免闪烁。
     */
    async function run({ silent }) {
      const token = ++runToken;
      if (!silent) {
        isConverting.value = true;
        errorMessage.value = '';
      }
      progress.value = 10;
      progressMessage.value = mode.value === 'text' ? '渲染文字' : '读取像素';
      const started = Date.now();

      try {
        const imageData = buildImageData();
        if (token !== runToken) return;

        progress.value = 45;
        progressMessage.value = '匹配方块颜色';
        await nextTick();

        const next = processPixels(imageData, selectedBlocks.value, {
          metric: metric.value,
          dither: dither.value,
          serpentine: serpentine.value,
          alphaThreshold: Number(alphaThreshold.value),
          plane: plane.value,
          rotate: Number(rotate.value),
          mirrorX: mirrorX.value,
          mirrorY: mirrorY.value
        });
        if (token !== runToken) return;
        result = next;

        progress.value = 75;
        progressMessage.value = '生成文件';
        await nextTick();

        await generateCurrentFile(token);
        if (token !== runToken) return;

        progress.value = 95;
        progressMessage.value = '绘制预览';
        // 预览容器是 v-if，必须先让它进入 DOM，canvas 的 ref 才存在
        showPreview.value = true;
        await nextTick();
        drawPreview(result);

        const elapsedMs = Date.now() - started;
        const elapsed = elapsedMs < 1000 ? `${elapsedMs}ms` : `${(elapsedMs / 1000).toFixed(2)}s`;
        const isWall = plane.value === 'xy';
        stats.value = {
          width: result.size.x,
          height: isWall ? result.size.y : result.size.z,
          totalBlocks: result.totalBlocks,
          blockTypes: result.counts.size,
          elapsed
        };
        materials.value = [...result.counts.entries()]
          .map(([block, count]) => ({ block: shorten(block), count }))
          .sort((a, b) => b.count - a.count || a.block.localeCompare(b.block));

        showResult.value = true;
        errorMessage.value = '';
        progress.value = 100;
        progressMessage.value = '完成';
        runCount.value += 1;
        document.documentElement.dataset.run = String(runCount.value);
      } catch (error) {
        if (token !== runToken) return;
        errorMessage.value = `转换失败：${error.message}`;
        // 失败时清掉旧文件，避免下载到上一轮的结果
        downloadBlob.value = null;
        downloadFilename.value = '';
        showResult.value = false;
        if (!silent) console.error(error);
      } finally {
        if (token === runToken) isConverting.value = false;
      }
    }

    /** 按当前格式生成可下载文件 */
    async function generateCurrentFile(token) {
      if (!result) return;
      const output = await generateOutput(result, format.value, `sunpixel_${mode.value}`, {
        name: mode.value === 'text'
          ? `文字像素画 ${text.value.split('\n')[0].slice(0, 12)}`
          : 'SunPixel 像素画'
      });
      if (token !== undefined && token !== runToken) return;
      downloadBlob.value = output.blob;
      downloadFilename.value = output.filename;
    }

    /* ---------------- 预览 ---------------- */
    /**
     * 按实际摆放方向把体素投影成平面图：
     *  - 平铺（xz）：从上方看，行 = Z
     *  - 竖立（xy）：从正面看，行 = Y（第 0 行在最上方）
     */
    function drawPreview(current) {
      const canvas = previewCanvas.value;
      if (!canvas) return;

      const { size, volume, colors, plane: planeMode } = current;
      const isWall = planeMode === 'xy';
      const w = size.x;
      const h = isWall ? size.y : size.z;

      canvas.width = w;
      canvas.height = h;

      const ctx = canvas.getContext('2d');
      const image = ctx.createImageData(w, h);
      const pixels = image.data;

      for (let row = 0; row < h; row++) {
        for (let x = 0; x < w; x++) {
          const y = isWall ? h - 1 - row : 0;
          const z = isWall ? 0 : row;
          const index = volume[(y * size.z + z) * size.x + x];
          const color = colors[index];
          const offset = (row * w + x) * 4;
          if (!color) {
            // 空气保持透明，露出棋盘格
            pixels[offset + 3] = 0;
            continue;
          }
          pixels[offset] = color[0];
          pixels[offset + 1] = color[1];
          pixels[offset + 2] = color[2];
          pixels[offset + 3] = 255;
        }
      }

      ctx.putImageData(image, 0, 0);
      hasPreview.value = true;
      previewSize.value = `${w} × ${h}`;
      fitMedia(canvas, w, h);
    }

    /**
     * 把图片/画布等比缩放到预览框内（不超过 PREVIEW_BOX_HEIGHT）。
     * 不能只靠 CSS：小尺寸像素画需要放大才看得清，而 width:100% 又会把长图拉得过高。
     */
    function fitMedia(element, w, h) {
      if (!element || !w || !h) return;

      const grid = element.closest('.preview');
      const gap = 16;
      const figurePadding = 26; // 1px 边框 + 12px 内边距
      let columnWidth = 340;

      if (grid) {
        // 直接由栅格宽度推算列宽：figure 自身的 clientWidth 在刚插入时还没定下来，
        // 用它会算出偏小的值，导致两张预览图宽度不一致。
        // 列数从计算样式里读，窄屏会变成单列，写死 2 列会让手机上的预览缩得过小。
        const available = grid.clientWidth || 820;
        const columns = (getComputedStyle(grid).gridTemplateColumns || '').split(' ').filter(Boolean).length || 1;
        columnWidth = (available - gap * (columns - 1)) / columns - figurePadding;
      }

      const scale = Math.max(0.02, Math.min(columnWidth / w, PREVIEW_BOX_HEIGHT / h));
      element.style.width = `${Math.round(w * scale)}px`;
      element.style.height = `${Math.round(h * scale)}px`;
    }

    async function downloadFile() {
      if (!downloadBlob.value) return;
      triggerDownload(downloadBlob.value, downloadFilename.value);
    }

    async function downloadExtra(kind) {
      if (!result) return;
      const names = { blueprint: '搭建图纸', csv: '材料清单' };
      try {
        const output = await generateOutput(result, kind, `sunpixel_${kind}`, { name: 'SunPixel 像素画' });
        triggerDownload(output.blob, output.filename);
      } catch (error) {
        notify(`${names[kind] || kind}导出失败：${error.message}`, 'error');
      }
    }

    function triggerDownload(blob, filename) {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    }

    /* ---------------- 小工具 ---------------- */
    function shorten(name) {
      return String(name).replace('minecraft:', '');
    }

    function hexToRgb(hex) {
      const value = String(hex).replace('#', '');
      const full = value.length === 3 ? value.split('').map((c) => c + c).join('') : value;
      const num = Number.parseInt(full, 16);
      if (!Number.isFinite(num)) return [0, 0, 0];
      return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
    }

    /** 轻提示：只用 textContent，避免文件名/URL 里的内容被当成 HTML */
    function notify(message, type = 'info') {
      if (toastTimer) clearTimeout(toastTimer);
      toast.value = { message, type };
      toastTimer = setTimeout(() => { toast.value = null; }, 2600);
    }

    function formatChangelog(content) {
      const escaped = String(content)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

      return escaped
        .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
        .replace(/^### (.*)$/gm, '<h4>$1</h4>')
        .replace(/^## (.*)$/gm, '<h3>$1</h3>')
        .replace(/^# (.*)$/gm, '<h3>$1</h3>')
        .replace(/^&gt; (.*)$/gm, '<blockquote>$1</blockquote>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
        .replace(/^- (.*)$/gm, '<li>$1</li>')
        .replace(/((?:<li>[\s\S]*?<\/li>)+)/g, (match) => `<ul>${match}</ul>`)
        .replace(/\n{2,}/g, '<br><br>')
        .replace(/\n/g, '<br>')
        .replace(/<\/ul><br>/g, '</ul>');
    }

    /* ---------------- 生命周期 ---------------- */
    function handleResize() {
      if (result) drawPreview(result);
      if (hasImage.value) fitMedia(originalImg.value, imageNatural.width, imageNatural.height);
    }

    onMounted(() => {
      loadAvailableBlocks();
      loadChangelog();
      window.addEventListener('resize', handleResize);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleResize);
      if (debounceTimer) clearTimeout(debounceTimer);
      if (toastTimer) clearTimeout(toastTimer);
    });

    /* ---------------- 参数变化自动重算 ---------------- */
    watch(
      [
        mode, width, height, plane, rotate, mirrorX, mirrorY, metric, dither, serpentine,
        alphaThreshold, smoothScale, selectedBlocks, text, fontFamily, fontSize, bold,
        italic, align, lineHeight, letterSpacing, textColor, textTransparent, textThreshold
      ],
      () => scheduleRun(),
      { deep: true }
    );

    // 切换输出格式只重算文件，不必重跑像素流程
    watch(format, async () => {
      if (!result) return;
      try {
        await generateCurrentFile();
      } catch (error) {
        notify(`生成失败：${error.message}`, 'error');
      }
    });

    return {
      mode, format, width, height, lockAspect, plane, rotate, mirrorX, mirrorY,
      metric, dither, serpentine, alphaThreshold, smoothScale,
      allBlocks, selectedBlocks, displayBlocks,
      text, fontFamily, fontSize, bold, italic, align, lineHeight, letterSpacing,
      textColor, textTransparent, textThreshold,
      uploadedFileName, imageUrl, originalPreview, imageSize, hasImage,
      showPreview, showResult, showChangelog, hasPreview, previewSize,
      progress, progressMessage, errorMessage, isConverting, changelogs, fileInput,
      previewCanvas, originalImg, stats, materials, canConvert, downloadFilename, toast, runCount,
      triggerFileInput, handleDrop, handleFileUpload, loadImageFromUrl,
      toggleBlock, selectAll, clearAll, selectCommon,
      startConversion, downloadFile, downloadExtra,
      formatChangelog, notify, FORMAT_EXTENSIONS
    };
  }
}).mount('#app');
