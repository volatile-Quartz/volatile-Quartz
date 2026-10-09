// fetch_releases.js
// 从 Dr_Wunderkammer 的 GitHub Releases 读取草稿项目，生成草稿存档模块。
// 本脚本只负责输出 <!-- RELEASES_START --> 与 <!-- RELEASES_END --> 之间的内容。

const fs = require('fs');

const REPO = 'volatile-Quartz/Dr_Wunderkammer';
const API_URL = `https://api.github.com/repos/${REPO}/releases?per_page=20`;

async function fetchReleases() {
  const res = await fetch(API_URL, {
    headers: { 'Accept': 'application/vnd.github+json' }
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function generateContent(releases) {
  if (!releases || releases.length === 0) {
    return '_暂无草稿存档_';
  }

  const lines = releases.map(r => {
    const tag = r.tag_name;
    const name = r.name || tag;
    const url = r.html_url;
    const assetCount = (r.assets || []).length;
    const bodyFirstLine = (r.body || '').split('\n')[0].trim();
    const assetHint = assetCount > 0 ? `（${assetCount} 个文件）` : '';
    const bodyHint = bodyFirstLine && bodyFirstLine !== name ? `\n  > ${bodyFirstLine}` : '';
    return `- 📦 [${name}](${url})${assetHint}${bodyHint}`;
  });

  return `${lines.join('\n')}\n\n🔗 [查看全部 Releases](https://github.com/${REPO}/releases)`;
}

const startMarker = '<!-- RELEASES_START -->';
const endMarker = '<!-- RELEASES_END -->';

async function main() {
  const readmePath = process.env.README_PATH || './README.md';
  let readme = fs.readFileSync(readmePath, 'utf8');

  try {
    const releases = await fetchReleases();
    const content = generateContent(releases);

    if (readme.includes(startMarker) && readme.includes(endMarker)) {
      readme = readme.replace(
        new RegExp(`${startMarker}[\\s\\S]*?${endMarker}`),
        `${startMarker}\n${content}\n${endMarker}`
      );
    } else {
      readme += `\n\n${startMarker}\n${content}\n${endMarker}`;
    }

    fs.writeFileSync(readmePath, readme);
    console.log('✅ 草稿存档模块更新成功');
  } catch (err) {
    console.error('❌ fetch_releases.js 失败:', err.message);
  }
}

main();
