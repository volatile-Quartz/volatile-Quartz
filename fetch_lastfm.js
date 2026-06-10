// fetch_lastfm.js
const fs = require('fs');

// 从环境变量读取密钥和用户名（稍后会通过 GitHub Actions 提供）
const API_KEY = process.env.LASTFM_API_KEY;
const USERNAME = process.env.LASTFM_USERNAME;

async function fetchAndUpdate() {
  if (!API_KEY || !USERNAME) {
    console.error('错误: 请设置环境变量 LASTFM_API_KEY 和 LASTFM_USERNAME');
    return;
  }

  const url = `https://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user=${USERNAME}&api_key=${API_KEY}&format=json&limit=5`;
  
  try {
    const response = await fetch(url);
    const data = await response.json();
    const tracks = data.recenttracks.track;
    
    let markdownContent = '### 🎵 最近在听\n\n';
    tracks.forEach(track => {
      const isNowPlaying = track['@attr'] && track['@attr'].nowplaying === 'true';
      const prefix = isNowPlaying ? '🎧 **正在播放：** ' : '🎵 ';
      markdownContent += `${prefix}${track.name} — ${track.artist['#text']}\n`;
    });
    
    // 读取 README.md
    const readmePath = './README.md';
    let readmeContent = fs.readFileSync(readmePath, 'utf8');
    
    const startMarker = '<!-- LASTFM_START -->';
    const endMarker = '<!-- LASTFM_END -->';
    const newSection = `${startMarker}\n${markdownContent}\n${endMarker}`;
    
    // 替换或追加
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