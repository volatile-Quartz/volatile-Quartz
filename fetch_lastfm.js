// fetch_lastfm.js
const fs = require('fs');

const API_KEY = process.env.LASTFM_API_KEY;
const USERNAME = process.env.LASTFM_USERNAME;

async function fetchData(endpoint) {
  const url = `https://ws.audioscrobbler.com/2.0/${endpoint}&api_key=${API_KEY}&format=json`;
  const response = await fetch(url);
  return response.json();
}

async function fetchAndUpdate() {
  if (!API_KEY || !USERNAME) {
    console.error('错误: 请设置环境变量 LASTFM_API_KEY 和 LASTFM_USERNAME');
    return;
  }

  try {
    console.log('📡 正在获取 Last.fm 数据...');
    
    // 1. 获取用户信息和统计
    const userInfo = await fetchData(`?method=user.getinfo&user=${USERNAME}`);
    const user = userInfo.user;
    const playCount = parseInt(user.playcount) || 0;
    
    // 2. 获取最近播放记录
    const recentTracksData = await fetchData(`?method=user.getrecenttracks&user=${USERNAME}&limit=5`);
    const recentTracks = recentTracksData.recenttracks.track;
    
    // 3. 获取最常听的艺术家（最近7天）
    const topArtistsData = await fetchData(`?method=user.gettopartists&user=${USERNAME}&period=7day&limit=5`);
    const topArtists = topArtistsData.topartists.artist;
    
    // 4. 获取最常听的歌曲（最近7天）
    const topTracksData = await fetchData(`?method=user.gettoptracks&user=${USERNAME}&period=7day&limit=5`);
    const topTracks = topTracksData.toptracks.track;
    
    // 5. 获取最常听的专辑（最近7天）
    const topAlbumsData = await fetchData(`?method=user.gettopalbums&user=${USERNAME}&period=7day&limit=3`);
    const topAlbums = topAlbumsData.topalbums.album;

    // 生成最近在听内容
    const recentTracksList = recentTracks.map(track => {
      const isNowPlaying = track['@attr'] && track['@attr'].nowplaying === 'true';
      const prefix = isNowPlaying ? '🎧 **正在播放：**' : '🎵';
      return `${prefix} ${track.name} — ${track.artist['#text']}`;
    }).join('\n');

    // 生成热门艺术家内容
    const topArtistsList = topArtists.map((artist, index) => {
      const rankEmoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][index];
      return `${rankEmoji} **${artist.name}** — ${parseInt(artist.playcount).toLocaleString()} 次播放`;
    }).join('\n');

    // 生成热门歌曲内容
    const topTracksList = topTracks.map((track, index) => {
      const rankEmoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][index];
      return `${rankEmoji} ${track.name} — ${track.artist.name} (${parseInt(track.playcount).toLocaleString()}次)`;
    }).join('\n');

    // 生成热门专辑内容
    const topAlbumsList = topAlbums.map((album, index) => {
      const rankEmoji = ['🥇', '🥈', '🥉'][index];
      return `${rankEmoji} **${album.name}** — ${album.artist.name}`;
    }).join('\n');

    // 生成可视化内容
    let markdownContent = `### 🎵 音乐世界

**📊 统计概览**  
| 项目 | 数量 |
|------|------|
| 🎧 总播放次数 | ${playCount.toLocaleString()} |

**🎧 正在播放 / 最近在听**  
${recentTracksList}

**🌟 本周热门艺术家**  
${topArtistsList}

**🎶 本周热门歌曲**  
${topTracksList}

**💿 本周热门专辑**  
${topAlbumsList}

*📈 数据更新时间: ${new Date().toLocaleString('zh-CN')}*`;

    // 读取 README.md
    const readmePath = './README.md';
    let readmeContent = fs.readFileSync(readmePath, 'utf8');
    
    const startMarker = '<!-- LASTFM_START -->';
    const endMarker = '<!-- LASTFM_END -->';
    const newSection = `${startMarker}\n${markdownContent}\n${endMarker}`;
    
    if (readmeContent.includes(startMarker) && readmeContent.includes(endMarker)) {
      readmeContent = readmeContent.replace(new RegExp(`${startMarker}[\\s\\S]*?${endMarker}`), newSection);
    } else {
      readmeContent += `\n\n${newSection}`;
    }
    
    fs.writeFileSync(readmePath, readmeContent);
    console.log('✅ README 更新成功！');
  } catch (error) {
    console.error('❌ 获取 Last.fm 数据失败:', error);
  }
}

fetchAndUpdate();