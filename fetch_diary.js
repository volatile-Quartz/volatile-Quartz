// fetch_diary.js
// 从 Dr_Wunderkammer 的 posts/index.json 读取周记目录，生成主页 README 的周记模块。
// 只展示最近 3 年（当年 + 前两年）的合集；更早的合并为一个"查看全部"链接。
// 本脚本只负责输出 <!-- DIARY_START --> 与 <!-- DIARY_END --> 之间的内容，
// 模块标题由 README 模板控制。

const fs = require('fs');

const INDEX_URL = 'https://raw.githubusercontent.com/volatile-Quartz/Dr_Wunderkammer/master/posts/index.json';
const PAGES_BASE = 'https://volatile-quartz.github.io/Dr_Wunderkammer/viewer.html?src=';
const REPO_URL = 'https://github.com/volatile-Quartz/Dr_Wunderkammer';

function currentYear() {
  return new Date().getFullYear();
}

async function fetchIndex() {
  const res = await fetch(INDEX_URL);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function generateDiaryContent() {
  const data = await fetchIndex();
  const entries = data.entries || [];

  // 只看 my-diary 目录下的条目
  const myDiary = entries.filter(e => e.path.startsWith('my-diary/'));

  // 按 label 分组
  const groups = {};
  for (const e of myDiary) {
    const label = e.label;
    if (!groups[label]) groups[label] = [];
    groups[label].push(e);
  }

  // 计算每个合集的统计
  const collections = Object.entries(groups).map(([label, items]) => {
    const dir = label.replace('my-diary/', '');
    const weeklyItems = items.filter(i =>
      i.path.endsWith('.md')
      && !i.path.endsWith('00_index.md')
      && !i.title.startsWith('附录')  // 附录单独归为 releases，不在周次列表里
    );
    const indexItem = items.find(i => i.path.endsWith('00_index.md'));
    const totalWords = weeklyItems.reduce((s, i) => s + (i.word_count || 0), 0);
    const yearMatch = dir.match(/(\d{4})/);
    const sortYear = yearMatch ? parseInt(yearMatch[1]) : 0;

    return {
      dir,
      title: indexItem ? indexItem.title : dir,
      weeklyCount: weeklyItems.length,
      totalWords,
      indexPath: indexItem ? indexItem.path : null,
      sortYear,
      weeklyItems: weeklyItems.sort((a, b) => a.path.localeCompare(b.path)),
    };
  });

  collections.sort((a, b) => b.sortYear - a.sortYear);

  // 分桶
  const year = currentYear();
  const recentCutoff = year - 2;
  const recent = collections.filter(c => c.sortYear >= recentCutoff && c.weeklyCount > 0);
  const older = collections.filter(c => c.sortYear < recentCutoff);

  // 每个合集：全部周条目倒序（最新在前），取最近 10 篇展开
  const recentBlocks = recent.map(coll => {
    const sortedDesc = [...coll.weeklyItems].reverse(); // 最新在前
    const showCount = Math.min(10, sortedDesc.length);
    const showItems = sortedDesc.slice(0, showCount);
    const hiddenCount = sortedDesc.length - showCount;

    const weeklyLinks = showItems.map(item => {
      let shortTitle = item.title;
      const m = item.title.match(/(第\d+周[^）]*?)）/);
      if (m) shortTitle = m[1] + '）';
      else shortTitle = item.title.length > 22 ? item.title.slice(0, 22) + '…' : item.title;
      return `- [${shortTitle}](${PAGES_BASE}${encodeURIComponent(item.path)}) · ${item.word_count}字`;
    }).join('\n');

    const collIndexUrl = coll.indexPath
      ? `${PAGES_BASE}${encodeURIComponent(coll.indexPath)}`
      : REPO_URL;

    const hiddenHint = hiddenCount > 0
      ? `\n- …（另有 ${hiddenCount} 篇，[查看合集全部 →](${collIndexUrl})）`
      : '';

    return `**${coll.title}** · 共 ${coll.weeklyCount} 篇 · ${coll.totalWords.toLocaleString()} 字

${weeklyLinks}${hiddenHint}

[📖 合集目录](${collIndexUrl})`;
  }).join('\n\n---\n\n');

  // 更早合集
  let olderLine = '';
  const olderWithContent = older.filter(c => c.weeklyCount > 0);
  if (olderWithContent.length > 0) {
    const summary = olderWithContent
      .map(c => `${c.title}（${c.weeklyCount}篇/${c.totalWords.toLocaleString()}字）`)
      .join('、');
    const olderTitles = older.map(c => c.title).join(' / ');
    olderLine = `\n\n<details>\n<summary>📚 更早的合集：${summary} — 点击展开</summary>\n\n- [${olderTitles} 完整目录](${REPO_URL})\n\n</details>\n`;
  }

  const totalWeeklies = collections.reduce((s, c) => s + c.weeklyCount, 0);
  const totalWords = collections.reduce((s, c) => s + c.totalWords, 0);
  const statsLine = `> 📊 共 ${collections.length} 个年份合集 · ${totalWeeklies} 篇 · ${totalWords.toLocaleString()} 字\n`;

  return `${statsLine}\n${recentBlocks}${olderLine}\n\n*最后更新: ${new Date().toLocaleString('zh-CN')} · 数据源: [posts/index.json](${INDEX_URL})*`;
}

const startMarker = '<!-- DIARY_START -->';
const endMarker = '<!-- DIARY_END -->';

async function main() {
  const readmePath = process.env.README_PATH || './README.md';
  let readme = fs.readFileSync(readmePath, 'utf8');

  try {
    const content = await generateDiaryContent();

    if (readme.includes(startMarker) && readme.includes(endMarker)) {
      readme = readme.replace(
        new RegExp(`${startMarker}[\\s\\S]*?${endMarker}`),
        `${startMarker}\n${content}\n${endMarker}`
      );
    } else {
      readme += `\n\n${startMarker}\n${content}\n${endMarker}`;
    }

    fs.writeFileSync(readmePath, readme);
    console.log('✅ 周记模块更新成功');
  } catch (err) {
    console.error('❌ fetch_diary.js 失败:', err.message);
  }
}

main();
