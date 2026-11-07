import { generateSchem } from './format/schem.js';
import { generateLitematic } from './format/litematic.js';
import { generateMcstructure } from './format/mcstructure.js';
import { generateMcfunction } from './format/mcfunction.js';
import { generateRunaway } from './format/runaway.js';
import { generateBlueprint, generateMaterialCsv } from './format/blueprint.js';

const FORMAT_EXTENSIONS = {
  schem: 'schem',
  litematic: 'litematic',
  mcstructure: 'mcstructure',
  mcfunction: 'mcfunction',
  json: 'json',
  blueprint: 'md',
  csv: 'csv'
};

const FORMAT_LABELS = {
  schem: 'Sponge 结构文件',
  litematic: 'Litematica 投影',
  mcstructure: '基岩版结构',
  mcfunction: '命令函数',
  json: 'RunAway JSON',
  blueprint: '手动搭建图纸',
  csv: '材料清单 CSV'
};

/**
 * 生成输出文件
 * @param {object} result processPixels 的返回值
 * @param {string} format 见 FORMAT_EXTENSIONS
 * @param {string} filename 不含扩展名的文件名
 * @param {object} meta 名称、作者等元信息
 * @returns {Promise<{blob: Blob, filename: string, info: object}>}
 */
async function generateOutput(result, format, filename, meta = {}) {
  let output;

  switch (format) {
    case 'schem':
      output = { blob: await generateSchem(result, meta) };
      break;
    case 'litematic':
      output = { blob: await generateLitematic(result, meta) };
      break;
    case 'mcstructure':
      output = { blob: await generateMcstructure(result, meta) };
      break;
    case 'mcfunction':
      output = generateMcfunction(result, meta);
      break;
    case 'blueprint':
      output = generateBlueprint(result, meta);
      break;
    case 'csv':
      output = generateMaterialCsv(result);
      break;
    case 'json':
    default:
      output = generateRunaway(result, meta);
      break;
  }

  const ext = FORMAT_EXTENSIONS[format] || 'json';
  const base = filename || `sunpixel_${Date.now()}`;
  return {
    blob: output.blob,
    filename: `${base}.${ext}`,
    info: output.info || {}
  };
}

export { generateOutput, FORMAT_EXTENSIONS, FORMAT_LABELS };
