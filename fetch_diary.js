// fetch_diary.js
// 从 Dr_Wunderkammer 的 posts/index.json 读取周记统计，输出主页一行数字。

const fs = require('fs');

const INDEX_URL = 'https://raw.githubusercontent.com/volatile-Quartz/Dr_Wunderkammer/master/posts/index.json';
const REPO_URL = 'https://github.com/volatile-Quartz/Dr_Wunderkammer';

async function fetchIndex() {
  const res = await fetch(INDEX_URL);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function generateContent() {
  const data = await fetchIndex();
  const entries = data.entries || [];

  // 只统计 my-diary 下的周次条目（排除 index.md 和 附录）
  const weeklies = entries.filter(e =>
    e.path.startsWith('my-diary/')
    && e.path.endsWith('.md')
    && !e.path.endsWith('00_index.md')
    && !e.title.startsWith('附录')
  );

  // 只统计 Diary- 开头的年份合集 label，排除 the-lore 等其他目录
  const labels = new Set(weeklies.map(e => e.label).filter(l => l.includes('Diary-')));
  const totalWords = weeklies.reduce((s, i) => s + (i.word_count || 0), 0);

  return `📚 **${labels.size}** 个年份合集 · 📝 **${weeklies.length}** 篇 · ✍️ **${totalWords.toLocaleString()}** 字 — [进入仓库 →](${REPO_URL})`;
}

const startMarker = '<!-- DIARY_START -->';
const endMarker = '<!-- DIARY_END -->';

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
    console.log('✅ 周记模块更新成功');
  } catch (err) {
    console.error('❌ fetch_diary.js 失败:', err.message);
  }
}

main();
