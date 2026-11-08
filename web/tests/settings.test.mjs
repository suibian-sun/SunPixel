import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_SETTINGS,
  sanitizeSettings,
  pickSettings,
  encodeSettings,
  decodeSettings,
  SETTINGS_SCHEMA
} from '../js/ui/settings.js';

test('设置：分享链接编解码可还原全部参数', () => {
  const source = sanitizeSettings({
    mode: 'relief',
    width: 96,
    height: 64,
    reliefMax: 33,
    reliefFill: 'minecraft:dirt',
    reliefHollow: true,
    text: 'Sun 像素',
    selectedBlocks: ['wool', 'concrete'],
    brightness: -20,
    gamma: 1.8
  });

  const encoded = encodeSettings(source);
  assert.match(encoded, /^[A-Za-z0-9_-]+$/, '链接参数应是 base64url，不含 + / =');

  const decoded = decodeSettings(encoded);
  assert.deepEqual(decoded, source);
  assert.equal(decoded.text, 'Sun 像素', '中文参数不应在编解码中损坏');
});

test('设置：非法值回落到默认值，不会被写进分享链接', () => {
  const cleaned = sanitizeSettings({
    width: 99999,
    height: 'abc',
    rotate: 45,
    mode: 'hologram',
    textColor: 'red',
    reliefFill: 'minecraft:bedrock',
    gamma: NaN,
    selectedBlocks: ['wool', 'not-a-block'],
    unknown: 'drop me'
  });

  assert.equal(cleaned.width, 512, '越界数值应夹到上限');
  assert.equal(cleaned.height, DEFAULT_SETTINGS.height);
  assert.equal(cleaned.rotate, 0);
  assert.equal(cleaned.mode, 'image');
  assert.equal(cleaned.textColor, DEFAULT_SETTINGS.textColor);
  assert.equal(cleaned.reliefFill, DEFAULT_SETTINGS.reliefFill);
  assert.equal(cleaned.gamma, DEFAULT_SETTINGS.gamma);
  assert.deepEqual(cleaned.selectedBlocks, ['wool']);
  assert.equal('unknown' in cleaned, false);
  assert.deepEqual(Object.keys(cleaned).sort(), Object.keys(SETTINGS_SCHEMA).sort());
});

test('设置：最低 / 最高高度的顺序会被修正', () => {
  const cleaned = sanitizeSettings({ reliefMin: 20, reliefMax: 4 });
  assert.equal(cleaned.reliefMax, 20);
});

test('设置：损坏或版本不符的链接返回 null', () => {
  assert.equal(decodeSettings(''), null);
  assert.equal(decodeSettings('这不是 base64'), null);
  assert.equal(decodeSettings('YWJj'), null, '非 JSON 内容应被拒绝');

  const oldVersion = Buffer.from(JSON.stringify({ v: 0, width: 64 })).toString('base64url');
  assert.equal(decodeSettings(oldVersion), null, '版本不匹配应拒绝，避免旧链接把参数改坏');

  assert.ok(decodeSettings(encodeSettings({ width: 64 })));
});

test('设置：pickSettings 只挑白名单字段', () => {
  const state = { width: 64, height: 32, mode: 'text', customFont: 'FontX', random: 1 };
  const picked = pickSettings((key) => state[key]);
  assert.equal(picked.width, 64);
  assert.equal(picked.mode, 'text');
  assert.equal('customFont' in picked, false);
  assert.equal('random' in picked, false);
});
