#!/usr/bin/env bash
# Last.fm 周报管线 · 沙箱环境一键恢复（每次新会话开头跑一次）
# 用法: bash scripts/setup_sandbox.sh
set -e

cd /workspace

# 1) 仓库
if [ ! -d volatile-Quartz ]; then
  git clone --depth 1 -b lastfm-tools https://github.com/volatile-Quartz/volatile-Quartz.git
else
  echo "repo already cloned"
fi
cd volatile-Quartz

# 2) pillow
if python3 -c "import PIL" 2>/dev/null; then
  echo "pillow ok"
else
  pip install -q pillow
fi

# 3) CJK 字体（wqy-microhei，apt 源没有，从 Debian 池解包）
if [ -f /usr/share/fonts/truetype/wqy/wqy-microhei.ttc ]; then
  echo "cjk font ok"
else
  curl -sL -o /tmp/wqy.deb "http://ftp.debian.org/debian/pool/main/f/fonts-wqy-microhei/fonts-wqy-microhei_0.2.0-beta-3.1_all.deb"
  dpkg -x /tmp/wqy.deb /tmp/wqy
  mkdir -p /usr/share/fonts/truetype/wqy
  cp /tmp/wqy/usr/share/fonts/truetype/wqy/*.ttc /usr/share/fonts/truetype/wqy/
  fc-cache -f >/dev/null 2>&1 || true
  echo "cjk font installed"
fi

echo "sandbox ready: repo + pillow + CJK font"
