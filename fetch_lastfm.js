// fetch_lastfm.js
// 读取 Last.fm 总播放/歌手/专辑/歌曲四项统计，更新主页那张紧凑表格。
//
// 主页只展示这四项概览 + 更新时间；周报等详细内容由 lastfm/ 下的
// weekly-lastfm-* workflow 单独产出，与本脚本无关。

const fs = require('fs');

const API_KEY = process.env.LASTFM_API_KEY;
const USERNAME = process.env.LASTFM_USERNAME;

async function fetchData(params) {
  const url = `https://ws.audioscrobbler.com/2.0/?${params}&api_key=${API_KEY}&format=json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Last.fm HTTP ${res.status}`);
  return res.json();
}

// Last.fm 的 total 在 @attr.total 里，取值可能是字符串
const totalOf = (obj) => parseInt(obj?.['@attr']?.total, 10) || 0;

async function generateContent() {
  if (!API_KEY || !USERNAME) {
    throw new Error('请设置环境变量 LASTFM_API_KEY 和 LASTFM_USERNAME');
  }

  const [userInfo, topArtists, topAlbums, topTracks] = await Promise.all([
    fetchData(`method=user.getinfo&user=${USERNAME}`),
    fetchData(`method=user.gettopartists&user=${USERNAME}&period=overall&limit=1`),
    fetchData(`method=user.gettopalbums&user=${USERNAME}&period=overall&limit=1`),
    fetchData(`method=user.gettoptracks&user=${USERNAME}&period=overall&limit=1`),
  ]);

  const plays = parseInt(userInfo.user?.playcount, 10) || 0;
  const artists = totalOf(topArtists.topartists);
  const albums = totalOf(topAlbums.topalbums);
  const tracks = totalOf(topTracks.toptracks);

  if (!plays) throw new Error('未取到播放次数，接口结构可能已变化');

  const stamp = new Date().toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai', hour12: false,
  });

  return `| 🎧 播放 | 🎤 歌手 | 💿 专辑 | 🎶 歌曲 |
|:-------:|:-------:|:-------:|:-------:|
| ${plays.toLocaleString()} | ${artists.toLocaleString()} | ${albums.toLocaleString()} | ${tracks.toLocaleString()} |

*更新于 ${stamp} · [进入 Last.fm →](https://www.last.fm/user/${USERNAME})*`;
}

const startMarker = '<!-- LASTFM_START -->';
const endMarker = '<!-- LASTFM_END -->';

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
    console.log('✅ Last.fm 模块更新成功');
  } catch (err) {
    console.error('❌ fetch_lastfm.js 失败:', err.message);
  }
}

main();