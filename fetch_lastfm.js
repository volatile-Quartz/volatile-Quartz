// fetch_lastfm.js
const fs = require('fs');

const API_KEY = process.env.LASTFM_API_KEY;
const USERNAME = process.env.LASTFM_USERNAME;

async function fetchData(params) {
  const url = `https://ws.audioscrobbler.com/2.0/?${params}&api_key=${API_KEY}&format=json`;
  const response = await fetch(url);
  return response.json();
}

function asArray(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

async function getWeeklyPlayCount(from, to) {
  const data = await fetchData(`method=user.getweeklytrackchart&user=${USERNAME}&from=${from}&to=${to}`);
  const tracks = asArray(data.weeklytrackchart?.track);
  return tracks.reduce((sum, track) => sum + (parseInt(track.playcount) || 0), 0);
}

async function fetchAndUpdate() {
  if (!API_KEY || !USERNAME) {
    console.error('错误: 请设置环境变量 LASTFM_API_KEY 和 LASTFM_USERNAME');
    return;
  }

  try {
    console.log('📡 正在获取 Last.fm 数据...');
    
    // 1. 获取用户信息和统计
    const userInfo = await fetchData(`method=user.getinfo&user=${USERNAME}`);
    const user = userInfo.user;
    const playCount = parseInt(user.playcount) || 0;
    const joinDate = new Date(user.registered.unixtime * 1000);
    
    // 2. 获取最近播放记录
    const recentTracksData = await fetchData(`method=user.getrecenttracks&user=${USERNAME}&limit=10`);
    const allRecentTracks = recentTracksData.recenttracks.track;
    const nowPlaying = allRecentTracks.find(track => track['@attr'] && track['@attr'].nowplaying === 'true');
    const recentHistory = allRecentTracks.filter(track => !(track['@attr'] && track['@attr'].nowplaying === 'true'));
    // 去除连续重复的相同歌曲（同一首歌连续播放两次只显示一条），再取最近 3 条
    const recentTracks = recentHistory.filter(
      (track, index) => index === 0
        || !(track.name === recentHistory[index - 1].name
          && track.artist['#text'] === recentHistory[index - 1].artist['#text'])
    ).slice(0, 3);
    
    // 3. 获取本周热门艺术家/歌曲/专辑
    const [topArtistsWeek, topTracksWeek, topAlbumsWeek] = await Promise.all([
      fetchData(`method=user.gettopartists&user=${USERNAME}&period=7day&limit=5`),
      fetchData(`method=user.gettoptracks&user=${USERNAME}&period=7day&limit=5`),
      fetchData(`method=user.gettopalbums&user=${USERNAME}&period=7day&limit=3`)
    ]);
    
    // 4. 获取全部时间热门艺术家/歌曲/专辑
    const [topArtistsAll, topTracksAll, topAlbumsAll, topAlbumsTotal] = await Promise.all([
      fetchData(`method=user.gettopartists&user=${USERNAME}&period=overall&limit=5`),
      fetchData(`method=user.gettoptracks&user=${USERNAME}&period=overall&limit=5`),
      fetchData(`method=user.gettopalbums&user=${USERNAME}&period=overall&limit=3`),
      fetchData(`method=user.gettopalbums&user=${USERNAME}&period=overall&limit=1`)
    ]);
    const artistCount = parseInt(topArtistsAll.topartists['@attr'].total) || 0;
    const trackCount = parseInt(topTracksAll.toptracks['@attr'].total) || 0;
    const albumCount = parseInt(topAlbumsTotal.topalbums['@attr'].total) || 0;
    
    // 5. 获取用户标签
    const tagsData = await fetchData(`method=user.gettags&user=${USERNAME}&limit=10`);
    const tags = tagsData.tags ? tagsData.tags.tag : [];
    
    // 6. 获取好友列表
    const friendsData = await fetchData(`method=user.getfriends&user=${USERNAME}&limit=5`);
    const friends = friendsData.friends ? friendsData.friends.user : [];
    
    // 7. 获取周播放趋势（最近 3 个自然周的总播放次数）
    const weeklyChartData = await fetchData(`method=user.getweeklychartlist&user=${USERNAME}`);
    // getweeklychartlist 返回的 chart 列表按时间升序排列（最旧在前）。
    // 直接 slice(0, 3) 会永远取到账号最早的 3 周（远古数据播放数为 0），
    // 必须先按 from 倒序，再取前 3 条才是最近 3 周。
    const weeklyCharts = asArray(weeklyChartData.weeklychartlist?.chart)
      .sort((a, b) => parseInt(b.from, 10) - parseInt(a.from, 10))
      .slice(0, 3);
    const weeklyCounts = await Promise.all(
      weeklyCharts.map(chart => getWeeklyPlayCount(chart.from, chart.to))
    );
    const weeklyStats = weeklyCharts.map((chart, index) => {
      const date = new Date(parseInt(chart.from, 10) * 1000);
      const label = index === 0 ? '📅 本周' : `📆 ${date.getMonth() + 1}/${date.getDate()}`;
      return `- ${label}: ${weeklyCounts[index].toLocaleString()} 次播放`;
    }).join('\n');
    const weeklyStatsSection = weeklyStats
      ? `**📈 播放趋势**  
${weeklyStats}

`
      : '';
    const nowPlayingSection = nowPlaying
      ? `🎧 **正在播放：** ${nowPlaying.name} — ${nowPlaying.artist['#text']}`
      : '';

    // 生成最近在听内容（列表形式）
    const recentTracksList = recentTracks.map(track => {
      return `- 🎵 ${track.name} — ${track.artist['#text']}`;
    }).join('\n');

    // 生成本周热门艺术家内容（列表形式）
    const topArtistsWeekList = topArtistsWeek.topartists.artist.map((artist, index) => {
      const rankEmoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][index];
      return `- ${rankEmoji} **${artist.name}** — ${parseInt(artist.playcount).toLocaleString()} 次播放`;
    }).join('\n');

    // 生成本周热门歌曲内容（列表形式）
    const topTracksWeekList = topTracksWeek.toptracks.track.map((track, index) => {
      const rankEmoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][index];
      return `- ${rankEmoji} ${track.name} — ${track.artist.name}`;
    }).join('\n');

    // 生成本周热门专辑内容（列表形式）
    const topAlbumsWeekList = topAlbumsWeek.topalbums.album.map((album, index) => {
      const rankEmoji = ['🥇', '🥈', '🥉'][index];
      return `- ${rankEmoji} **${album.name}** — ${album.artist.name}`;
    }).join('\n');

    // 生成全部时间热门艺术家内容（列表形式）
    const topArtistsAllList = topArtistsAll.topartists.artist.map((artist, index) => {
      const rankEmoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][index];
      return `- ${rankEmoji} **${artist.name}** — ${parseInt(artist.playcount).toLocaleString()} 次播放`;
    }).join('\n');

    // 生成全部时间热门歌曲内容（列表形式）
    const topTracksAllList = topTracksAll.toptracks.track.map((track, index) => {
      const rankEmoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][index];
      return `- ${rankEmoji} ${track.name} — ${track.artist.name}`;
    }).join('\n');

    // 生成标签云（无标签时整块隐藏，不显示"暂无标签"占位）
    const tagsSection = tags.length > 0
      ? `### 🏷️ 我的音乐标签
${tags.slice(0, 8).map(tag => `#${tag.name}`).join(' ')}

---

`
      : '';

    // 生成好友列表（列表形式）
    const friendsList = friends.length > 0 ? friends.map(friend => `- 👤 [${friend.name}](https://www.last.fm/user/${friend.name})`).join('\n') : '暂无好友';

    // 生成完整的可视化内容
    let markdownContent = `### 🎵 音乐世界

**📊 统计概览**  
| 项目 | 数据 |
|------|------|
| 🎧 播放总次数 | ${playCount.toLocaleString()} 次 |
| 🎤 歌手总计 | ${artistCount.toLocaleString()} 位 |
| 💿 专辑总计 | ${albumCount.toLocaleString()} 张 |
| 🎶 歌曲总计 | ${trackCount.toLocaleString()} 首 |

${nowPlayingSection}

**🎵 最近在听**  
${recentTracksList}

${weeklyStatsSection}---

### 🌟 本周排行

**🎤 热门艺术家**  
${topArtistsWeekList}

**🎶 热门歌曲**  
${topTracksWeekList}

**💿 热门专辑**  
${topAlbumsWeekList}

---

### 🏆 历史最佳

**🎤 最爱的艺术家**  
${topArtistsAllList}

**🎶 最爱的歌曲**  
${topTracksAllList}

---

${tagsSection}### 👥 Last.fm 好友
${friendsList}

*更新时间: ${new Date().toLocaleString('zh-CN')}*`;

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