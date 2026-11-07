/**
 * 文字像素画：把文字渲染成目标分辨率的位图，交给像素画流水线
 *
 * 思路来自 minecraft-block-letter（字符 → 128×128 单色画布 → 阈值二值化），
 * 这里扩展为：多行、对齐、字距、行高、自动缩放与可选描边，
 * 并且输出的是 RGBA 像素，因此可以直接复用现有的抖动 / 透明 / 导出流程。
 */

const DEFAULT_FONT_STACK = '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Source Han Sans SC", ui-sans-serif, system-ui, sans-serif';

function splitLines(text) {
  return String(text ?? '').replace(/\r\n?/g, '\n').split('\n');
}

function defaultCanvasFactory(width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

/**
 * 渲染文字到 ImageData
 * @param {string} text
 * @param {object} options
 * @returns {{width:number,height:number,data:Uint8ClampedArray}}
 */
function renderTextToImageData(text, options = {}) {
  const width = Math.max(1, Math.round(options.width || 128));
  const height = Math.max(1, Math.round(options.height || 128));
  const createCanvas = options.createCanvas || defaultCanvasFactory;
  const fontFamily = options.fontFamily || DEFAULT_FONT_STACK;
  const bold = !!options.bold;
  const italic = !!options.italic;
  const align = options.align || 'center';
  const lineHeight = options.lineHeight || 1.1;
  const letterSpacing = Number(options.letterSpacing || 0);
  const padding = Number(options.padding || 0);
  const strokeWidth = Number(options.strokeWidth || 0);
  const autoFit = options.autoFit !== false;

  const canvas = createCanvas(width, height);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.clearRect(0, 0, width, height);

  const lines = splitLines(text);
  const usableWidth = Math.max(1, width - padding * 2);
  const usableHeight = Math.max(1, height - padding * 2);

  let fontSize = Math.max(1, Math.round(options.fontSize || height));
  const weight = bold ? 700 : 400;
  const style = italic ? 'italic ' : '';

  const applyFont = (size) => {
    ctx.font = `${style}${weight} ${size}px ${fontFamily}`;
  };

  const measure = (line) => {
    const metrics = ctx.measureText(line);
    const spacing = Math.max(0, line.length - 1) * letterSpacing;
    return { width: metrics.width + spacing, ascent: metrics.actualBoundingBoxAscent, descent: metrics.actualBoundingBoxDescent };
  };

  // 自动缩放：让最长的一行刚好放进画布
  if (autoFit) {
    applyFont(fontSize);
    let widest = 0;
    for (const line of lines) widest = Math.max(widest, measure(line).width);
    const lineCount = Math.max(1, lines.length);
    const heightLimit = (usableHeight - (lineCount - 1) * 0) / (lineCount * lineHeight);
    const scaleW = widest > 0 ? usableWidth / widest : 1;
    const scaleH = heightLimit / fontSize;
    fontSize = Math.max(1, Math.floor(fontSize * Math.min(1, scaleW, scaleH)));
    applyFont(fontSize);
  }

  // 逐行绘制，垂直居中
  const totalHeight = lines.length * fontSize * lineHeight;
  let baseline = (height - totalHeight) / 2 + fontSize * (lineHeight - 1) / 2 + fontSize * 0.8;

  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#000000';
  ctx.strokeStyle = '#000000';
  ctx.lineJoin = 'round';

  for (const line of lines) {
    let x;
    if (align === 'left') x = padding;
    else if (align === 'right') x = width - padding;
    else x = width / 2;
    ctx.textAlign = align === 'left' ? 'left' : align === 'right' ? 'right' : 'center';

    if (letterSpacing > 0) {
      // 手动逐字绘制以实现字距
      const widths = [...line].map((ch) => ctx.measureText(ch).width);
      const lineWidth = widths.reduce((a, b) => a + b, 0) + Math.max(0, line.length - 1) * letterSpacing;
      let cursor = ctx.textAlign === 'center' ? x - lineWidth / 2 : ctx.textAlign === 'right' ? x - lineWidth : x;
      ctx.textAlign = 'left';
      [...line].forEach((ch, i) => {
        if (strokeWidth > 0) {
          ctx.lineWidth = strokeWidth * 2;
          ctx.strokeText(ch, cursor, baseline);
        }
        ctx.fillText(ch, cursor, baseline);
        cursor += widths[i] + letterSpacing;
      });
    } else {
      if (strokeWidth > 0) {
        ctx.lineWidth = strokeWidth * 2;
        ctx.strokeText(line, x, baseline);
      }
      ctx.fillText(line, x, baseline);
    }

    baseline += fontSize * lineHeight;
  }

  const imageData = ctx.getImageData(0, 0, width, height);
  return { width, height, data: imageData.data };
}

/**
 * 把文字的 alpha 通道二值化并上色，得到可供像素画流程使用的 RGBA
 * @param {{width:number,height:number,data:Uint8ClampedArray}} source
 * @param {object} options { threshold, foreground:[r,g,b], background:'transparent'|[r,g,b] }
 */
function colorizeText(source, options = {}) {
  const threshold = options.threshold === undefined ? 110 : options.threshold;
  const foreground = options.foreground || [0, 0, 0];
  const background = options.background === undefined ? 'transparent' : options.background;
  const out = new Uint8ClampedArray(source.data.length);

  for (let i = 0; i < source.data.length; i += 4) {
    const alpha = source.data[i + 3];
    if (alpha >= threshold) {
      out[i] = foreground[0];
      out[i + 1] = foreground[1];
      out[i + 2] = foreground[2];
      out[i + 3] = 255;
    } else if (background === 'transparent') {
      out[i] = 0;
      out[i + 1] = 0;
      out[i + 2] = 0;
      out[i + 3] = 0;
    } else {
      out[i] = background[0];
      out[i + 1] = background[1];
      out[i + 2] = background[2];
      out[i + 3] = 255;
    }
  }

  return { width: source.width, height: source.height, data: out };
}

export { renderTextToImageData, colorizeText, splitLines, DEFAULT_FONT_STACK };
