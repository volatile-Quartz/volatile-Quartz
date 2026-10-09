// fetch_releases.js
// 从 Dr_Wunderkammer 的 GitHub Releases 读取草稿存档统计，输出主页一行数字。

const fs = require('fs');

const REPO = 'volatile-Quartz/Dr_Wunderkammer';
const API_URL = `https://api.github.com/repos/${REPO}/releases?per_page=20`;

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

async function generateContent() {
  const releases = await fetchReleases();
  if (!releases || releases.length === 0) {
    return '_暂无_';
  }

  let totalAssets = 0;
  for (const r of releases) totalAssets += (r.assets || []).length;

  return `📦 **${releases.length}** 次存档 · 🗂️ **${totalAssets}** 个文件 — [查看 Releases →](https://github.com/${REPO}/releases)`;
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
