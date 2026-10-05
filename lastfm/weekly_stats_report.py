#!/usr/bin/env python3
"""Generate weekly listening stats (markdown block, ready for GitHub issue) + HTML report.
Reads /tmp/lastfm_prep.json + /tmp/lastfm_enrich.json + lastfm_rules.json (style whitelist).
Usage: python3 weekly_stats_report.py
输出口径：有效记录=清洗后播放次数；每日=独立曲目/日；风格=曲风白名单过滤；插值单位=次。
"""
import json, collections, html, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(BASE_DIR, "lastfm_rules.json")))
GENRE = set(RULES.get("style_genre_whitelist", []))
MERGES = RULES.get("style_tag_merges", {})

prep = json.load(open("/tmp/lastfm_prep.json"))
enr = json.load(open("/tmp/lastfm_enrich.json"))
durations, tags_by_artist = enr["durations"], enr["tags_by_artist"]
meta = prep["meta"]
label = meta["week_label"].replace(" ", "").lower()
clean = prep["clean"]

def fmt_dur(sec):
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    if h:
        return "{}:{:02d}:{:02d}".format(h, m, s)
    return "{}:{:02d}".format(m, s)

def canon(t):
    return MERGES.get(t, t)

# ---- 时长估算：直接查到 + 同歌手均值插值（无则取全周均值），单位：次播放 ----
full_counts = prep["full_counts"]
direct, interpolated, artist_dur = 0, 0, collections.defaultdict(list)
for key, d in durations.items():
    direct += full_counts.get(key, 1)
    artist_dur[key.split("||")[0]].append(d)
known = [d for d in durations.values() if d]
global_mean = (sum(known) / len(known)) if known else None
total_sec = 0
for key, cnt in full_counts.items():
    d = durations.get(key)
    if not d:
        cand = artist_dur.get(key.split("||")[0], [])
        d = (sum(cand) / len(cand)) if cand else global_mean
        if d:
            interpolated += cnt
    if d:
        total_sec += d * cnt

# ---- 每日（独立曲目/日）----
daily = prep["daily"]
days = sorted(daily)

# ---- 风格：Top 歌手标签 × 播放次数，曲风白名单过滤 ----
tag_cnt = collections.Counter()
for artist, cnt in prep["top_artists"]:
    for t in tags_by_artist.get(artist, []):
        tag_cnt[canon(t.lower())] += cnt
genres = [t for t, c in tag_cnt.most_common(30) if t in GENRE]
style_str = " / ".join(genres[:6])

# ---- 新歌 / 复听 ----
pct_new = prep["new_tracks"] / max(1, clean["tracks"]) * 100

# ---- 对比上周（清洗后口径）----
diff_pct = (clean["plays"] - clean["plays_prev"]) / max(1, clean["plays_prev"]) * 100

# ---- Markdown 块（与 issue 既有格式一致，纯文本行）----
plays = clean["plays"]
md = []
md.append("- 播放量：有效记录 {} 次（日均 {} 次），独立曲目 {} 首，独立歌手 {} 组".format(
    plays, round(plays / 7), clean["tracks"], clean["artists"]))
dur_note = "（直接查到 {} 次播放的时长，其余 {} 次按同歌手均值插值）".format(direct, interpolated)
md.append("- 累计时长：约 {}{}".format(fmt_dur(total_sec), dur_note))
md.append("- 最猛一天：{}（{} 首）· 最冷清：{}（{} 首）".format(
    max(daily, key=daily.get), daily[max(daily, key=daily.get)],
    min(daily, key=daily.get), daily[min(daily, key=daily.get)]))
md.append("- Top 歌手：{}".format("、".join("{}（{}）".format(a, c) for a, c in prep["top_artists"][:5])))
if prep["played_again"]:
    x = prep["played_again"][0]
    suffix = " 等" if len(prep["played_again"]) > 1 else ""
    md.append("- 反复播放：{} 首歌本周 ≥2 次（{}《{}》×{}{}）".format(
        len(prep["played_again"]), x["artist"], x["title"], x["count"], suffix))
else:
    md.append("- 反复播放：无")
md.append("- 新歌占比：{}%（新听 {} 首，上周也听过的 {} 首）；新面孔歌手 {} 组".format(
    round(pct_new), prep["new_tracks"], prep["rep_tracks"], len(prep["new_artists"])))
md.append("- 风格分布：{}".format(style_str))
md.append("- 对比上周：总播放 {} vs {}（{}{}%）".format(
    plays, clean["plays_prev"], "+" if diff_pct >= 0 else "-", abs(round(diff_pct))))

json.dump({"total_sec": total_sec, "direct": direct, "interpolated": interpolated,
           "top_tags": genres[:6], "pct_new": pct_new, "diff_pct": diff_pct},
          open("/tmp/lastfm_report.json", "w"), ensure_ascii=False, indent=1)

print("\n".join(md))
open("/workspace/{}.md".format(label), "w").write("\n".join(md) + "\n")

# ---- HTML 报告 ----
def svg_bars(items, w=640, h=260):
    n = len(items); bw = w / n; mx = max(v for _, v in items) or 1
    out = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" style="width:100%%;height:auto;font-family:system-ui">' % (w, h + 34)]
    for i, (lb, v) in enumerate(items):
        bh = (v / mx) * (h - 40); x = i * bw + bw * 0.18
        out.append('<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" rx="4" fill="#7c5cbf"/>'.format(x, h - bh, bw * 0.64, bh))
        out.append('<text x="{:.1f}" y="{:.1f}" font-size="13" text-anchor="middle" fill="#333">{}</text>'.format(x + bw * 0.32, h - bh - 6, v))
        out.append('<text x="{:.1f}" y="{:.1f}" font-size="12" text-anchor="middle" fill="#666">{}</text>'.format(x + bw * 0.32, h + 18, html.escape(str(lb))))
    out.append("</svg>")
    return "\n".join(out)

def svg_hbars(items, w=640):
    n = len(items); rh = 26; mx = max(v for _, v in items) or 1
    out = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" style="width:100%%;height:auto;font-family:system-ui">' % (w, n * rh + 34)]
    for i, (lb, v) in enumerate(items):
        y = 34 + i * rh; bw = (v / mx) * (w - 190)
        out.append('<text x="6" y="{:.1f}" font-size="13" fill="#333">{}</text>'.format(y + 16, html.escape(str(lb))))
        out.append('<rect x="190" y="{:.1f}" width="{:.1f}" height="18" rx="4" fill="#4a90d9"/>'.format(y + 5, bw))
        out.append('<text x="{:.1f}" y="{:.1f}" font-size="12" fill="#555">{}</text>'.format(196 + bw, y + 19, v))
    out.append("</svg>")
    return "\n".join(out)

daily_items = [(d, daily[d]) for d in days]
art_items = [(a, c) for a, c in prep["top_artists"][:8]]
tag_items = [(t, c) for t, c in tag_cnt.most_common(8) if t in GENRE][:8]
repeat_html = ("<br>".join("<b>{}</b>《{}》× {}".format(html.escape(a), html.escape(t), c)
                           for x in prep["played_again"][:10] for a, t, c in [x.values()]) or "无")

body = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{} · 听歌周报 · {}</title>
<style>
 body{{margin:0;background:#f4f2f8;color:#222;font-family:system-ui,-apple-system,sans-serif}}
 .wrap{{max-width:760px;margin:0 auto;padding:24px 20px 60px}}
 h1{{font-size:26px;margin:8px 0 2px}} .sub{{color:#777;margin:0 0 20px}}
 .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}}
 .card{{background:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .card .v{{font-size:26px;font-weight:700;color:#5b3d9e}} .card .l{{font-size:13px;color:#888}}
 .panel{{background:#fff;border-radius:12px;padding:16px 18px;margin-top:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .panel h2{{margin:0 0 10px;font-size:17px}}
 .foot{{color:#aaa;font-size:12px;margin-top:20px;text-align:center}}
</style></head><body><div class="wrap">
<h1>{} · 听歌周报</h1>
<p class="sub">{} · Last.fm @volatile-Quartz</p>
<div class="cards">
  {cards}
</div>
<div class="panel"><h2>每日播放趋势（独立曲目/日）</h2>{bars}</div>
<div class="panel"><h2>Top 歌手（按播放次数）</h2>{hbars}</div>
<div class="panel"><h2>风格分布（歌手标签×曲风白名单）</h2>{tags}</div>
<div class="panel"><h2>反复播放 Top（本周 ≥2 次）</h2>
<p style="font-size:14px;line-height:1.8">{repeats}</p></div>
<p class="foot">数据来源 Last.fm API · 清洗规则 lastfm_rules.json · 时长为曲目时长估算（缺失按同歌手均值插值）</p>
</div></body></html>
""".format(
    html.escape(meta["week_label"]), html.escape(meta["week_range"]),
    html.escape(meta["week_label"]), html.escape(meta["week_range"]),
    cards="".join('<div class="card"><div class="v">{}</div><div class="l">{}</div><div style="font-size:12px;color:#aaa">{}</div></div>'.format(v, l, d)
                  for v, l, d in [
                      ("{} 次".format(plays), "本周播放", "有效记录，日均 {:.0f} 次".format(plays / 7)),
                      ("{} 首".format(clean["tracks"]), "独立曲目", "{} 组独立歌手".format(clean["artists"])),
                      (fmt_dur(total_sec), "累计时长", "直接 {} + 插值 {}".format(direct, interpolated)),
                      ("{:.0f}%".format(pct_new), "新歌占比", "相比上周新听 {} 首".format(prep["new_tracks"]))]),
    bars=svg_bars(daily_items), hbars=svg_hbars(art_items),
    tags=svg_hbars(tag_items), repeats=repeat_html)
open("/workspace/{}_report.html".format(label), "w").write(body)
print("wrote /workspace/{}.md and /workspace/{}_report.html".format(label, label))
