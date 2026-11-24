"""
统一的 Last.fm 凭证加载器 — 零依赖，优先读环境变量，fallback 读项目根 .env

用法：
    from _env import API_KEY, USER

加载优先级：
  1. 已设的 LASTFM_API_KEY / LASTFM_USERNAME 环境变量
  2. 项目根 .env 文件（lastfm/../../.env）
"""
import os
from pathlib import Path


def _load_env_file():
    """从项目根 .env 读 K=V，写入 os.environ（仅补未设的）。"""
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if v.startswith(('"', "'")) and v.endswith(('"', "'")):
            v = v[1:-1]
        os.environ.setdefault(k, v)


_load_env_file()

API_KEY = os.environ.get("LASTFM_API_KEY")
USER = os.environ.get("LASTFM_USERNAME", "volatile-Quartz")

if not API_KEY:
    raise RuntimeError(
        "LASTFM_API_KEY 未设置 — 请在项目根创建 .env（复制 .env.example），"
        "或 export LASTFM_API_KEY=xxx"
    )
