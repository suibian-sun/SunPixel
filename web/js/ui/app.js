import {
  BLOCK_NAMES,
  BLOCK_DISPLAY_NAMES,
  getImagePixels,
  processPixels
} from '../converter.js';
import { generateOutput, FORMAT_EXTENSIONS } from '../formatter.js';
import { renderTextToImageData, colorizeText } from '../core/text-art.js';
import { adjustPixels } from '../core/adjust.js';
import { createZip } from '../core/zip.js';
import {
  FILL_BLOCKS,
  pickSettings,
  encodeSettings,
  decodeSettings,
  readStoredSettings,
  writeStoredSettings
} from './settings.js';

const { createApp, ref, computed, onMounted, onBeforeUnmount, watch, nextTick } = Vue;

const COMMON_BLOCKS = ['wool', 'concrete', 'terracotta', 'glass'];
const SIZE_PRESETS = [16, 32, 64, 128, 256];

/** 立体地形柱身的候选方块，与 settings.js 的白名单保持一致 */
const FILL_LABELS = {
  'minecraft:stone': '石头',
  'minecraft:cobblestone': '圆石',
  'minecraft:deepslate': '深板岩',
  'minecraft:dirt': '泥土',
  'minecraft:sandstone': '砂岩',
  'minecraft:andesite': '安山岩',
  'minecraft:netherrack': '下界岩',
  'minecraft:snow_block': '雪块'
};

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

    // 强化地图画：用柱子高低差换额外色阶
    const mapArt = ref(false);
    const mapLayers = ref(8);
    // 明暗灵敏度：相邻像素亮度差超过它才升降一格，越大起伏越少
    const lumaThreshold = ref(4);
    // 0 表示不限制；其余为最多使用的方块种类
    const maxBlocks = ref(0);

    /* ---------------- 立体浮雕 ---------------- */
    const reliefMin = ref(1);
    const reliefMax = ref(24);
    const reliefShell = ref(1);
    const reliefHollow = ref(false);
    const reliefFill = ref(FILL_BLOCKS[0]);
    const reliefCurve = ref('linear');
    const reliefInvert = ref(false);
    const isBundling = ref(false);

    // 图片预处理
    const brightness = ref(0);
    const contrast = ref(0);
    const saturation = ref(100);
    const gamma = ref(1);
    const grayscale = ref(false);
    const invert = ref(false);

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
    // 字形拉伸与位移（%），加粗强度按像素描边
    const scaleX = ref(100);
    const scaleY = ref(100);
    const offsetX = ref(0);
    const offsetY = ref(0);
    const boldness = ref(0);
    const customFont = ref('');
    const customFontLabel = ref('');
    const isExportingChars = ref(false);

    const FONT_STACKS = {
      system: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", ui-sans-serif, system-ui, sans-serif',
      serif: '"Songti SC", "SimSun", "Noto Serif SC", serif',
      mono: '"JetBrains Mono", Consolas, "Courier New", monospace',
      heiti: '"Heiti SC", "Microsoft YaHei", "Noto Sans SC", sans-serif'
    };

    const fontStack = computed(() => {
      if (customFont.value) return `"${customFont.value}", ${FONT_STACKS.system}`;
      return FONT_STACKS[fontFamily.value] || FONT_STACKS.system;
    });

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
    const fontInput = ref(null);
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
    let persistTimer = null;
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

    const fillBlocks = computed(() =>
      FILL_BLOCKS.map((value) => ({ value, label: FILL_LABELS[value] || value.replace('minecraft:', '') }))
    );
    const sizePresets = SIZE_PRESETS;
    /** 一张地图 128×128，超过就要拼接，提前告诉用户要几张 */
    const mapCount = computed(() =>
      Math.max(1, Math.ceil(width.value / 128)) * Math.max(1, Math.ceil(height.value / 128))
    );
    const reliefVolume = computed(() =>
      (width.value * height.value * Math.max(1, reliefMax.value)).toLocaleString('en-US')
    );

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

    // 地图画依赖柱子沿南北向的高度差，只能平铺
    watch(mapArt, (on) => {
      if (on && plane.value !== 'xz') plane.value = 'xz';
    });

    // 立体是地形，只做平铺；切到别的模式时地图画开关不该跟着残留
    watch(mode, (value) => {
      if (value !== 'image' && mapArt.value) mapArt.value = false;
      if (value === 'relief' && plane.value !== 'xz') plane.value = 'xz';
    });

    watch([reliefMin, reliefMax], ([min, max]) => {
      if (max < min) reliefMax.value = min;
    });

    /* ---------------- 交互 ---------------- */
    function clampSize(value) {
      if (!Number.isFinite(value)) return 1;
      return Math.min(512, Math.max(1, value));
    }

    function triggerFileInput() {
      fileInput.value?.click();
    }

    function triggerFontInput() {
      fontInput.value?.click();
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

    function applySizePreset(size) {
      width.value = size;
      height.value = size;
    }

    function resetAdjustments() {
      brightness.value = 0;
      contrast.value = 0;
      saturation.value = 100;
      gamma.value = 1;
      grayscale.value = false;
      invert.value = false;
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

    /* ---------------- 设置记忆与分享 ---------------- */
    // 键名与 settings.js 的白名单一一对应；新增参数时两边一起加
    const settingRefs = {
      mode, format, width, height, lockAspect, plane, rotate, mirrorX, mirrorY,
      metric, dither, serpentine, alphaThreshold, smoothScale, maxBlocks,
      mapArt, mapLayers, lumaThreshold,
      brightness, contrast, saturation, gamma, grayscale, invert,
      reliefMin, reliefMax, reliefShell, reliefHollow, reliefFill, reliefCurve, reliefInvert,
      text, fontFamily, fontSize, bold, italic, align, lineHeight, letterSpacing,
      textColor, textTransparent, textThreshold, scaleX, scaleY, offsetX, offsetY, boldness,
      selectedBlocks
    };

    function collectSettings() {
      return pickSettings((key) => settingRefs[key]?.value);
    }

    /** 应用一组（已校验的）参数，并保证模式与摆放的约束成立 */
    function applySettings(settings) {
      for (const [key, value] of Object.entries(settings)) {
        const target = settingRefs[key];
        if (!target) continue;
        target.value = Array.isArray(value) ? [...value] : value;
      }
      if (mapArt.value || mode.value === 'relief') plane.value = 'xz';
      if (reliefMax.value < reliefMin.value) reliefMax.value = reliefMin.value;
    }

    function persistSettings() {
      if (persistTimer) clearTimeout(persistTimer);
      persistTimer = setTimeout(() => {
        persistTimer = null;
        writeStoredSettings(collectSettings());
      }, 400);
    }

    /** 从 #s= 或 ?s= 恢复分享的参数，恢复后把参数从地址栏抹掉，避免重复覆盖用户改动 */
    function restoreFromUrl() {
      const payload = window.location.hash.startsWith('#s=')
        ? window.location.hash.slice(3)
        : new URLSearchParams(window.location.search).get('s');
      if (!payload) return false;

      const settings = decodeSettings(payload);
      if (!settings) {
        notify('分享链接已损坏或版本不兼容，已忽略', 'error');
        return false;
      }
      applySettings(settings);

      const next = new URL(window.location.href);
      next.hash = '';
      next.searchParams.delete('s');
      window.history.replaceState(null, '', next.toString());
      return true;
    }

    function buildShareUrl() {
      const url = new URL(window.location.href);
      url.hash = `s=${encodeSettings(collectSettings())}`;
      return url.toString();
    }

    async function copyShareLink() {
      const link = buildShareUrl();
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(link);
        } else {
          throw new Error('clipboard unavailable');
        }
        notify('分享链接已复制', 'success');
      } catch {
        // 非安全上下文（http 局域网访问）没有剪贴板权限，退回 execCommand
        const area = document.createElement('textarea');
        area.value = link;
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand('copy');
        area.remove();
        notify(ok ? '分享链接已复制' : '复制失败，请手动复制地址栏链接', ok ? 'success' : 'error');
      }
    }

    /* ---------------- 素材 ---------------- */
    /** 统一做图像调节；参数全为默认值时原样返回，不产生额外开销 */
    function applyAdjustments(source) {
      return adjustPixels(source, {
        brightness: Number(brightness.value),
        contrast: Number(contrast.value),
        saturation: Number(saturation.value),
        gamma: Number(gamma.value),
        grayscale: grayscale.value,
        invert: invert.value
      });
    }

    /** 按当前设置取源像素：文字先渲染成位图，图片先缩放到目标尺寸 */
    function buildImageData() {
      let source;

      if (mode.value === 'text') {
        const rendered = renderTextToImageData(text.value, {
          width: width.value,
          height: height.value,
          fontFamily: fontStack.value,
          fontSize: fontSize.value,
          bold: bold.value,
          italic: italic.value,
          align: align.value,
          lineHeight: Number(lineHeight.value),
          letterSpacing: Number(letterSpacing.value),
          strokeWidth: Number(boldness.value),
          scaleX: Number(scaleX.value) / 100,
          scaleY: Number(scaleY.value) / 100,
          offsetX: Number(offsetX.value),
          offsetY: Number(offsetY.value),
          padding: 2
        });
        source = colorizeText(rendered, {
          threshold: Number(textThreshold.value),
          foreground: hexToRgb(textColor.value),
          background: textTransparent.value ? 'transparent' : [255, 255, 255]
        });
      } else {
        if (!imageElement) throw new Error('请先选择图片');
        source = getImagePixels(imageElement, width.value, height.value, { smooth: smoothScale.value });
      }

      // 文字模式的「图片调节」是隐藏的，参数不该偷偷作用到文字上
      return mode.value === 'text' ? source : applyAdjustments(source);
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
        const usingMapArt = mapArt.value && mode.value === 'image';
        const usingRelief = mode.value === 'relief';

        const imageData = buildImageData();
        if (token !== runToken) return;

        progress.value = 45;
        progressMessage.value = usingRelief ? '堆叠地形' : '匹配方块颜色';
        await nextTick();

        const next = processPixels(imageData, selectedBlocks.value, {
          metric: metric.value,
          dither: dither.value,
          serpentine: serpentine.value,
          alphaThreshold: Number(alphaThreshold.value),
          plane: plane.value,
          rotate: Number(rotate.value),
          mirrorX: mirrorX.value,
          mirrorY: mirrorY.value,
          mapArt: usingMapArt,
          mapLayers: Number(mapLayers.value),
          lumaThreshold: Number(lumaThreshold.value),
          maxBlocks: Number(maxBlocks.value),
          relief: usingRelief,
          reliefMin: Number(reliefMin.value),
          reliefMax: Number(reliefMax.value),
          reliefShell: Number(reliefShell.value),
          reliefHollow: reliefHollow.value,
          reliefFill: reliefFill.value,
          reliefCurve: reliefCurve.value,
          reliefInvert: reliefInvert.value
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
        const isWall = result.plane === 'xy';
        stats.value = {
          width: result.size.x,
          height: isWall ? result.size.y : result.size.z,
          layers: result.mapArt || result.relief ? result.size.y : 0,
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
        name: outputName()
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
    /**
     * 立体的等距视图：画出柱体侧面与顶面，起伏和朝向一眼可见。
     * 单纯的顶视图只能看到颜色，看不出「山有多高」。
     */
    function drawReliefPreview(current) {
      const canvas = previewCanvas.value;
      if (!canvas) return;

      const { size, volume, colors } = current;
      const TW = 4; // 一格宽 4px，2:1 等距
      const TH = 2;
      const span = size.x + size.z;

      canvas.width = span * (TW / 2) + TW;
      canvas.height = span * (TH / 2) + size.y * TH + TH * 2;
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const offsetX = size.z * (TW / 2) + TW / 2;
      const offsetY = size.y * TH + TH;

      const tops = new Int32Array(size.x * size.z);
      for (let z = 0; z < size.z; z++) {
        for (let x = 0; x < size.x; x++) {
          for (let y = size.y - 1; y >= 0; y--) {
            const index = volume[(y * size.z + z) * size.x + x];
            if (index !== 0) {
              tops[z * size.x + x] = (y + 1) * 4096 + index;
              break;
            }
          }
        }
      }

      const shade = (rgb, factor) =>
        `rgb(${Math.round(rgb[0] * factor)},${Math.round(rgb[1] * factor)},${Math.round(rgb[2] * factor)})`;

      // 由远及近：屏幕位置越靠下越近，后画的自然遮住前一根柱子
      for (let sum = 0; sum <= span - 2; sum++) {
        const from = Math.max(0, sum - (size.z - 1));
        const to = Math.min(size.x - 1, sum);
        for (let x = from; x <= to; x++) {
          const z = sum - x;
          const packed = tops[z * size.x + x];
          if (!packed) continue;

          const h = Math.floor(packed / 4096);
          const rgb = colors[packed % 4096];
          if (!rgb) continue;

          const cx = offsetX + (x - z) * (TW / 2);
          const cy = offsetY + (x + z) * (TH / 2) - h * TH;
          const bottom = cy + h * TH;
          const half = TW / 2;
          const halfH = TH / 2;

          // 左面偏亮、右面偏暗，模拟从左上打光
          ctx.fillStyle = shade(rgb, 0.82);
          ctx.beginPath();
          ctx.moveTo(cx - half, cy);
          ctx.lineTo(cx, cy + halfH);
          ctx.lineTo(cx, bottom + halfH);
          ctx.lineTo(cx - half, bottom);
          ctx.closePath();
          ctx.fill();

          ctx.fillStyle = shade(rgb, 0.62);
          ctx.beginPath();
          ctx.moveTo(cx, cy + halfH);
          ctx.lineTo(cx + half, cy);
          ctx.lineTo(cx + half, bottom);
          ctx.lineTo(cx, bottom + halfH);
          ctx.closePath();
          ctx.fill();

          // 顶面
          ctx.fillStyle = shade(rgb, 1);
          ctx.beginPath();
          ctx.moveTo(cx, cy - halfH);
          ctx.lineTo(cx + half, cy);
          ctx.lineTo(cx, cy + halfH);
          ctx.lineTo(cx - half, cy);
          ctx.closePath();
          ctx.fill();
        }
      }

      hasPreview.value = true;
      previewSize.value = `${size.x} × ${size.z} · 等距视图`;
      fitMedia(canvas, canvas.width, canvas.height);
    }

    function drawPreview(current) {
      const canvas = previewCanvas.value;
      if (!canvas) return;

      const { size, volume, colors, plane: planeMode } = current;
      const isWall = planeMode === 'xy';
      const w = size.x;
      const h = isWall ? size.y : size.z;

      if (current.relief) {
        drawReliefPreview(current);
        return;
      }

      canvas.width = w;
      canvas.height = h;

      const ctx = canvas.getContext('2d');

      // 地图画 / 立体自带「按明暗档位、按高度」上色的像素，直接贴上才看得出成品的样子
      if (current.previewPixels && current.previewPixels.width === w && current.previewPixels.height === h) {
        ctx.putImageData(new ImageData(new Uint8ClampedArray(current.previewPixels.data), w, h), 0, 0);
        hasPreview.value = true;
        previewSize.value = `${w} × ${h} · ${current.mapArt ? '地图配色' : '顶视图 · 按高度提亮'}`;
        fitMedia(canvas, w, h);
        return;
      }

      const image = ctx.createImageData(w, h);
      const pixels = image.data;

      for (let row = 0; row < h; row++) {
        for (let x = 0; x < w; x++) {
          let index = 0;
          if (isWall) {
            // 竖立：从正面看，第 0 行在最上方
            index = volume[((h - 1 - row) * size.z) * size.x + x];
          } else {
            // 平铺：从上方看，取这一列最高的非空气方块，立体地形的顶面才不会被空气盖住
            for (let y = size.y - 1; y >= 0; y--) {
              const value = volume[(y * size.z + row) * size.x + x];
              if (value !== 0) {
                index = value;
                break;
              }
            }
          }
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

    /** 载入自定义字体（TTF / OTF / WOFF），用于文字像素画 */
    async function handleFontFile(event) {
      const file = event.target.files?.[0];
      event.target.value = '';
      if (!file) return;
      if (!/\.(ttf|otf|woff2?)$/i.test(file.name)) {
        notify('请选择 TTF / OTF / WOFF 字体文件', 'error');
        return;
      }
      if (file.size > 12 * 1024 * 1024) {
        notify('字体文件过大，请控制在 12MB 以内', 'error');
        return;
      }
      try {
        const buffer = await file.arrayBuffer();
        const name = `SunPixelFont${Date.now()}`;
        const face = new FontFace(name, buffer);
        await face.load();
        document.fonts.add(face);
        customFont.value = name;
        customFontLabel.value = file.name.replace(/\.[^.]+$/, '');
        notify(`字体已载入：${customFontLabel.value}`, 'success');
        scheduleRun(0);
      } catch (error) {
        notify(`字体载入失败：${error.message}`, 'error');
      }
    }

    function resetFont() {
      customFont.value = '';
      customFontLabel.value = '';
      scheduleRun(0);
    }

    /**
     * 逐字导出：每个字符单独生成 128×128 的结构，打包成一个 zip
     * 思路来自 minecraft-block-letter 的字符投影，方便做字库或逐字搭建。
     */
    async function exportCharacters() {
      if (mode.value !== 'text' || isExportingChars.value) return;
      const chars = [...new Set(Array.from(String(text.value).replace(/[\r\n\t]/g, '')))]
        .filter((ch) => ch.trim().length > 0);
      if (!chars.length) {
        notify('没有可导出的字符', 'error');
        return;
      }
      if (chars.length > 200) {
        notify('字符太多，单次最多 200 个', 'error');
        return;
      }

      isExportingChars.value = true;
      try {
        const files = [];
        const usedNames = new Set();

        for (let i = 0; i < chars.length; i++) {
          const ch = chars[i];
          const rendered = renderTextToImageData(ch, {
            width: 128,
            height: 128,
            fontFamily: fontStack.value,
            fontSize: 96,
            bold: bold.value,
            italic: italic.value,
            align: 'center',
            lineHeight: 1.1,
            letterSpacing: 0,
            strokeWidth: Number(boldness.value),
            scaleX: Number(scaleX.value) / 100,
            scaleY: Number(scaleY.value) / 100,
            offsetX: Number(offsetX.value),
            offsetY: Number(offsetY.value),
            padding: 2
          });
          const pixels = colorizeText(rendered, {
            threshold: Number(textThreshold.value),
            foreground: hexToRgb(textColor.value),
            background: textTransparent.value ? 'transparent' : [255, 255, 255]
          });
          const single = processPixels(applyAdjustments(pixels), selectedBlocks.value, {
            metric: metric.value,
            dither: dither.value,
            serpentine: serpentine.value,
            alphaThreshold: Number(alphaThreshold.value),
            plane: 'xz',
            rotate: 0,
            mirrorX: false,
            mirrorY: false,
            maxBlocks: Number(maxBlocks.value)
          });
          const output = await generateOutput(single, format.value, 'char', { name: ch });

          let base = ch.replace(/[\\/:*?"<>|\s]/g, '_');
          if (!base) base = `U${ch.codePointAt(0).toString(16).toUpperCase()}`;
          if (usedNames.has(base)) base = `${base}_${i + 1}`;
          usedNames.add(base);

          files.push({
            name: `${base}.${FORMAT_EXTENSIONS[format.value]}`,
            data: new Uint8Array(await output.blob.arrayBuffer())
          });

          progress.value = Math.round(((i + 1) / chars.length) * 100);
          progressMessage.value = `逐字导出 ${i + 1}/${chars.length}`;
        }

        triggerDownload(createZip(files), `SunPixel_逐字_${chars.length}个.zip`);
        notify(`已导出 ${chars.length} 个字符`, 'success');
      } catch (error) {
        notify(`逐字导出失败：${error.message}`, 'error');
      } finally {
        isExportingChars.value = false;
        progress.value = 0;
        progressMessage.value = '';
      }
    }

    async function downloadExtra(kind) {
      if (!result) return;
      const names = { blueprint: '搭建图纸', csv: '材料清单' };
      try {
        const output = await generateOutput(result, kind, `sunpixel_${kind}`, { name: outputName() });
        triggerDownload(output.blob, output.filename);
      } catch (error) {
        notify(`${names[kind] || kind}导出失败：${error.message}`, 'error');
      }
    }

    function outputName() {
      if (mode.value === 'text') return `文字像素画 ${text.value.split('\n')[0].slice(0, 12)}`;
      return mode.value === 'relief' ? 'SunPixel 立体地形' : 'SunPixel 像素画';
    }

    /** 效果图放大成 PNG，打包时一起带上 */
    function previewPngBlob(scale = 4) {
      const source = previewCanvas.value;
      if (!source || !source.width || !source.height) return Promise.resolve(null);
      const canvas = document.createElement('canvas');
      canvas.width = source.width * scale;
      canvas.height = source.height * scale;
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
      return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), 'image/png'));
    }

    /**
     * 一键打包：全部结构格式 + 图纸 + 材料清单 + 效果图
     * 单个附加文件失败（例如方块太多、CSV 超限）只跳过它，不影响整体。
     */
    async function downloadBundle() {
      if (!result || isBundling.value) return;
      isBundling.value = true;
      const meta = { name: outputName() };
      const files = [];
      const skipped = [];

      try {
        const formats = ['schem', 'litematic', 'mcstructure', 'nbt', 'mcfunction', 'json'];
        for (let i = 0; i < formats.length; i++) {
          const format = formats[i];
          progressMessage.value = `打包 ${format}（${i + 1}/${formats.length}）`;
          progress.value = Math.round(((i + 1) / (formats.length + 3)) * 100);
          try {
            const output = await generateOutput(result, format, `sunpixel_${mode.value}`, meta);
            files.push({ name: output.filename, data: new Uint8Array(await output.blob.arrayBuffer()) });
          } catch (error) {
            // 例如方块太多超出结构方块文件上限，跳过它但不影响其他格式
            skipped.push(`${format}：${error.message}`);
          }
        }

        for (const extra of ['blueprint', 'csv']) {
          try {
            const output = await generateOutput(result, extra, `sunpixel_${extra}`, meta);
            files.push({ name: output.filename, data: new Uint8Array(await output.blob.arrayBuffer()) });
          } catch (error) {
            skipped.push(`${extra}：${error.message}`);
          }
        }

        const png = await previewPngBlob(4);
        if (png) {
          files.push({ name: '效果图.png', data: new Uint8Array(await png.arrayBuffer()) });
        }

        triggerDownload(createZip(files), `SunPixel_${mode.value}_${stats.value.width}x${stats.value.height}.zip`);
        notify(skipped.length ? `已打包 ${files.length} 个文件，跳过：${skipped.join('；')}` : `已打包 ${files.length} 个文件`, skipped.length ? 'info' : 'success');
      } catch (error) {
        notify(`打包失败：${error.message}`, 'error');
      } finally {
        isBundling.value = false;
        progress.value = 0;
        progressMessage.value = '';
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
      // 先恢复本机记住的参数，再让分享链接覆盖，最后才初始化方块与日志
      const stored = readStoredSettings();
      if (stored) applySettings(stored);
      if (restoreFromUrl()) notify('已载入分享的参数', 'success');

      loadAvailableBlocks();
      loadChangelog();
      window.addEventListener('resize', handleResize);
      if (hasSource.value) scheduleRun(0);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleResize);
      if (debounceTimer) clearTimeout(debounceTimer);
      if (persistTimer) clearTimeout(persistTimer);
      if (toastTimer) clearTimeout(toastTimer);
      writeStoredSettings(collectSettings());
    });

    /* ---------------- 参数变化自动重算 ---------------- */
    watch(
      [
        mode, width, height, plane, rotate, mirrorX, mirrorY, metric, dither, serpentine,
        alphaThreshold, smoothScale, selectedBlocks, text, fontFamily, fontSize, bold,
        italic, align, lineHeight, letterSpacing, textColor, textTransparent, textThreshold,
        mapArt, mapLayers, lumaThreshold, maxBlocks, brightness, contrast, saturation, gamma,
        grayscale, invert, scaleX, scaleY, offsetX, offsetY, boldness, customFont,
        reliefMin, reliefMax, reliefShell, reliefHollow, reliefFill, reliefCurve, reliefInvert
      ],
      () => {
        scheduleRun();
        persistSettings();
      },
      { deep: true }
    );

    watch(lockAspect, persistSettings);

    // 切换输出格式只重算文件，不必重跑像素流程
    watch(format, async () => {
      persistSettings();
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
      mapArt, mapLayers, lumaThreshold, maxBlocks,
      reliefMin, reliefMax, reliefShell, reliefHollow, reliefFill, reliefCurve, reliefInvert,
      fillBlocks, sizePresets, mapCount, reliefVolume, isBundling,
      brightness, contrast, saturation, gamma, grayscale, invert,
      allBlocks, selectedBlocks, displayBlocks,
      text, fontFamily, fontSize, bold, italic, align, lineHeight, letterSpacing,
      textColor, textTransparent, textThreshold,
      scaleX, scaleY, offsetX, offsetY, boldness, customFont, customFontLabel, isExportingChars,
      uploadedFileName, imageUrl, originalPreview, imageSize, hasImage,
      showPreview, showResult, showChangelog, hasPreview, previewSize,
      progress, progressMessage, errorMessage, isConverting, changelogs, fileInput,
      previewCanvas, originalImg, fontInput, stats, materials, canConvert, downloadFilename, toast, runCount,
      triggerFileInput, handleDrop, handleFileUpload, loadImageFromUrl,
      handleFontFile, resetFont, exportCharacters, triggerFontInput,
      toggleBlock, selectAll, clearAll, selectCommon, applySizePreset, resetAdjustments,
      startConversion, downloadFile, downloadExtra, downloadBundle, copyShareLink,
      formatChangelog, notify, FORMAT_EXTENSIONS
    };
  }
}).mount('#app');
