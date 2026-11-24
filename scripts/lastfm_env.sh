#!/usr/bin/env bash
# 一键载入本地 .env — 任何新 agent/shell 会话先 source 这个脚本
#   cd /workspace && source scripts/lastfm_env.sh
# 之后 fetch_lastfm.js、lastfm/*.py 都能自动读到 LASTFM_API_KEY / LASTFM_USERNAME
set -euo pipefail

# 找 .env：优先从脚本位置推，兜底 cwd / cwd/父目录
_ENV_CANDIDATES=()
if [ -n "${BASH_VERSION:-}" ] && [ -n "${BASH_SOURCE[0]:-}" ]; then
  _ENV_CANDIDATES+=("$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env")
fi
if [ -n "${ZSH_VERSION:-}" ]; then
  _ENV_CANDIDATES+=("$(cd "$(dirname "${(%):-%N}")/.." && pwd)/.env")
fi
_ENV_CANDIDATES+=("$(pwd)/.env" "$(pwd)/../.env")

ENV_FILE=""
for _c in "${_ENV_CANDIDATES[@]}"; do
  if [ -f "$_c" ]; then ENV_FILE="$_c"; break; fi
done

if [ -z "$ENV_FILE" ]; then
  echo "[lastfm_env] 未找到 .env — 请先从 .env.example 创建 .env 并填入真实 key" >&2
  return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a
echo "[lastfm_env] 已载入 LASTFM_USERNAME=${LASTFM_USERNAME:-<unset>}  (via $ENV_FILE)"
