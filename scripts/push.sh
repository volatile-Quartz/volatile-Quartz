#!/usr/bin/env bash
# 一键同步并推送：自动 pull --rebase + commit + push
# 用法:
#   GITHUB_TOKEN=<token> ./scripts/push.sh "提交信息" [文件...]
# 默认暂存 fetch_lastfm.js / scripts/push.sh / AGENTS.md（避免 git add -A 误带入无关文件）
set -u

REPO_URL="https://x-access-token:${GITHUB_TOKEN:-}@github.com/bingdu748/bingdu748.git"
if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "错误: 请设置环境变量 GITHUB_TOKEN（仓库凭证）" >&2
  exit 1
fi
if [ $# -lt 1 ]; then
  echo "用法: GITHUB_TOKEN=<token> $0 \"提交信息\" [文件...]" >&2
  exit 1
fi
MSG="$1"; shift || true
FILES=("$@")
if [ ${#FILES[@]} -eq 0 ]; then
  FILES=(fetch_lastfm.js scripts/push.sh AGENTS.md)
fi

cd "$(dirname "$0")/.." || exit 1

echo "==> git fetch"
git fetch origin

echo "==> git add"
git add -- "${FILES[@]}"
if git diff --cached --quiet; then
  echo "没有暂存变更，跳过提交与推送"
  exit 0
fi

echo "==> git commit"
git -c user.name="bingdu748" \
    -c user.email="50004335+bingdu748@users.noreply.github.com" \
    commit -m "$MSG" || exit 1

echo "==> git pull --rebase（远程 main 常被机器人自动推进）"
if ! git pull --rebase origin main; then
  echo "rebase 冲突：请手动解决后执行 git add . && git rebase --continue，再推送" >&2
  exit 1
fi

echo "==> git push"
git push "$REPO_URL" HEAD:main
echo "✅ 推送成功: $(git log --oneline -1)"