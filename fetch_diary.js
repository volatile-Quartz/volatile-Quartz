// fetch_diary.js
// 从 Dr_Wunderkammer 的 posts/index.json 读取周记统计，输出主页统计行 + 最新 3 篇。

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

  // 最新 3 篇：按（合集末位年份, 文件序号）排序。
  // index.json 按目录字母序排列（Diary-2019 在尾部），不能直接取数组尾部。
  // word_count < 50 视为占位文件（如刚建的空周记），不展示。
  const dated = weeklies
    .filter(e => e.word_count >= 50)
    .map(e => {
      const y = e.path.match(/Diary-(\d{4})(?:-(\d{4}))?\//);
      const n = e.path.match(/\/(\d+)_/);
      if (!y || !n) return null;
      return { ...e, sortKey: [parseInt(y[2] || y[1], 10), parseInt(n[1], 10)] };
    })
    .filter(Boolean)
    .sort((a, b) => b.sortKey[0] - a.sortKey[0] || b.sortKey[1] - a.sortKey[1]);

  const recent = dated.slice(0, 3)
    .map(e => `- [${e.title}](${REPO_URL}/blob/master/${e.path})`)
    .join('\n');

  return `📚 **${labels.size}** 个年份合集 · 📝 **${weeklies.length}** 篇 · ✍️ **${totalWords.toLocaleString()}** 字

📅 最近更新：

${recent}

→ [进入 Dr_Wunderkammer →](${REPO_URL})`;
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
