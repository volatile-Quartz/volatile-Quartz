// fetch_whatpulse.js
// 抓取 WhatPulse 用户页 HTML 中的统计数字，生成主页展示区块（与 Last.fm 同风格的表格）。
//
// 官网展示的字段（2026-10 实测）：
//   Keys / Clicks / Scrolls / Distance / Download / Upload / Uptime / Pulses
// 输出为「表头=字段、数据行=数值」的表格（字段在前，数据在后）。
// Pulses 指客户端把统计「上报」到官网的次数，中文记作「上报次数」（不译作「脉冲」）。
// 注意：Distance、Download、Upload、Uptime 带单位（1414.448km / 19.25TB / 5 years,...），
// 不能用「只匹配整数」的正则，否则会整条漏掉。

const fs = require('fs');

const USERNAME = process.env.WHATPULSE_USER || process.env.WHATPUSE_USER || 'volatileQuartz';
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
  if (num >= 1_000_000_000) return (num / 1_000_000_000).toFixed(1).replace(/\.0$/, '') + 'B';
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (num >= 1_000) return (num / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return num.toString();
}

// 抓取所有 title="%Xxx%" 后面的文本（含单位，不限于数字）
function extract(html) {
  const fields = {};
  const regex = /title="%([A-Za-z]+)%">([^<]*)<\/span>/g;
  let m;
  while ((m = regex.exec(html)) !== null) {
    fields[m[1]] = m[2].trim();
  }
  return fields;
}

const toInt = (v) => parseInt(String(v || '').replace(/,/g, ''), 10) || 0;

// "1414.448km" → "1,414km"（不换单位，只补千分位）
function formatDistance(raw) {
  if (!raw) return '';
  const m = String(raw).match(/^([\d.]+)\s*(.*)$/);
  if (!m) return raw;
  const num = Math.round(parseFloat(m[1]));
  return `${num.toLocaleString()}${m[2]}`;
}

// "5 years, 2 weeks, 5 hours, ..." → "5年2周"
function compactUptime(raw) {
  if (!raw) return '';
  const zh = {
    year: '年', years: '年', week: '周', weeks: '周', day: '天', days: '天',
    hour: '小时', hours: '小时', minute: '分', minutes: '分', second: '秒', seconds: '秒',
  };
  const parts = [...String(raw).matchAll(/(\d+)\s+([a-zA-Z]+)/g)]
    .map(m => `${m[1]}${zh[m[2].toLowerCase()] || m[2]}`);
  return parts.slice(0, 2).join('') || raw;
}

async function generateContent() {
  const html = await fetchPage();
  const f = extract(html);

  const keys = toInt(f.TotalKeyCount) || toInt(f.TotalKeys);
  const clicks = toInt(f.TotalMouseClicks) || toInt(f.TotalClicks);
  const scrolls = toInt(f.TotalScrolls);
  const pulses = toInt(f.Pulses);
  const distance = formatDistance(f.TotalMouseDistance);
  const download = f.TotalDownloaded || '';
  const upload = f.TotalUploaded || '';
  const uptime = compactUptime(f.TotalUptimeLong);

  if (!keys && !clicks) {
    throw new Error('WhatPulse 页面没有匹配到统计字段（页面结构可能已更新）');
  }

  // 与官网字段一一对应：表头=字段，数据行=数值（字段在前、数据在后）
  // Pulses = 客户端把统计上报到官网的次数 → 「上报次数」
  const v = (n) => (n > 0 ? compact(n) : '—');

  const stamp = new Date().toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai', hour12: false,
  });

  return `| ⌨️ 键盘 | 🖱️ 鼠标 | 🔄 滚动 | 🖲️ 移动距离 | ⬇️ 下载 | ⬆️ 上传 | ⏱️ 使用时长 | 📡 上报次数 |
|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|:-------:|
| ${v(keys)} | ${v(clicks)} | ${v(scrolls)} | ${distance || '—'} | ${download || '—'} | ${upload || '—'} | ${uptime || '—'} | ${v(pulses)} |

*更新于 ${stamp} · [进入 WhatPulse →](${URL})*`;
}

const startMarker = '<!-- WHATPULSE_START -->';
const endMarker = '<!-- WHATPULSE_END -->';

async function main() {
  const readmePath = process.env.README_PATH || './README.md';
  let readme = fs.readFileSync(readmePath, 'utf8');

  try {
    const content = await generateContent();
    if (!readme.includes(startMarker) || !readme.includes(endMarker)) {
      throw new Error(`README 中找不到 ${startMarker} / ${endMarker} 标记`);
    }
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