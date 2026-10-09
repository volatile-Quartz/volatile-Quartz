// fetch_issues.js
// 读取本仓库（profile 仓库）里的「记录类」issue，生成主页入口行。
//
// 这些 issue 用来持续记录看过的动漫/电影、唱过的歌等；
// 正文或评论里按列表填写后，这里会自动统计条数。

const fs = require('fs');

const REPO = 'volatile-Quartz/volatile-Quartz';

// 想在主页展示的记录条目（issue 编号）
const ENTRIES = [
  { no: 4, icon: '🎬', name: '动漫' },
  { no: 3, icon: '🎥', name: '电影' },
  { no: 5, icon: '🎤', name: '唱歌' },
];

async function fetchIssue(no) {
  const headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'homepage-readme-builder',
  };
  const token = process.env.GITHUB_TOKEN;
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`https://api.github.com/repos/${REPO}/issues/${no}`, { headers });
  if (!res.ok) throw new Error(`issue #${no} HTTP ${res.status}`);
  return res.json();
}

// 统计正文里的列表条目（- xxx / * xxx / 1. xxx）
function countItems(body) {
  if (!body) return 0;
  return body
    .split('\n')
    .filter(line => /^\s*(?:[-*+]\s+|\d+[.、)]\s+)/.test(line))
    .length;
}

async function generateContent() {
  const issues = await Promise.all(ENTRIES.map(e => fetchIssue(e.no)));

  const parts = ENTRIES.map((entry, i) => {
    const issue = issues[i];
    const count = countItems(issue.body);
    const suffix = count > 0 ? `（${count}）` : '';
    return `${entry.icon} [${entry.name}](${issue.html_url})${suffix}`;
  });

  return parts.join(' · ');
}

const startMarker = '<!-- STATS_START -->';
const endMarker = '<!-- STATS_END -->';

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
    console.log('✅ 记录条目模块更新成功');
  } catch (err) {
    console.error('❌ fetch_issues.js 失败:', err.message);
  }
}

main();