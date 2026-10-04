#!/usr/bin/env python3
"""Week stats: fetch, clean, aggregate. Usage: python3 weekly_stats_prep.py 2026-09-21 (week start, Monday, Beijing)."""
import json, time, urllib.request, urllib.parse, collections, sys
from datetime import datetime, timedelta, timezone

API_KEY = "66b1c1ad34af302bb1672147f78e9e90"
USER = "volatile-Quartz"
RULES = json.load(open("/workspace/scripts/lastfm_rules.json"))
TZ = timezone(timedelta(hours=8))

def ts_of(datestr):
    return int(datetime.strptime(datestr, "%Y-%m-%d").replace(tzinfo=TZ).timestamp())

if len(sys.argv) < 2:
    print("usage: weekly_stats_prep.py 2026-09-21   (week-start Monday, Beijing)")
    sys.exit(1)
START = sys.argv[1]
T0 = ts_of(START)
WEEK = (T0, T0 + 7 * 86400)
PREV = (T0 - 7 * 86400, T0)
week_label = "Week " + str((int(datetime.strptime(START, "%Y-%m-%d").isocalendar()[1])))
week_end = (datetime.fromtimestamp(T0, TZ) + timedelta(days=6)).strftime("%Y-%m-%d")

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
            ts = int(t["date"]["uts"])
            out.append({"ts": ts, "artist": t["artist"]["#text"], "track": t["name"]})
        total = int(data.get("recenttracks", {}).get("@attr", {}).get("totalPages", page))
        if page >= total:
            break
        page += 1
        time.sleep(1.0)
    return out

def clean(records):
    """Apply lastfm_rules: blacklist, alias, title cleaning. Returns list of dicts."""
    bl_artists = [a.lower() for a in RULES["blacklist_artists"]]
    fkw = [k.lower() for k in RULES["filter_keywords"]]
    bl_tracks = [t.split("|") for t in RULES["blacklist_tracks"]]
    alias = RULES["solo_alias"]
    res = []
    for r in records:
        a, t = r["artist"].strip(), r["track"].strip()
        al, tl = a.lower(), t.lower()
        if any(k in al for k in bl_artists):
            continue
        if any(k in al for k in fkw) or any(k in tl for k in fkw):
            continue
        if any(ba in a for ba in bl_artists) or any(ba in al for ba in bl_artists):
            continue
        hit = False
        for ba, bt in bl_tracks:
            if ba.lower() in al and bt.lower() in tl:
                hit = True
                break
        if hit:
            continue
        # title suffixes (strip if title starts with or ends with any suffix)
        for suf in RULES["title_suffix"]:
            s = suf.lower()
            if tl.startswith(s + " ") or tl.endswith(" " + s) or tl == s:
                t = t[:-len(s)].strip().rstrip(" -–()[]【】")
                tl = t.lower()
        # trailing parenthetical
        if RULES["extra_rules"].get("strip_trailing_parenthetical"):
            if tl.endswith(")") and "(" in t:
                t = t[:t.rfind("(")].strip()
        # artist alias
        a = alias.get(a, a)
        res.append({"ts": r["ts"], "artist": a, "title": t})
    return res

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
    wk_clean_all = clean(wk)          # keep duplicates for play counts
    pv_clean_all = clean(pv)
    wk_clean = dedup(wk_clean_all)     # unique tracks
    pv_clean = dedup(pv_clean_all)
    pv_keys = {(r["artist"].lower(), r["title"].lower()) for r in pv_clean}

    # daily trend (UTC ts -> Beijing date), unique tracks per day
    tz = 8 * 3600
    from datetime import datetime
    daily = collections.Counter()
    for r in wk_clean:
        d = datetime.fromtimestamp(r["ts"] + tz).strftime("%m-%d")
        daily[d] += 1

    # top artists / tracks by real play counts (pre-dedup)
    art_cnt = collections.Counter(r["artist"] for r in wk_clean_all)
    trk_cnt = collections.Counter((r["artist"], r["title"]) for r in wk_clean_all)

    # new vs repeated (prev week baseline)
    new_tracks = [r for r in wk_clean if (r["artist"].lower(), r["title"].lower()) not in pv_keys]
    rep_tracks = [r for r in wk_clean if (r["artist"].lower(), r["title"].lower()) in pv_keys]
    played_again = [{"artist": a, "title": t, "count": c} for (a, t), c in trk_cnt.items() if c >= 2]

    # prev week totals
    pv_art_cnt = collections.Counter(r["artist"] for r in pv_clean)
    new_artists = [a for a in art_cnt if a not in pv_art_cnt]

    stats = {
        "meta": {"week_label": week_label, "week_range": f"{START} ~ {week_end}"},
        "week": {"total_scrobbles": len(wk), "total_scrobbles_prev": len(pv)},
        "clean": {"tracks": len(wk_clean), "tracks_prev": len(pv_clean),
                  "artists": len(art_cnt), "artists_prev": len(pv_art_cnt)},
        "daily": dict(sorted(daily.items())),
        "top_artists": art_cnt.most_common(15),
        "top_tracks": trk_cnt.most_common(10),
        "new_tracks": len(new_tracks), "rep_tracks": len(rep_tracks),
        "played_again": played_again,
        "new_artists": new_artists,
        "prev_artists": list(pv_art_cnt.keys()),
        "full_counts": {f"{a}||{t}": c for (a, t), c in trk_cnt.items()},
    }
    # raw pairs for duration/tags lookup: (artist_clean, title_clean) -> (artist_raw, title_raw)
    lookup = {}
    for r in wk_clean:
        lookup.setdefault((r["artist"], r["title"]), r)
    stats["_lookup"] = {f"{a}||{t}": {"artist_raw": v["artist"], "title_raw": v["title"]}
                        for (a, t), v in lookup.items()}
    json.dump(stats, open("/tmp/lastfm_prep.json", "w"), ensure_ascii=False, indent=1)
    print(f"week raw={len(wk)} clean={len(wk_clean)} prev raw={len(pv)} clean={len(pv_clean)}", flush=True)
    print("daily:", dict(sorted(daily.items())), flush=True)
    print("top_artists:", art_cnt.most_common(15), flush=True)

if __name__ == "__main__":
    main()
