#!/usr/bin/env python3
"""Phase 1: 拉取原始数据 + 清洗前统计 + 逐行清单（用户确认用）。
Usage: python3 lastfm/weekly_stats_preview.py 2026-09-21   (week-start Monday, Beijing)

产出（均带周次前缀，置于当前工作区根目录，供归档）：
- <week>_raw_stats.md     清洗前统计（全部原始记录，未过滤）
- <week>_lineup.txt       逐行清单：按时间排序每条原始记录 + 保留/剔除原因标注
输出到 stdout 的关键统计供 workflow 打印。
"""
import json, time, urllib.request, urllib.parse, collections, sys, os
from datetime import datetime, timedelta, timezone

API_KEY = "66b1c1ad34af302bb1672147f78e9e90"
USER = "volatile-Quartz"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(BASE_DIR, "lastfm_rules.json")))
TZ = timezone(timedelta(hours=8))

if len(sys.argv) < 2:
    print("usage: weekly_stats_preview.py 2026-09-21   (week-start Monday, Beijing)")
    sys.exit(1)
START = sys.argv[1]
T0 = int(datetime.strptime(START, "%Y-%m-%d").replace(tzinfo=TZ).timestamp())
WEEK = (T0, T0 + 7 * 86400)
week_label = "Week " + str(datetime.strptime(START, "%Y-%m-%d").isocalendar()[1])
week_end = (datetime.fromtimestamp(T0, TZ) + timedelta(days=6)).strftime("%Y-%m-%d")
label = START[:4] + week_label.replace(" ", "").lower()   # 2026week39

bl_artists = [a.lower() for a in RULES["blacklist_artists"]]
fkw = [k.lower() for k in RULES["filter_keywords"]]
bl_tracks = [t.split("|") for t in RULES["blacklist_tracks"]]

def fetch(lo, hi):
    out, page = [], 1
    while True:
        q = urllib.parse.urlencode({
            "method": "user.getrecenttracks", "user": USER, "api_key": API_KEY,
            "from": lo, "to": hi, "format": "json", "limit": 200, "page": page})
        data = json.load(urllib.request.urlopen("http://ws.audioscrobbler.com/2.0/?" + q, timeout=30))
        tracks = data.get("recenttracks", {}).get("track", [])
        if not tracks:
            break
        for t in tracks:
            if "@attr" in t:      # now playing
                continue
            out.append({"ts": int(t["date"]["uts"]), "artist": t["artist"]["#text"], "track": t["name"],
                        "album": t.get("album", {}).get("#text", "")})
        total = int(data.get("recenttracks", {}).get("@attr", {}).get("totalPages", page))
        if page >= total:
            break
        page += 1
        time.sleep(1.0)
    return out

def reason(r):
    """返回 (命中的规则类型, 命中值) 或 None（保留）。"""
    al, tl = r["artist"].strip().lower(), r["track"].strip().lower()
    for b in bl_artists:
        if b in al:
            return ("blacklist_artist", b)
    for k in fkw:
        if k in al or k in tl:
            return ("keyword", k)
    for ba, bt in bl_tracks:
        if ba in al and bt in tl:
            return ("blacklist_track", "{}|{}".format(ba, bt))
    return None

print("fetching...", flush=True)
recs = fetch(*WEEK)
recs.sort(key=lambda r: r["ts"])

# ---- 清洗前统计 ----
uniq = [r for r in recs if 1]  # 占位（下面用 dict 去重）
seen = {}
for r in recs:
    seen.setdefault((r["artist"].strip().lower(), r["track"].strip().lower()), r)
uniq = list(seen.values())
byday = collections.Counter(datetime.fromtimestamp(r["ts"] + 8 * 3600).strftime("%m-%d") for r in recs)
art = collections.Counter(r["artist"].strip() for r in recs)
trk = collections.Counter((r["artist"].strip(), r["track"].strip()) for r in recs)

md = []
md.append("## {} 清洗前统计（全部原始记录，未过滤）".format(label))
md.append("")
md.append("- 本周范围：{} ~ {}".format(START, week_end))
md.append("- 原始记录：**{} 条**（含重复播放），去重后独立曲目 **{} 首**，独立歌手 **{} 组**".format(len(recs), len(uniq), len(art)))
md.append("- 按天（原始条数）：{}".format("、".join("{}={}".format(d, byday[d]) for d in sorted(byday))))
md.append("")
md.append("### Top 歌手（按原始名播放次数，含可能需过滤的非音乐频道）")
for a, c in art.most_common(25):
    md.append("- {}（{}）".format(a, c))
md.append("")
md.append("### 重复播放 ≥2 次（原始名，去重后）")
played = {k: v for k, v in trk.items() if v >= 2}
for (a, t), c in sorted(played.items(), key=lambda x: -x[1]):
    md.append("- {}《{}》×{}".format(a, t, c))
open(label + "_raw_stats.md", "w").write("\n".join(md) + "\n")

# ---- 逐行清单 ----
lines = []
for r in recs:
    t = datetime.fromtimestamp(r["ts"] + 8 * 3600).strftime("%m-%d %H:%M")
    why = reason(r)
    if why:
        lines.append("[{}] [剔除-{}] {}《{}》 ({}: {})".format(t, why[0], r["artist"], r["track"], why[0], why[1]))
    else:
        lines.append("[{}] [保留] {}《{}》".format(t, r["artist"], r["track"]))
open(label + "_lineup.txt", "w").write("\n".join(lines) + "\n")
# 原始记录落盘（含 album），供归档为 01_raw.json 及 Phase 2 复用
json.dump(recs, open(label + "_raw.json", "w"), ensure_ascii=False)

print(json.dumps({"label": label, "raw": len(recs), "uniq": len(uniq), "artists": len(art),
                  "byday": dict(sorted(byday.items()))}, ensure_ascii=False))