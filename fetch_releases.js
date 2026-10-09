// fetch_releases.js
// 从 calculations 仓库的 GitHub Releases 读取草稿存档统计，输出主页一行数字。

const fs = require('fs');

const REPO = 'volatile-Quartz/calculations';
const API_URL = `https://api.github.com/repos/${REPO}/releases?per_page=20`;
const INDEX_URL = 'https://raw.githubusercontent.com/volatile-Quartz/calculations/main/index.json';

async function fetchReleases() {
  const headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'homepage-readme-builder'
  };
  // 可选：CI 中 GitHub 自动注入 GITHUB_TOKEN，本地可手动 export
  const token = process.env.GITHUB_TOKEN;
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(API_URL, { headers });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// index.json 里有编号区间/张数汇总；取不到就退化为只报压缩包个数
async function fetchIndexSummary() {
  try {
    const res = await fetch(INDEX_URL);
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.range_min || !data.range_max) return null;
    return {
      min: data.range_min,
      max: data.range_max,
      count: data.total_count || null,
    };
  } catch {
    return null;
  }
}

async function generateContent() {
  const releases = await fetchReleases();
  if (!releases || releases.length === 0) {
    return `🗂️ 整理中 — [草稿纸查看器 →](https://volatile-quartz.github.io/calculations/)`;
  }

  let totalAssets = 0;
  for (const r of releases) totalAssets += (r.assets || []).length;

  const summary = await fetchIndexSummary();
  const detail = summary
    ? ` · 🖼️ 覆盖 No.${summary.min}–${summary.max}${summary.count ? `（${summary.count} 张）` : ''}`
    : '';

  return `📦 **${releases.length}** 次存档 · 🗂️ **${totalAssets}** 个压缩包${detail} — [在线查看 →](https://volatile-quartz.github.io/calculations/)`;
}

const startMarker = '<!-- RELEASES_START -->';
const endMarker = '<!-- RELEASES_END -->';

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
    console.log('✅ 草稿存档模块更新成功');
  } catch (err) {
    console.error('❌ fetch_releases.js 失败:', err.message);
  }
}

main();
