#!/usr/bin/env python3
"""Enrich weekly stats: per-track duration (seconds, with cache) + top-artist tags.
Usage: python3 weekly_stats_enrich.py   (reads /tmp/lastfm_prep.json)
时长口径：Last.fm duration 为毫秒（如 196000）；此处归一为秒：
  d >= 60000 视为毫秒 → d//1000；30 <= d <= 3600 视为秒；其余视为坏值 → 0（走插值）。
缓存：默认 /tmp/lastfm_dur_cache.json，可传参覆盖（全局缓存，跨周复用）。
"""
import json, time, urllib.request, urllib.parse, os, sys

API_KEY = "66b1c1ad34af302bb1672147f78e9e90"
CACHE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/lastfm_dur_cache.json"
prep = json.load(open("/tmp/lastfm_prep.json"))

def api(params, retries=3):
    q = urllib.parse.urlencode({**params, "api_key": API_KEY, "format": "json"})
    url = "http://ws.audioscrobbler.com/2.0/?" + q
    for attempt in range(retries):
        try:
            return json.load(urllib.request.urlopen(url, timeout=30))
        except Exception:
            time.sleep(2.0 * (attempt + 1))
    return {}

def norm_duration(d):
    try:
        d = int(d)
    except Exception:
        return 0
    if d >= 60000:          # 毫秒
        d //= 1000
    if 30 <= d <= 3600:     # 秒，且长度合理
        return d
    return 0                 # 0 / 占位坏值

def get_duration(artist, track):
    """Try as-is, then fallback to first name when artist string is a collab (feat./&)."""
    attempts = [artist]
    for sep in (" feat. ", " & ", ", ", "/"):
        if sep in artist:
            attempts.append(artist.split(sep)[0].strip())
            break
    for a in dict.fromkeys(attempts):
        d = api({"method": "track.getInfo", "artist": a, "track": track, "autocorrect": 0})
        t = d.get("track", {})
        if isinstance(t, dict) and t.get("duration"):
            return norm_duration(t["duration"]), a != artist
    return 0, False

def get_tags(artist):
    d = api({"method": "artist.getTopTags", "artist": artist, "autocorrect": 0})
    return [x["name"] for x in d.get("toptags", {}).get("tag", [])[:8]]

cache = {}
if os.path.exists(CACHE):
    cache = json.load(open(CACHE))
    print("loaded cache:", len(cache), flush=True)

lookup = prep["_lookup"]
print("querying {} tracks...".format(len(lookup)), flush=True)
durations, fallback_hits = {}, 0
for i, (key, v) in enumerate(lookup.items(), 1):
    if key in cache:
        d = cache[key]
        if d:
            durations[key] = d
    else:
        dur, via_fallback = get_duration(v["artist_raw"], v["title_raw"])
        cache[key] = dur
        if dur:
            durations[key] = dur
            if via_fallback:
                fallback_hits += 1
    if i % 20 == 0:
        print("  {}/{}".format(i, len(lookup)), flush=True)
    time.sleep(1.1)

tags_by_artist = {}
for artist, _cnt in prep["top_artists"]:
    first = artist.split(" & ")[0].split(" feat. ")[0].strip()
    tags_by_artist[artist] = get_tags(first)
    time.sleep(1.1)

json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
json.dump({"durations": durations, "tags_by_artist": tags_by_artist, "fallback_hits": fallback_hits},
          open("/tmp/lastfm_enrich.json", "w"), ensure_ascii=False)
print("done. durations: {} (fallback {}), tags: {}, cache saved".format(
    len(durations), fallback_hits, len(tags_by_artist)), flush=True)
