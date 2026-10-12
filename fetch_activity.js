// fetch_activity.js
// 抓取 GitHub public events，聚合出跨仓库"最近活跃"3 条，更新主页区块。
//
// 展示的 event 类型：Push / Release / Issue / PR / 仓库创建。
// WatchEvent（star 别人）与杂项不展示，保持"产出"语义。

const fs = require('fs');

const USER = 'volatile-Quartz';
const EVENTS_URL = `https://api.github.com/users/${USER}/events/public?per_page=30`;

// event type → 动词描述（payload 里取细节）
function describe(ev) {
  const repo = ev.repo?.name ? `[${ev.repo.name.replace(`${USER}/`, '')}]` : '';
  const date = ev.created_at ? ev.created_at.slice(5, 10).replace('-', '/') : '';
  switch (ev.type) {
    case 'PushEvent': {
      const n = ev.payload?.size || ev.payload?.commits?.length || 0;
      if (!n) return null;  // size=0 是分支删除/force push 元事件，不展示
      return { repo, text: `推送 ${n} 个 commit`, date, weight: 2 };
    }
    case 'ReleaseEvent':
      return { repo, text: `发布 ${ev.payload?.release?.tag_name || ''}`.trimEnd(), date, weight: 3 };
    case 'IssuesEvent':
      return { repo, text: `${ev.payload?.action === 'closed' ? '关闭' : '更新'} issue #${ev.payload?.issue?.number}`, date, weight: 1 };
    case 'PullRequestEvent':
      return { repo, text: `${ev.payload?.action === 'closed' ? '合并' : '提交'} PR #${ev.payload?.pull_request?.number}`, date, weight: 2 };
    case 'CreateEvent':
      return { repo, text: ev.payload?.ref_type === 'repository' ? '创建仓库' : `创建 ${ev.payload?.ref_type || '分支'} ${ev.payload?.ref || ''}`.trimEnd(), date, weight: 1 };
    default:
      return null;
  }
}

async function generateContent() {
  const headers = { 'User-Agent': 'homepage-activity-fetcher' };
  if (process.env.GITHUB_TOKEN) {
    headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  }
  const res = await fetch(EVENTS_URL, { headers });
  if (!res.ok) throw new Error(`GitHub API HTTP ${res.status}`);
  const events = await res.json();
  if (!Array.isArray(events)) throw new Error('GitHub API 返回结构异常');

  // 去重合并：events API 天然按时间倒序，遍历时同一 (repo|text|date) 只保留首次（最新）出现。
  // weight 仅在合并时用于挑选描述，不影响最终顺序。
  const merged = new Map();
  for (const ev of events) {
    const d = describe(ev);
    if (!d) continue;
    const key = `${d.repo}|${d.text}|${d.date}`;
    const prev = merged.get(key);
    if (!prev || d.weight > prev.weight) merged.set(key, d);
  }

  const items = [...merged.values()]
    .slice(0, 3)
    .map(d => `- ${d.repo} ${d.text}（${d.date}）`)
    .join('\n');

  if (!items) return '最近暂无公开动态';

  return `${items}

→ [活动流 →](https://github.com/${USER})`;
}

const startMarker = '<!-- ACTIVITY_START -->';
const endMarker = '<!-- ACTIVITY_END -->';

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
    console.log('✅ 最近活跃模块更新成功');
  } catch (err) {
    console.error('❌ fetch_activity.js 失败:', err.message);
  }
}

main();
