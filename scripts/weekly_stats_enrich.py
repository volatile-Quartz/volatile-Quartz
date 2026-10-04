#!/usr/bin/env python3
"""Enrich weekly stats: per-track duration (with fallback matching) + top-artist tags.
Usage: python3 weekly_stats_enrich.py   (reads /tmp/lastfm_prep.json)"""
import json, time, urllib.request, urllib.parse, collections

API_KEY = "66b1c1ad34af302bb1672147f78e9e90"
prep = json.load(open("/tmp/lastfm_prep.json"))

def api(params):
    q = urllib.parse.urlencode({**params, "api_key": API_KEY, "format": "json"})
    url = "http://ws.audioscrobbler.com/2.0/?" + q
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(url, timeout=30))
        except Exception:
            time.sleep(2.0)
    return {}

def get_duration(artist, track):
    """Try as-is, then fallback to first name when artist string is a collab (feat./&)."""
    attempts = [artist]
    for sep in (" feat. ", " & ", ", ", "/"):
        if sep in artist:
            attempts.append(artist.split(sep)[0].strip())
            break
    for a in dict.fromkeys(attempts):
        d = api({"method": "track.getinfo", "artist": a, "track": track})
        t = d.get("track", {})
        if isinstance(t, dict) and t.get("duration"):
            return int(t["duration"]), a != artist
    return 0, False

def get_tags(artist):
    d = api({"method": "artist.getinfo", "artist": artist})
    a = d.get("artist", {})
    if not isinstance(a, dict):
        return []
    return [x["name"] for x in a.get("tags", {}).get("tag", [])[:5]]

lookup = prep["_lookup"]
print(f"querying {len(lookup)} tracks...", flush=True)
durations, fallback_hits = {}, 0
for i, (key, v) in enumerate(lookup.items(), 1):
    dur, via_fallback = get_duration(v["artist_raw"], v["title_raw"])
    if dur:
        durations[key] = dur
        if via_fallback:
            fallback_hits += 1
    if i % 20 == 0:
        print(f"  {i}/{len(lookup)}", flush=True)
    time.sleep(1.1)

tags_by_artist = {}
for artist, _cnt in prep["top_artists"]:
    first = artist.split(" & ")[0].split(" feat. ")[0].strip()
    tags_by_artist[artist] = get_tags(first)
    time.sleep(1.1)

json.dump({"durations": durations, "tags_by_artist": tags_by_artist, "fallback_hits": fallback_hits},
          open("/tmp/lastfm_enrich.json", "w"), ensure_ascii=False)
print(f"done. durations: {len(durations)} (fallback {fallback_hits}), tags: {len(tags_by_artist)}", flush=True)
