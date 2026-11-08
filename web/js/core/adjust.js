/**
 * 图片预处理：亮度、对比度、饱和度、伽马、灰度、反色
 *
 * 全部在取像素之后、颜色量化之前执行，因此对抖动、透明阈值、地图画都生效。
 */

function clampByte(value) {
  return value < 0 ? 0 : value > 255 ? 255 : Math.round(value);
}

/**
 * @param {{width:number,height:number,data:Uint8ClampedArray}} imageData
 * @param {object} options
 *   brightness -100..100，contrast -100..100，saturation 0..200（%），
 *   gamma 0.2..3，grayscale / invert 为布尔
 */
function adjustPixels(imageData, options = {}) {
  const brightness = Number(options.brightness || 0);
  const contrast = Number(options.contrast || 0);
  const saturation = Number(options.saturation === undefined ? 100 : options.saturation);
  const gamma = Math.max(0.2, Number(options.gamma === undefined ? 1 : options.gamma));
  const grayscale = !!options.grayscale;
  const invert = !!options.invert;

  const data = Uint8ClampedArray.from(imageData.data);

  if (
    brightness === 0 &&
    contrast === 0 &&
    saturation === 100 &&
    gamma === 1 &&
    !grayscale &&
    !invert
  ) {
    return { width: imageData.width, height: imageData.height, data };
  }

  // 对比度用常见的光栅公式，避免两端被硬截断
  const c = contrast * 2.55;
  const contrastFactor = (259 * (c + 255)) / (255 * (259 - c));
  const saturationFactor = saturation / 100;
  const gammaInverse = 1 / gamma;

  // 伽马查表，避免每像素做 Math.pow
  const lut = new Uint8ClampedArray(256);
  for (let i = 0; i < 256; i++) {
    lut[i] = clampByte(255 * Math.pow(i / 255, gammaInverse));
  }

  for (let i = 0; i < data.length; i += 4) {
    let r = data[i];
    let g = data[i + 1];
    let b = data[i + 2];

    if (brightness !== 0) {
      const delta = brightness * 2.55;
      r += delta;
      g += delta;
      b += delta;
    }

    if (contrast !== 0) {
      r = contrastFactor * (r - 128) + 128;
      g = contrastFactor * (g - 128) + 128;
      b = contrastFactor * (b - 128) + 128;
    }

    if (gamma !== 1) {
      r = lut[clampByte(r)];
      g = lut[clampByte(g)];
      b = lut[clampByte(b)];
    }

    if (saturation !== 100 || grayscale) {
      const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (grayscale) {
        r = luma;
        g = luma;
        b = luma;
      } else {
        r = luma + (r - luma) * saturationFactor;
        g = luma + (g - luma) * saturationFactor;
        b = luma + (b - luma) * saturationFactor;
      }
    }

    if (invert) {
      r = 255 - r;
      g = 255 - g;
      b = 255 - b;
    }

    data[i] = clampByte(r);
    data[i + 1] = clampByte(g);
    data[i + 2] = clampByte(b);
  }

  return { width: imageData.width, height: imageData.height, data };
}

export { adjustPixels };
