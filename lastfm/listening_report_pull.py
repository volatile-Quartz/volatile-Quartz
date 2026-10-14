#!/usr/bin/env python3
"""Last.fm 周报数据拉取（新管线，替代 weekly_stats_prep/enrich）。

口径：报告周 = 北京时间周五 00:00 → 次周五 00:00（与 last.fm listening-report 一致，实测对齐）。
Usage: python3 lastfm/listening_report_pull.py 2026-10-02 --page-text /tmp/report_inner.txt [--force]
  参数 = 报告周起始周五（北京时间）。
  --page-text  浏览器执行 report_extract_dump.js 得到的 innerText 全文（推荐，固化解析）。
  --page       旧路径：手工整理的页面 JSON（兼容保留）。
  --force      总数对账不一致时仍继续（用于周五后补 scrobble 的场景，人工确认后使用）。

对账闸门（防抓取错误固化进档案）：
  1. 硬断言：页面总 scrobbles == API 窗口原始条数，不等且无 --force 直接 exit 1；
  2. 内部一致性：页面 daily 求和 / clock 求和 == 总数，失败打警告；
  3. 软对账：页面 Top5 歌手在 API 归并榜单中的计数逐条比对，差异打 WARNING；
  4. 同实体巡逻：API Top50 歌手做规范化（casefold+去尾部标点）比对，疑似同一实体
     的拼写对输出到 01_report.json 的 candidate_merges，供人工确认后补进 solo_alias。

产出：
  lastfm/artifacts/report_<start>/00_raw.json    窗口内全部原始 scrobble
  lastfm/artifacts/report_<start>/01_report.json 页面数据 + API 深度榜单（黑名单剔除在出图阶段做）

归并口径：歌手聚合应用 solo_alias（复现页面的实体归并，如 Kikuo→きくお）；
榜单展示值 = 页面 Top5 精确值优先，API 深度条目补位。
页面缺失降级：--page-text/--page 都不给时仍可跑（页面字段为 None，总量卡显示 "—"）。
"""
import json, time, urllib.request, urllib.parse, collections, sys, os, re
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from report_text_parser import parse_report_text, check_consistency

API_KEY = "66b1c1ad34af302bb1672147f78e9e90"
USER = "volatile-Quartz"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(BASE_DIR, "lastfm_rules.json")))
TZ = timezone(timedelta(hours=8))

def ts_of(datestr):
    return int(datetime.strptime(datestr, "%Y-%m-%d").replace(tzinfo=TZ).timestamp())

def norm_artist(a):
    """同实体检测用规范化：casefold + 去尾部标点/空白。"""
    return re.sub(r"[\s.\-–—_·。．・・]+$", "", a.strip().casefold())

START = sys.argv[1] if len(sys.argv) > 1 else None
FORCE = "--force" in sys.argv
PAGE_TEXT = sys.argv[sys.argv.index("--page-text") + 1] if "--page-text" in sys.argv else None
PAGE_JSON = sys.argv[sys.argv.index("--page") + 1] if "--page" in sys.argv else None
if not START:
    print("usage: listening_report_pull.py 2026-10-02 --page-text /tmp/report_inner.txt [--force]")
    sys.exit(1)

T0 = ts_of(START)
T1 = T0 + 7 * 86400
solo_alias = RULES["solo_alias"]

def fetch(lo, hi):
    out, page = [], 1
    while True:
        q = urllib.parse.urlencode({
            "method": "user.getrecenttracks", "user": USER, "api_key": API_KEY,
            "from": lo, "to": hi, "format": "json", "limit": 200, "page": page})
        d = json.load(urllib.request.urlopen("http://ws.audioscrobbler.com/2.0/?" + q, timeout=30))
        tr = d.get("recenttracks", {}).get("track", [])
        if not tr:
            break
        for t in tr:
            if "@attr" in t:
                continue
            out.append({"ts": int(t["date"]["uts"]), "artist": t["artist"]["#text"],
                        "track": t["name"], "album": t.get("album", {}).get("#text", "")})
        total = int(d.get("recenttracks", {}).get("@attr", {}).get("totalPages", page))
        if page >= total:
            break
        page += 1
        time.sleep(1.0)
    return out

def canon_artist(a):
    a = a.strip()
    return solo_alias.get(a, a)

# ── 页面数据：innerText 固化解析优先，JSON 兼容 ──
pg = None
if PAGE_TEXT and os.path.exists(PAGE_TEXT):
    pg = parse_report_text(open(PAGE_TEXT).read())
    print("page parsed from innerText:", PAGE_TEXT)
elif PAGE_JSON and os.path.exists(PAGE_JSON):
    pg = json.load(open(PAGE_JSON))
    print("page loaded from json:", PAGE_JSON)
else:
    print("⚠️ 无页面数据（--page-text/--page），页面字段将为空，总量卡显示 —")

print("fetching window {} (+08:00) ...".format(START), flush=True)
raw = fetch(T0, T1)
print("raw scrobbles:", len(raw))

# ── 对账闸门 1：总数硬断言 ──
page_total = (pg or {}).get("totals", {}).get("scrobbles")
if page_total is not None and page_total != len(raw):
    msg = "总数对账失败：page={} vs api={}（差 {}）".format(page_total, len(raw), len(raw) - page_total)
    if FORCE:
        print("⚠️ FORCE 继续 ——", msg)
    else:
        print("❌", msg)
        print("   若是周五后补 scrobble 导致，确认后加 --force 重跑。")
        sys.exit(1)
else:
    print("总数对账 OK: page={} api={}".format(page_total, len(raw)))

# ── 对账闸门 2：页面内部一致性 ──
if pg:
    ok, detail = check_consistency(pg)
    print("页面内部一致性:", "OK" if ok else "⚠️ FAIL", "|", detail)

art_cnt = collections.Counter(canon_artist(r["artist"]) for r in raw)
trk_cnt = collections.Counter((r["artist"], r["track"]) for r in raw)
alb_cnt = collections.Counter((r["artist"], r["album"]) for r in raw if r["album"])

api_artists = [{"name": a, "scrobbles": c} for a, c in art_cnt.most_common(50)]
api_tracks = [{"name": t, "artist": a, "scrobbles": c} for (a, t), c in trk_cnt.most_common(50)]
api_albums = [{"name": t, "artist": a, "scrobbles": c} for (a, t), c in alb_cnt.most_common(50)]

# ── 对账闸门 3：页面 Top5 歌手 vs API 归并榜单（软警告） ──
api_map = {e["name"].casefold(): e["scrobbles"] for e in api_artists}
for e in (pg or {}).get("top_artists", []):
    got = api_map.get(e["name"].casefold())
    if got is None:
        print("⚠️ 页面 Top5 歌手未在 API 榜命中:", e["name"], e["scrobbles"])
    elif got != e["scrobbles"]:
        print("⚠️ 计数不一致: {} page={} api={}".format(e["name"], e["scrobbles"], got))

# ── 对账闸门 4：同实体巡逻（规范化重复 → 候选归并对） ──
norm_map = collections.defaultdict(set)
for e in api_artists:
    norm_map[norm_artist(e["name"])].add(e["name"])
candidate_merges = sorted(sorted(v) for v in norm_map.values() if len(v) > 1)
if candidate_merges:
    print("⚠️ 疑似同实体（确认后补进 solo_alias）:", candidate_merges)

# ── 页面 Top5 曲目/专辑缺 artist 时从 API 榜补 ──
api_track_artist = {e["name"].casefold(): e["artist"] for e in api_tracks}
api_album_artist = {e["name"].casefold(): e["artist"] for e in api_albums}
for key, lookup in [("top_tracks", api_track_artist), ("top_albums", api_album_artist)]:
    for e in (pg or {}).get(key, []):
        if not e.get("artist"):
            e["artist"] = lookup.get(e["name"].casefold())

end_date = (datetime.fromtimestamp(T0, TZ) + timedelta(days=6)).strftime("%Y-%m-%d")
report = {
    "meta": {"start": START, "end": end_date, "username": USER,
             "range_text": (pg or {}).get("meta", {}).get("range_text"),
             "generated_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %z"),
             "candidate_merges": candidate_merges},
    "totals": (pg or {}).get("totals"),
    "daily": (pg or {}).get("daily"),
    "daily_prev": (pg or {}).get("daily_prev"),
    "clock": (pg or {}).get("clock"),
    "tags_current": (pg or {}).get("tags_current"),
    "decades": (pg or {}).get("decades"),
    "community": (pg or {}).get("community"),
    "music_ratio": (pg or {}).get("music_ratio"),
    "discovery": (pg or {}).get("discovery"),
    "top_new": (pg or {}).get("top_new"),
    "page_top_artists": (pg or {}).get("top_artists", []),
    "page_top_tracks": (pg or {}).get("top_tracks", []),
    "page_top_albums": (pg or {}).get("top_albums", []),
    "api": {"total_scrobbles": len(raw), "window": {"from_ts": T0, "to_ts": T1},
            "top_artists": api_artists, "top_tracks": api_tracks, "top_albums": api_albums},
}
outdir = os.path.join(BASE_DIR, "artifacts", "report_" + START)
os.makedirs(outdir, exist_ok=True)
json.dump(raw, open(os.path.join(outdir, "00_raw.json"), "w"), ensure_ascii=False)
json.dump(report, open(os.path.join(outdir, "01_report.json"), "w"), ensure_ascii=False, indent=1)
print("top5 check (api):", [(a["name"], a["scrobbles"]) for a in api_artists[:5]])
print("saved:", outdir + "/00_raw.json, 01_report.json")
