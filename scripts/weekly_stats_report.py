#!/usr/bin/env python3
"""Generate weekly listening report: Markdown section + standalone HTML (inline SVG charts).
Reads /tmp/lastfm_prep.json + /tmp/lastfm_enrich.json. Usage: python3 weekly_stats_report.py"""
import json, collections, html

prep = json.load(open("/tmp/lastfm_prep.json"))
enr = json.load(open("/tmp/lastfm_enrich.json"))
durations, tags_by_artist = enr["durations"], enr["tags_by_artist"]
meta = prep["meta"]
label = meta["week_label"].replace(" ", "").lower()

def fmt_dur(sec):
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{sec % 3600 // 60:02d}:{s:02d}"

# ---- duration estimate with per-artist-mean interpolation ----
full_counts = prep["full_counts"]
direct, interpolated, artist_dur = 0, 0, collections.defaultdict(list)
for key, d in durations.items():
    direct += full_counts.get(key, 1)
    artist_dur[key.split("||")[0]].append(d)
total_sec = 0
for key, cnt in full_counts.items():
    d = durations.get(key)
    if not d:
        cand = artist_dur.get(key.split("||")[0], [])
        d = (sum(cand) / len(cand)) if cand else None
        if d:
            interpolated += cnt
    if d:
        total_sec += d * cnt / 1000   # Last.fm duration is in milliseconds

# ---- daily ----
daily = prep["daily"]
days = sorted(daily)

# ---- genres: top artists count x tags ----
tag_cnt = collections.Counter()
for artist, cnt in prep["top_artists"]:
    for t in tags_by_artist.get(artist, []):
        t = "female vocalists" if t.lower() == "female vocalist" else t.lower()
        tag_cnt[t] += cnt
top_tags = [t for t, c in tag_cnt.most_common(12) if t]

# ---- new vs repeated ----
pct_new = prep["new_tracks"] / max(1, prep["clean"]["tracks"]) * 100

# ---- compare prev week ----
scrob = prep["week"]
diff_pct = (scrob["total_scrobbles"] - scrob["total_scrobbles_prev"]) / max(1, scrob["total_scrobbles_prev"]) * 100

json.dump({"total_sec": total_sec, "direct": direct, "interpolated": interpolated,
           "top_tags": top_tags, "pct_new": pct_new, "diff_pct": diff_pct},
          open("/tmp/lastfm_report.json", "w"), ensure_ascii=False, indent=1)

print(f"{label}: total={fmt_dur(total_sec)} direct={direct} interpolated={interpolated}")

# ================= Markdown section =================
md = []
md.append(f"## 📊 本周概览（{meta['week_label']}，{meta['week_range']}）")
md.append("")
md.append(f"- **播放量**：本周有效记录 **{scrob['total_scrobbles']} 次**（日均 {scrob['total_scrobbles']/max(1,len(days)):.0f} 次），独立曲目 **{prep['clean']['tracks']} 首**，独立歌手 **{prep['clean']['artists']} 组**")
dur_note = f"（直接查到 {direct} 次播放的时长，其余 {interpolated} 按同歌手均值插值）"
md.append(f"- **累计时长**：约 **{fmt_dur(total_sec)}**{dur_note}")
md.append(f"- **最猛一天**：{max(daily, key=daily.get)}（{daily[max(daily, key=daily.get)]} 首）· 最冷清：{min(daily, key=daily.get)}（{daily[min(daily, key=daily.get)]} 首）")
md.append(f"- **Top 歌手**：{', '.join(f'{a}（{c}）' for a, c in prep['top_artists'][:5])}")
if prep["played_again"]:
    md.append(f"- **反复播放**：{len(prep['played_again'])} 首歌本周 ≥2 次（{'、'.join(f'{a}《{t}》×{c}' for x in prep['played_again'][:3] for a, t, c in [x.values()])}）")
md.append(f"- **新歌 vs 复听**：相比上周新听 **{prep['new_tracks']} 首（{pct_new:.0f}%）**，上周也听过的 {prep['rep_tracks']} 首（基线：上周有效记录仅 {prep['clean']['tracks_prev']} 首）；新面孔歌手 {len(prep['new_artists'])} 组")
md.append(f"- **风格分布**：{' / '.join(top_tags[:6])}")
md.append(f"- **对比上周**：总播放 {scrob['total_scrobbles']} vs {scrob['total_scrobbles_prev']}（{diff_pct:+.0f}%）")
md.append("")
open(f"/workspace/{label}_overview.md", "w").write("\n".join(md))

# ================= HTML report =================
def svg_bars(items, w=640, h=260):
    n = len(items)
    bw = w / n
    mx = max(v for _, v in items) or 1
    out = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" style="width:100%%;height:auto;font-family:system-ui">' % (w, h + 34)]
    for i, (lb, v) in enumerate(items):
        bh = (v / mx) * (h - 40)
        x = i * bw + bw * 0.18
        out.append(f'<rect x="{x:.1f}" y="{h - bh:.1f}" width="{bw * 0.64:.1f}" height="{bh:.1f}" rx="4" fill="#7c5cbf"/>')
        out.append(f'<text x="{x + bw * 0.32:.1f}" y="{h - bh - 6:.1f}" font-size="13" text-anchor="middle" fill="#333">{v}</text>')
        out.append(f'<text x="{x + bw * 0.32:.1f}" y="{h + 18:.1f}" font-size="12" text-anchor="middle" fill="#666">{html.escape(str(lb))}</text>')
    out.append("</svg>")
    return "\n".join(out)

def svg_hbars(items, w=640):
    n = len(items)
    rh = 26
    mx = max(v for _, v in items) or 1
    out = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" style="width:100%%;height:auto;font-family:system-ui">' % (w, n * rh + 34)]
    for i, (lb, v) in enumerate(items):
        y = 34 + i * rh
        bw = (v / mx) * (w - 190)
        out.append(f'<text x="6" y="{y + 16:.1f}" font-size="13" fill="#333">{html.escape(str(lb))}</text>')
        out.append(f'<rect x="190" y="{y + 5:.1f}" width="{bw:.1f}" height="18" rx="4" fill="#4a90d9"/>')
        out.append(f'<text x="{196 + bw:.1f}" y="{y + 19:.1f}" font-size="12" fill="#555">{v}</text>')
    out.append("</svg>")
    return "\n".join(out)

daily_items = [(d, daily[d]) for d in days]
art_items = [(a, c) for a, c in prep["top_artists"][:8]]
tag_items = [(t, c) for t, c in tag_cnt.most_common(8)]

cards = [
    ("本周播放", f"{scrob['total_scrobbles']} 次", "有效记录，日均 {:.0f} 次".format(scrob['total_scrobbles'] / max(1, len(days)))),
    ("独立曲目", f"{prep['clean']['tracks']} 首", f"{prep['clean']['artists']} 组独立歌手"),
    ("累计时长", fmt_dur(total_sec), f"直接 {direct} + 插值 {interpolated}"),
    ("新歌占比", f"{pct_new:.0f}%", f"相比上周新听 {prep['new_tracks']} 首"),
]

repeated_html = ('<br>'.join(f'<b>{html.escape(a)}</b>《{html.escape(t)}》× {c}'
                             for x in prep['played_again'][:10] for a, t, c in [x.values()]) or '无')

body = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(meta['week_label'])} 听歌周报 · {html.escape(meta['week_range'])}</title>
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
<h1>{html.escape(meta['week_label'])} · 听歌周报</h1>
<p class="sub">{html.escape(meta['week_range'])} · Last.fm @volatile-Quartz</p>
<div class="cards">
  {''.join(f'<div class="card"><div class="v">{v}</div><div class="l">{l}</div><div style="font-size:12px;color:#aaa">{d}</div></div>' for v, l, d in [(c[1], c[0], c[2]) for c in cards])}
</div>
<div class="panel"><h2>每日播放趋势</h2>{svg_bars(daily_items)}</div>
<div class="panel"><h2>Top 歌手（按播放次数）</h2>{svg_hbars(art_items)}</div>
<div class="panel"><h2>风格分布（歌手标签聚合）</h2>{svg_hbars(tag_items)}</div>
<div class="panel"><h2>反复播放 Top（本周 ≥2 次）</h2>
<p style="font-size:14px;line-height:1.8">{repeated_html}</p></div>
<p class="foot">数据来源 Last.fm API · 清洗规则 lastfm_rules.json · 时长为曲目时长估算（缺失按同歌手均值插值）</p>
</div></body></html>
"""
open(f"/workspace/{label}_report.html", "w").write(body)
print(f"wrote /workspace/{label}_overview.md and /workspace/{label}_report.html")
