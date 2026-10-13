#!/usr/bin/env python3
"""Last.fm 周报数据拉取（新管线，替代 weekly_stats_prep/enrich）。

口径：报告周 = 北京时间周五 00:00 → 次周五 00:00（与 last.fm listening-report 一致，实测对齐）。
Usage: python3 lastfm/listening_report_pull.py 2026-10-02 [--page /tmp/report_page.json]
  参数 = 报告周起始周五（北京时间）；--page 为浏览器抓取的周报页 JSON（可选）。

产出：
  lastfm/artifacts/report_<start>/00_raw.json   窗口内全部原始 scrobble（ts/artist/track/album）
  lastfm/artifacts/report_<start>/01_report.json 页面数据 + API 深度榜单（黑名单剔除在出图阶段做，这里只归并）

归并口径（与周报页对齐）：
  - 歌手聚合时应用 solo_alias 拼写归并（页面把 Kikuo/きくお 合并计数，此处同口径）；
  - 榜单展示值 = 页面 Top5 精确值优先，API 深度条目补位（页面专辑计数用服务器元数据，可能比 scrobble 标签 +1）。
"""
import json, time, urllib.request, urllib.parse, collections, sys, os
from datetime import datetime, timedelta, timezone

API_KEY = "66b1c1ad34af302bb1672147f78e9e90"
USER = "volatile-Quartz"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(BASE_DIR, "lastfm_rules.json")))
TZ = timezone(timedelta(hours=8))

def ts_of(datestr):
    return int(datetime.strptime(datestr, "%Y-%m-%d").replace(tzinfo=TZ).timestamp())

if len(sys.argv) < 2:
    print("usage: listening_report_pull.py 2026-10-02 [--page /path/to/page.json]")
    sys.exit(1)
START = sys.argv[1]
PAGE_FILE = None
if "--page" in sys.argv:
    i = sys.argv.index("--page")
    PAGE_FILE = sys.argv[i + 1]

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

print("fetching window {} (+08:00) ...".format(START), flush=True)
raw = fetch(T0, T1)
print("raw scrobbles:", len(raw))

art_cnt = collections.Counter(canon_artist(r["artist"]) for r in raw)
trk_cnt = collections.Counter((r["artist"], r["track"]) for r in raw)
alb_cnt = collections.Counter((r["artist"], r["album"]) for r in raw if r["album"])

api_artists = [{"name": a, "scrobbles": c} for a, c in art_cnt.most_common(50)]
api_tracks = [{"name": t, "artist": a, "scrobbles": c} for (a, t), c in trk_cnt.most_common(50)]
api_albums = [{"name": t, "artist": a, "scrobbles": c} for (a, t), c in alb_cnt.most_common(50)]

pg = json.load(open(PAGE_FILE)) if PAGE_FILE and os.path.exists(PAGE_FILE) else {}
end_date = (datetime.fromtimestamp(T0, TZ) + timedelta(days=6)).strftime("%Y-%m-%d")
report = {
    "meta": {"start": START, "end": end_date, "username": USER,
             "range_text": pg.get("meta", {}).get("range_text"),
             "generated_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %z")},
    "totals": pg.get("totals"),
    "clock": pg.get("clock"),
    "tags": pg.get("tags"),
    "discovery": pg.get("discovery"),
    "music_ratio": pg.get("music_ratio"),
    "page_top_artists": pg.get("top_artists", []),
    "page_top_tracks": pg.get("top_tracks", []),
    "page_top_albums": pg.get("top_albums", []),
    "api": {"total_scrobbles": len(raw), "window": {"from_ts": T0, "to_ts": T1},
            "top_artists": api_artists, "top_tracks": api_tracks, "top_albums": api_albums},
}
outdir = os.path.join(BASE_DIR, "artifacts", "report_" + START)
os.makedirs(outdir, exist_ok=True)
json.dump(raw, open(os.path.join(outdir, "00_raw.json"), "w"), ensure_ascii=False)
json.dump(report, open(os.path.join(outdir, "01_report.json"), "w"), ensure_ascii=False, indent=1)
print("top5 check (api):", [ (a["name"], a["scrobbles"]) for a in api_artists[:5] ])
print("saved:", outdir + "/00_raw.json, 01_report.json")
