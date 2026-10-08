#!/usr/bin/env python3
"""Week stats: fetch, clean, aggregate.
Usage: python3 weekly_stats_prep.py 2026-09-28   (week-start Monday, Beijing)

Reads lastfm_rules.json (same dir). Writes /tmp/lastfm_prep.json.
口径约定：
- 有效记录 = 清洗后播放次数（含重复）；独立曲目 = 清洗后去重；
- 每日按「独立曲目/日」统计（供“最猛/最冷清 X 首”），同时保留播放次数/日；
- 署名清洗顺序：artist_by_song → solo_alias/feat_map/amp_map/no_split → title_by_song（前缀/精确，优先于后缀剥离）。
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
    print("usage: weekly_stats_prep.py 2026-09-28   (week-start Monday, Beijing)")
    sys.exit(1)
START = sys.argv[1]
T0 = ts_of(START)
WEEK = (T0, T0 + 7 * 86400)
PREV = (T0 - 7 * 86400, T0)
week_label = "Week " + str(datetime.strptime(START, "%Y-%m-%d").isocalendar()[1])
week_end = (datetime.fromtimestamp(T0, TZ) + timedelta(days=6)).strftime("%Y-%m-%d")

bl_artists = [a.lower() for a in RULES["blacklist_artists"]]
fkw = [k.lower() for k in RULES["filter_keywords"]]
bl_tracks = [t.split("|") for t in RULES["blacklist_tracks"]]
solo_alias = RULES["solo_alias"]
feat_map = RULES["feat_map"]
amp_map = RULES["amp_map"]
no_split = set(RULES["no_split"])
artist_by_song = RULES["artist_by_song"]
title_by_song = RULES["title_by_song"]

def fetch(lo, hi):
    out, page = [], 1
    while True:
        q = urllib.parse.urlencode({
            "method": "user.getrecenttracks", "user": USER, "api_key": API_KEY,
            "from": lo, "to": hi, "format": "json", "limit": 200, "page": page})
        url = "http://ws.audioscrobbler.com/2.0/?" + q
        data = json.load(urllib.request.urlopen(url, timeout=30))
        tracks = data.get("recenttracks", {}).get("track", [])
        if not tracks:
            break
        for t in tracks:
            if "@attr" in t:      # now playing
                continue
            out.append({"ts": int(t["date"]["uts"]), "artist": t["artist"]["#text"], "track": t["name"]})
        total = int(data.get("recenttracks", {}).get("@attr", {}).get("totalPages", page))
        if page >= total:
            break
        page += 1
        time.sleep(1.0)
    return out

def display_artist(a):
    a = a.strip()
    if a in solo_alias:
        a = solo_alias[a]
    if a in feat_map:
        p = feat_map[a]
        return "{} feat. {}".format(p[0], p[1])
    if a in amp_map:
        return amp_map[a]
    if a in no_split:
        return a
    return a

def clean(rec):
    """Apply lastfm_rules: blacklist, alias/署名映射, 曲名清洗。"""
    ra = rec["artist"].strip()
    rt = rec["track"].strip()
    al, tl = ra.lower(), rt.lower()
    if any(b in al for b in bl_artists):
        return None
    if any(k in al for k in fkw) or any(k in tl for k in fkw):
        return None
    if any(ba in al and bt in tl for ba, bt in bl_tracks):
        return None
    # artist_by_song（按原始歌手|原始曲名修正归属）
    artist = ra
    for k, v in artist_by_song.items():
        a, t = k.split("|", 1)
        if ra == a and rt == t:
            artist = v
            break
    disp = display_artist(artist)
    # title_by_song（精确或前缀匹配；命中则不再做后缀剥离）
    title = rt
    overridden = False
    for k, v in title_by_song.items():
        a, t = k.split("|", 1)
        if disp == a and (rt == t or rt.startswith(t)):
            title = v
            overridden = True
            break
    if not overridden:
        t = rt
        ttl = t.lower()
        for suf in RULES["title_suffix"]:
            s = suf.lower()
            if ttl.startswith(s + " ") or ttl.endswith(" " + s) or ttl == s:
                t = t[:-len(s)].strip().rstrip(" -–()[]【】")
                ttl = t.lower()
        if RULES["extra_rules"].get("strip_trailing_parenthetical"):
            if ttl.endswith(")") and "(" in t:
                t = t[:t.rfind("(")].strip()
        title = t
    return {"ts": rec["ts"], "artist": disp, "title": title}

def dedup(records):
    """Same artist+title -> keep latest. Returns ordered dict key->record."""
    seen = {}
    for r in records:
        key = (r["artist"].lower(), r["title"].lower())
        seen[key] = r   # later overwrites => keep latest
    return list(seen.values())

def main():
    print("fetching week...", flush=True)
    wk = fetch(*WEEK)
    print("fetching prev week...", flush=True)
    pv = fetch(*PREV)
    wk_clean_all = [c for c in (clean(r) for r in wk) if c]
    pv_clean_all = [c for c in (clean(r) for r in pv) if c]
    wk_clean = dedup(wk_clean_all)     # unique tracks
    pv_clean = dedup(pv_clean_all)
    pv_keys = {(r["artist"].lower(), r["title"].lower()) for r in pv_clean}

    tz = 8 * 3600
    # 每日：独立曲目（set）与播放次数（Counter）两种口径
    daily_uniq = collections.defaultdict(set)
    daily_plays = collections.Counter()
    for r in wk_clean_all:
        d = datetime.fromtimestamp(r["ts"] + tz).strftime("%m-%d")
        daily_plays[d] += 1
        daily_uniq[d].add((r["artist"].lower(), r["title"].lower()))
    daily = {d: len(s) for d, s in sorted(daily_uniq.items())}
    daily_plays = dict(sorted(daily_plays.items()))

    art_cnt = collections.Counter(r["artist"] for r in wk_clean_all)
    trk_cnt = collections.Counter((r["artist"], r["title"]) for r in wk_clean_all)

    new_tracks = [r for r in wk_clean if (r["artist"].lower(), r["title"].lower()) not in pv_keys]
    rep_tracks = [r for r in wk_clean if (r["artist"].lower(), r["title"].lower()) in pv_keys]
    played_again = [{"artist": a, "title": t, "count": c} for (a, t), c in trk_cnt.items() if c >= 2]
    played_again.sort(key=lambda x: -x["count"])

    pv_art_cnt = collections.Counter(r["artist"] for r in pv_clean)
    new_artists = [a for a in art_cnt if a not in pv_art_cnt]

    stats = {
        "meta": {"week_label": week_label, "week_range": "{} ~ {}".format(START, week_end)},
        "week": {"raw": len(wk), "raw_prev": len(pv)},
        "clean": {"plays": len(wk_clean_all), "plays_prev": len(pv_clean_all),
                  "tracks": len(wk_clean), "tracks_prev": len(pv_clean),
                  "artists": len(art_cnt), "artists_prev": len(pv_art_cnt)},
        "daily": daily,
        "daily_plays": daily_plays,
        "top_artists": art_cnt.most_common(15),
        "top_tracks": trk_cnt.most_common(10),
        "new_tracks": len(new_tracks), "rep_tracks": len(rep_tracks),
        "played_again": played_again,
        "new_artists": new_artists,
        "full_counts": {"{}||{}".format(a, t): c for (a, t), c in trk_cnt.items()},
    }
    lookup = {}
    for r in wk_clean:
        lookup.setdefault((r["artist"], r["title"]), r)
    stats["_lookup"] = {"{}||{}".format(a, t): {"artist_raw": v["artist"], "title_raw": v["title"]}
                        for (a, t), v in lookup.items()}
    json.dump(stats, open("/tmp/lastfm_prep.json", "w"), ensure_ascii=False, indent=1)
    print("week raw={} clean_plays={} unique={} | prev raw={} clean_plays={} unique={}".format(
        len(wk), len(wk_clean_all), len(wk_clean), len(pv), len(pv_clean_all), len(pv_clean)), flush=True)
    print("daily(unique):", daily, flush=True)
    print("top_artists:", art_cnt.most_common(15), flush=True)

if __name__ == "__main__":
    main()
