/**
 * 参数记忆与分享链接
 *
 * 两个需求共用一份「白名单 + 校验」：
 *  - 记住上次设置：写进 localStorage，下次打开自动恢复
 *  - 分享链接：把参数压成 base64url 放进 #s=，对方打开即复现同一份作品
 *
 * 所有函数都是纯函数（localStorage 相关除外），方便在 Node 里单测。
 */

import { BLOCK_NAMES } from '../block-data.js';

const STORAGE_KEY = 'sunpixel:settings:v1';
const SHARE_VERSION = 1;

/** 填充方块：做立体地形的柱身，和表层配色分开 */
const FILL_BLOCKS = [
  'minecraft:stone',
  'minecraft:cobblestone',
  'minecraft:deepslate',
  'minecraft:dirt',
  'minecraft:sandstone',
  'minecraft:andesite',
  'minecraft:netherrack',
  'minecraft:snow_block'
];

const blockSet = new Set(BLOCK_NAMES);

const enumRule = (values, fallback) => ({ type: 'enum', values, default: fallback });
const intRule = (min, max, fallback) => ({ type: 'int', min, max, default: fallback });
const floatRule = (min, max, fallback) => ({ type: 'float', min, max, default: fallback });
const boolRule = (fallback) => ({ type: 'bool', default: fallback });

/** 会被记住 / 分享的参数白名单；不在表里的字段一律忽略 */
const SETTINGS_SCHEMA = {
  mode: enumRule(['image', 'text', 'relief'], 'image'),
  format: enumRule(['schem', 'litematic', 'mcstructure', 'nbt', 'mcfunction', 'json'], 'schem'),
  width: intRule(1, 512, 128),
  height: intRule(1, 512, 128),
  lockAspect: boolRule(true),
  plane: enumRule(['xz', 'xy'], 'xz'),
  rotate: enumRule([0, 90, 180, 270], 0),
  mirrorX: boolRule(false),
  mirrorY: boolRule(false),

  metric: enumRule(['lab', 'rgb'], 'lab'),
  dither: enumRule(['none', 'floyd'], 'none'),
  serpentine: boolRule(true),
  alphaThreshold: intRule(1, 254, 128),
  smoothScale: boolRule(true),
  maxBlocks: enumRule([0, 8, 12, 16, 24], 0),

  mapArt: boolRule(false),
  mapLayers: enumRule([4, 8, 16], 8),
  lumaThreshold: intRule(0, 32, 4),

  brightness: intRule(-100, 100, 0),
  contrast: intRule(-100, 100, 0),
  saturation: intRule(0, 200, 100),
  gamma: floatRule(0.2, 2.5, 1),
  grayscale: boolRule(false),
  invert: boolRule(false),

  reliefMin: intRule(1, 64, 1),
  reliefMax: intRule(1, 128, 24),
  reliefShell: intRule(1, 8, 1),
  reliefHollow: boolRule(false),
  reliefFill: enumRule(FILL_BLOCKS, 'minecraft:stone'),
  reliefCurve: enumRule(['linear', 'sqrt', 'square'], 'linear'),
  reliefInvert: boolRule(false),

  text: { type: 'string', maxLength: 200, default: 'SunPixel' },
  fontFamily: enumRule(['system', 'heiti', 'serif', 'mono'], 'system'),
  fontSize: intRule(8, 512, 96),
  bold: boolRule(true),
  italic: boolRule(false),
  align: enumRule(['center', 'left', 'right'], 'center'),
  lineHeight: floatRule(0.6, 3, 1.1),
  letterSpacing: intRule(-20, 40, 0),
  textColor: { type: 'color', default: '#111111' },
  textTransparent: boolRule(true),
  textThreshold: intRule(1, 254, 110),
  scaleX: intRule(50, 150, 100),
  scaleY: intRule(50, 150, 100),
  offsetX: intRule(-32, 32, 0),
  offsetY: intRule(-32, 32, 0),
  boldness: floatRule(0, 8, 0),

  selectedBlocks: { type: 'blocks', default: ['wool', 'concrete'] }
};

const DEFAULT_SETTINGS = Object.freeze(
  Object.fromEntries(
    Object.entries(SETTINGS_SCHEMA).map(([key, rule]) => [
      key,
      Array.isArray(rule.default) ? [...rule.default] : rule.default
    ])
  )
);

function clampNumber(value, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.min(max, Math.max(min, number));
}

/** 把任意输入收敛成可信的参数对象；非法字段回落到默认值 */
function sanitizeSettings(input) {
  const source = input && typeof input === 'object' ? input : {};
  const output = {};

  for (const [key, rule] of Object.entries(SETTINGS_SCHEMA)) {
    const value = source[key];

    switch (rule.type) {
      case 'enum': {
        output[key] = rule.values.includes(value) ? value : rule.default;
        break;
      }
      case 'int': {
        const number = clampNumber(value, rule.min, rule.max);
        output[key] = number === null ? rule.default : Math.round(number);
        break;
      }
      case 'float': {
        const number = clampNumber(value, rule.min, rule.max);
        output[key] = number === null ? rule.default : Math.round(number * 100) / 100;
        break;
      }
      case 'bool': {
        output[key] = typeof value === 'boolean' ? value : rule.default;
        break;
      }
      case 'color': {
        output[key] = /^#[0-9a-f]{6}$/i.test(String(value)) ? String(value).toLowerCase() : rule.default;
        break;
      }
      case 'string': {
        const text = typeof value === 'string' ? value.slice(0, rule.maxLength) : rule.default;
        output[key] = text;
        break;
      }
      case 'blocks': {
        const list = Array.isArray(value)
          ? [...new Set(value.filter((item) => typeof item === 'string' && blockSet.has(item)))]
          : [];
        output[key] = list.length ? list : [...rule.default];
        break;
      }
      default: {
        output[key] = rule.default;
      }
    }
  }

  // 最高高度不能低于最低高度，否则立体模式会算出负的柱高
  if (output.reliefMax < output.reliefMin) output.reliefMax = output.reliefMin;
  return output;
}

/** 从一组 ref / 普通值里挑出白名单参数 */
function pickSettings(get) {
  const raw = {};
  for (const key of Object.keys(SETTINGS_SCHEMA)) {
    const value = typeof get === 'function' ? get(key) : get?.[key];
    if (value !== undefined) raw[key] = value;
  }
  return raw;
}

function bytesToBase64Url(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64UrlToBytes(text) {
  const normalized = String(text).replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** 参数 → 可直接塞进 URL 的短字符串 */
function encodeSettings(settings) {
  const payload = { v: SHARE_VERSION, ...sanitizeSettings(settings) };
  return bytesToBase64Url(new TextEncoder().encode(JSON.stringify(payload)));
}

/** URL 字符串 → 参数对象；损坏或版本不符时返回 null */
function decodeSettings(text) {
  if (!text) return null;
  try {
    const json = new TextDecoder().decode(base64UrlToBytes(text));
    const data = JSON.parse(json);
    if (!data || typeof data !== 'object' || data.v !== SHARE_VERSION) return null;
    return sanitizeSettings(data);
  } catch {
    return null;
  }
}

function readStoredSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return sanitizeSettings(JSON.parse(raw));
  } catch {
    return null;
  }
}

function writeStoredSettings(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sanitizeSettings(settings)));
    return true;
  } catch {
    // 隐私模式 / 配额满时静默失败，不影响主流程
    return false;
  }
}

function clearStoredSettings() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 同上
  }
}

export {
  SETTINGS_SCHEMA,
  DEFAULT_SETTINGS,
  FILL_BLOCKS,
  STORAGE_KEY,
  SHARE_VERSION,
  sanitizeSettings,
  pickSettings,
  encodeSettings,
  decodeSettings,
  readStoredSettings,
  writeStoredSettings,
  clearStoredSettings
};
