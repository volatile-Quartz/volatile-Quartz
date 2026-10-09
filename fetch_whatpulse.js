// fetch_whatpulse.js
// 抓取 WhatPulse 用户页 HTML 中的统计数字，生成主页一行展示。

const fs = require('fs');

const USERNAME = process.env.WHATPUSE_USER || 'volatileQuartz';
const URL = `https://whatpulse.org/u/${USERNAME}`;

async function fetchPage() {
  const res = await fetch(URL, {
    headers: { 'User-Agent': 'homepage-readme-builder' }
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

// 把 1,234,567 格式化成 1.2M / 34.5K 这样更紧凑的展示
function compact(num) {
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (num >= 1_000) return (num / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return num.toString();
}

function extract(html) {
  const fields = {};
  // 匹配 title="%FieldName%" 后面跟着的数字（带千分逗号）
  const regex = /title="%([A-Za-z]+)%">\s*([\d,]+)\s*<\/span>/g;
  let m;
  while ((m = regex.exec(html)) !== null) {
    fields[m[1]] = parseInt(m[2].replace(/,/g, ''), 10);
  }
  return fields;
}

async function generateContent() {
  const html = await fetchPage();
  const f = extract(html);

  const keys = f.TotalKeyCount || 0;
  const clicks = f.TotalMouseClicks || 0;
  const scrolls = f.TotalScrolls || 0;
  const pulses = f.Pulses || 0;

  if (!keys && !clicks) {
    throw new Error('WhatPulse 页面没有匹配到统计字段（页面结构可能已更新）');
  }

  const parts = [];
  if (keys) parts.push(`⌨️ **${compact(keys)}** 键`);
  if (clicks) parts.push(`🖱️ **${compact(clicks)}** 点击`);
  if (scrolls) parts.push(`🔄 **${compact(scrolls)}** 滚动`);
  if (pulses) parts.push(`💓 **${compact(pulses)}** 周期`);

  return `${parts.join(' · ')} — [详情 →](${URL})`;
}

const startMarker = '<!-- WHATPUSE_START -->';
const endMarker = '<!-- WHATPUSE_END -->';

async function main() {
  const readmePath = process.env.README_PATH || './README.md';
  let readme = fs.readFileSync(readmePath, 'utf8');

  try {
    const content = await generateContent();
    readme = readme.replace(
      new RegExp(`${startMarker}[\\s\\S]*?${endMarker}`),
      `${startMarker}\n${content}\n${endMarker}`
    );
    fs.writeFileSync(readmePath, readme);
    console.log('✅ WhatPulse 模块更新成功');
  } catch (err) {
    console.error('❌ fetch_whatpulse.js 失败:', err.message);
  }
}

main();
