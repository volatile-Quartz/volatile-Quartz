// fetch_issues.js
// 读取本仓库（profile 仓库）里的「记录类」issue，生成主页入口行。
//
// 这些 issue 用来持续记录看过的动漫/电影、唱过的歌等；
// 记录通常写在评论里，格式为 Markdown 表格（类型/原名/译名/…）或列表，
// 一条评论可含多张表（如按年份分段），这里自动统计条目数。

const fs = require('fs');

const REPO = 'volatile-Quartz/volatile-Quartz';
const API = `https://api.github.com/repos/${REPO}`;

// 想在主页展示的记录条目（issue 编号）
const ENTRIES = [
  { no: 4, icon: '🎬', name: '动漫' },
  { no: 3, icon: '🎥', name: '电影' },
  { no: 5, icon: '🎤', name: '唱歌' },
];

function headers() {
  const h = { 'Accept': 'application/vnd.github+json', 'User-Agent': 'homepage-readme-builder' };
  const token = process.env.GITHUB_TOKEN;
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

async function gh(url) {
  const res = await fetch(url, { headers: headers() });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`);
  return res.json();
}

// issue 的全部评论（分页取全）
async function fetchComments(no) {
  const out = [];
  for (let page = 1; ; page++) {
    const data = await gh(`${API}/issues/${no}/comments?per_page=100&page=${page}`);
    out.push(...data);
    if (data.length < 100) break;
  }
  return out;
}

// 统计记录条目：Markdown 表格数据行 + 列表项（- / * / 1. / 1、）
function countItems(text) {
  if (!text) return 0;
  let count = 0;
  let inTable = false;

  for (const raw of text.split('\n')) {
    const t = raw.trim();
    if (!t) { inTable = false; continue; }

    // 表格分隔行（|--|--| 或 -- | -- | --）→ 进入表格模式，表头行不计
    const isSep = t.includes('|') && t.includes('-') && /^[\s:|-]+$/.test(t);
    if (isSep) { inTable = true; continue; }

    if (inTable) {
      if (t.includes('|')) { count++; continue; }  // 表格数据行
      inTable = false;                             // 表格结束
    }

    if (/^[-*+]\s+/.test(t) || /^\d+[.、)]\s*/.test(t)) count++;
  }
  return count;
}

async function generateContent() {
  const parts = await Promise.all(ENTRIES.map(async (entry) => {
    const [issue, comments] = await Promise.all([
      gh(`${API}/issues/${entry.no}`),
      fetchComments(entry.no),
    ]);
    let count = countItems(issue.body);
    for (const c of comments) count += countItems(c.body);
    const suffix = count > 0 ? `（${count}）` : '';
    return `${entry.icon} [${entry.name}](${issue.html_url})${suffix}`;
  }));

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
    console.log('   ' + content);
  } catch (err) {
    console.error('❌ fetch_issues.js 失败:', err.message);
  }
}

main();