#!/usr/bin/env python3
"""Generate weekly listening stats (markdown block, ready for GitHub issue) + HTML report.
Reads /tmp/lastfm_prep.json + /tmp/lastfm_enrich.json + lastfm_rules.json (style rules).
Usage: python3 weekly_stats_report.py
输出口径：有效记录=清洗后播放次数；每日=独立曲目/日；风格=宽松清洗（去语言/描述标签+合并变体）后生成图片词云；插值单位=次。

"""
import json, collections, html, os, re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(BASE_DIR, "lastfm_rules.json")))
STYLE_DROP = set(RULES.get("style_drop_tags", []))
MERGES = RULES.get("style_tag_merges", {})
# 白名单来源：genre_tree.json（树状结构，扁平化叶子）；缺文件则回退 rules 白名单
GENRE_WL = set()
_tree_path = os.path.join(BASE_DIR, "genre_tree.json")
if os.path.exists(_tree_path):
    def _flat(o, skip_prefix="_"):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.startswith(skip_prefix):
                    continue
                _flat(v)
        elif isinstance(o, list):
            for x in o:
                if isinstance(x, str):
                    GENRE_WL.add(x)
                else:
                    _flat(x)
    _flat(json.load(open(_tree_path)))
else:
    GENRE_WL = set()   # genre_tree.json 为唯一真源，缺失时用空集（不放行任何 tag）

def _validate_genre_tree():
    """启动时做一致性校验，发现问题只 warning 不 crash（不影响运行）。"""
    from collections import Counter
    tree_raw = json.load(open(_tree_path)) if os.path.exists(_tree_path) else {}
    def _raw_flat(o):
        r = []
        if isinstance(o, dict):
            for v in o.values(): r.extend(_raw_flat(v))
        elif isinstance(o, list):
            for x in o: r.extend(_raw_flat(x))
        elif isinstance(o, str):
            r.append(o)
        return r
    all_strings = _raw_flat(tree_raw)
    dup = [t for t, c in Counter(all_strings).items() if c > 1]
    if dup:
        print(f"⚠️ genre_tree 有重复叶子: {dup}", flush=True)
    bad = GENRE_WL & STYLE_DROP
    if bad:
        print(f"⚠️ tree 叶子被 drop 误删: {bad}", flush=True)
    bad_merges = [(k, v) for k, v in MERGES.items()
                  if v not in GENRE_WL and v not in STYLE_DROP]
    if bad_merges:
        print(f"⚠️ merge 产物既不在 tree 也不在 drop: {bad_merges}", flush=True)
    print(f"✅ genre_tree 加载完成：{len(GENRE_WL)} 个叶子")
    if not dup and not bad and not bad_merges:
        print("✅ 校验通过 — 无重复叶子 / 无 drop 冲突 / 无孤儿 merge")
_validate_genre_tree()

prep = json.load(open("/tmp/lastfm_prep.json"))
enr = json.load(open("/tmp/lastfm_enrich.json"))
durations, tags_by_artist = enr["durations"], enr["tags_by_artist"]
meta = prep["meta"]
# 文件名带年份前缀，避免跨年混淆（如 2026week39_report.html）
label = meta["week_range"].split(" ~ ")[0][:4] + meta["week_label"].replace(" ", "").lower()
clean = prep["clean"]

def fmt_dur(sec):
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    if h:
        return "{}:{:02d}:{:02d}".format(h, m, s)
    return "{}:{:02d}".format(m, s)

UNKNOWN_GENRES = collections.Counter()   # 不在白名单也不在 drop 的 tag，用于每周告警

def canon(t):
    """风格标签清洗：合并变体 → 黑名单剔除 → 白名单强校验。
    不在白名单也不在 drop 的 tag 会累积到 UNKNOWN_GENRES，供每周告警用户审阅是否纳入 tree。
    """
    t2 = MERGES.get(t, t)
    if t2 in STYLE_DROP or not t2 or len(t2) > 30:
        return None
    if t2 not in GENRE_WL:
        UNKNOWN_GENRES[t2] += 1
        return None
    return t2

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

# ---- 风格：Top 歌手标签 × 播放次数，宽松清洗（去语言/描述标签 + 合并变体）----
tag_cnt = collections.Counter()
for artist, cnt in prep["top_artists"]:
    for t in tags_by_artist.get(artist, []):
        c = canon(t.lower())
        if c:
            tag_cnt[c] += cnt
genres = [t for t, c in tag_cnt.most_common(30)]
genres_set = set(genres)
style_str = " / ".join(genres[:6])

# ---- 曲风对比：自动找上周 artifacts 里的 genres ----
# prev_label_from label: "2026week40" -> "2026week39"
def prev_label_from(lb):
    m = re.match(r"(\d{4})week(\d+)", lb)
    if not m: return ""
    year, wk = int(m.group(1)), int(m.group(2))
    pw, py = wk - 1, year
    if pw < 1: pw, py = 53, year - 1
    return f"{py}week{pw}"
prev_genres_set = set()
prev_path_candidates = [
    os.path.join(BASE_DIR, "artifacts", prev_label_from(label), "04_report.json"),
    os.path.join("/workspace/lastfm/artifacts", prev_label_from(label), "04_report.json"),
]
for p in prev_path_candidates:
    if os.path.exists(p):
        try:
            prev_report = json.load(open(p))
            prev_genres_set = set(prev_report.get("all_tags", prev_report.get("top_tags", [])))
            break
        except Exception:
            pass
genres_new = sorted(genres_set - prev_genres_set)   # 本周新增
genres_gone = sorted(prev_genres_set - genres_set)   # 本周消失

# ---- unknown genres 告警：不在白名单也不在 drop 的 tag，提示用户审阅 ----
unknown_note = ""
if UNKNOWN_GENRES:
    unk_lines = ["  {}（×{}）".format(t, c) for t, c in UNKNOWN_GENRES.most_common()]
    unknown_note = "\n⚠️ 未识别风格（不在 genre_tree 也不在 drop_tags）：\n" + "\n".join(unk_lines)
    print(unknown_note, flush=True)

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
if prev_genres_set:
    diff_parts = []
    if genres_new: diff_parts.append("+{} 新增（{}）".format(len(genres_new), "、".join(genres_new[:5])))
    if genres_gone: diff_parts.append("-{} 消失（{}）".format(len(genres_gone), "、".join(genres_gone[:5])))
    diff_str = "；" + "；".join(diff_parts) if diff_parts else "；与上周持平"
else:
    diff_str = ""
md.append("- 曲风数量：{} 种{}".format(len(genres_set), diff_str))
md.append("- 新歌占比：{}%（新听 {} 首，上周也听过的 {} 首）；新面孔歌手 {} 组".format(
    round(pct_new), prep["new_tracks"], prep["rep_tracks"], len(prep["new_artists"])))
md.append("- 风格分布（Top {}）：{}".format(min(8, len(genres)), style_str))
rep_items = sorted([(k, v) for k, v in prep["full_counts"].items() if v >= 2],
                   key=lambda x: -x[1])[:8]
if rep_items:
    rep_str = "、".join("《{}》—{}（{}×）".format(
        k.partition("||")[2], k.partition("||")[0], v) for k, v in rep_items)
    md.append("- 重复播放：{}".format(rep_str))
if UNKNOWN_GENRES:
    md.append("- ⚠️ 未识别风格（需审阅是否纳入 tree 或 drop）：{}".format(
        "、".join("{}×{}".format(t, c) for t, c in UNKNOWN_GENRES.most_common(10))))
md.append("- 对比上周：总播放 {} vs {}（{}{}%）".format(
    plays, clean["plays_prev"], "+" if diff_pct >= 0 else "-", abs(round(diff_pct))))

json.dump({"total_sec": total_sec, "direct": direct, "interpolated": interpolated,
           "all_tags": genres, "genres_count": len(genres_set),
           "new_genres": genres_new, "gone_genres": genres_gone,
           "pct_new": pct_new, "diff_pct": diff_pct,
           "tracks": clean["tracks"], "artists": clean["artists"]},
          open("/tmp/lastfm_report.json", "w"), ensure_ascii=False, indent=1)

print("\n".join(md))
out_dir = os.path.join(BASE_DIR, "artifacts", label)
open(os.path.join(out_dir, "05_{}.md".format(label)), "w").write("\n".join(md) + "\n")

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
    fc = rh / 2       # 每行的垂直中心线（从行起点起算）
    out = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" style="width:100%%;height:auto;font-family:system-ui">' % (w, n * rh + 34)]
    for i, (lb, v) in enumerate(items):
        y = 34 + i * rh; bw = (v / mx) * (w - 190)
        # rect 中心对齐 fc → rect y 偏移 = fc - rect_h/2 = 13 - 9 = 4
        out.append('<text x="6" y="{:.1f}" font-size="13" fill="#333">{}</text>'.format(y + fc + 4, html.escape(str(lb))))
        out.append('<rect x="190" y="{:.1f}" width="{:.1f}" height="18" rx="4" fill="#4a90d9"/>'.format(y + fc - 9, bw))
        if bw > 44:   # 长条时数字写在条内（白字），避免顶格被裁掉
            out.append('<text x="{:.1f}" y="{:.1f}" font-size="12" text-anchor="end" fill="#fff">{}</text>'.format(190 + bw - 6, y + fc + 4, v))
        else:
            out.append('<text x="{:.1f}" y="{:.1f}" font-size="12" fill="#555">{}</text>'.format(196 + bw, y + fc + 4, v))
    out.append("</svg>")
    return "\n".join(out)

daily_items = [(d, daily[d]) for d in days]
art_items = [(a, c) for a, c in prep["top_artists"][:8]]
tag_items = [(t, c) for t, c in tag_cnt.most_common(8)]


# ---- 曲风变化 HTML ----
if prev_genres_set:
    parts = []
    if genres_new:
        parts.append('<span style="color:#2a9d8f;font-weight:600">+{} 新增：{}</span>'.format(
            len(genres_new), "、".join(html.escape(g) for g in genres_new)))
    if genres_gone:
        parts.append('<span style="color:#e76f51;font-weight:600">-{} 消失：{}</span>'.format(
            len(genres_gone), "、".join(html.escape(g) for g in genres_gone)))
    if not parts:
        parts.append('<span style="color:#888">与上周持平，曲风无变化</span>')
    genre_change_html = "<br>".join(parts)
else:
    genre_change_html = '<span style="color:#aaa">缺少上周对比数据（首次运行？）</span>'

# 标题带年份（如 2026 week 39 听歌周报），last.fm 首字母小写
title_txt = "{} {} 听歌周报".format(meta["week_range"].split(" ~ ")[0][:4], meta["week_label"].lower())

body = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{} · {}</title>
<style>
 body{{margin:0;background:#f4f2f8;color:#222;font-family:system-ui,-apple-system,sans-serif}}
 .wrap{{max-width:760px;margin:0 auto;padding:24px 20px 60px}}
 h1{{font-size:26px;margin:8px 0 2px}} .sub{{color:#777;margin:0 0 20px}}
 .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
 .card{{background:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .card .v{{font-size:26px;font-weight:700;color:#5b3d9e}} .card .l{{font-size:13px;color:#888}}
 .panel{{background:#fff;border-radius:12px;padding:16px 18px;margin-top:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .panel h2{{margin:0 0 10px;font-size:17px}}
 .foot{{color:#aaa;font-size:12px;margin-top:20px;text-align:center}}
</style></head><body><div class="wrap">
<h1>{}</h1>
<p class="sub">{} · last.fm @volatile-Quartz</p>
<div class="cards">
  {cards}
</div>
<div class="panel"><h2>每日播放趋势（播放次数/日）</h2>{bars}</div>
<div class="panel"><h2>Top 歌手（按播放次数）</h2>{hbars}</div>
<div class="panel"><h2>曲风分布（按播放次数）</h2>{tags}</div>
<div class="panel"><h2>曲风变化</h2>
<p style="font-size:14px;line-height:1.8">{genre_change}</p></div>
<p class="foot">数据来源 last.fm API · 清洗规则 lastfm_rules.json · 时长为曲目时长估算（缺失按同歌手均值插值）</p>
</div></body></html>
""".format(
    html.escape(title_txt), html.escape(meta["week_range"]),
    html.escape(title_txt), html.escape(meta["week_range"]),
    cards="".join('<div class="card"><div class="v">{}</div><div class="l">{}</div><div style="font-size:12px;color:#aaa">{}</div></div>'.format(v, l, d)
                  for v, l, d in [
                      ("{} 次".format(plays), "本周播放", "有效记录，日均 {:.0f} 次".format(plays / 7)),
                      ("{} 首".format(clean["tracks"]), "独立曲目", ""),
                      ("{} 组".format(clean["artists"]), "独立歌手", ""),
                      ("{} 种".format(len(genres_set)), "曲风数量",
                       "+{} 新增 -{} 消失".format(len(genres_new), len(genres_gone)) if prev_genres_set else ""),
                      (fmt_dur(total_sec), "累计时长", "直接 {} + 插值 {}".format(direct, interpolated)),
                      ("{:.0f}%".format(pct_new), "新歌占比", "相比上周新听 {} 首".format(prep["new_tracks"]))]),
    bars=svg_bars(daily_items), hbars=svg_hbars(art_items),
    tags=svg_hbars(tag_items), genre_change=genre_change_html)
open(os.path.join(out_dir, "06_{}_report.html".format(label)), "w").write(body)
print("wrote artifacts/{}/05_.md + 06_ report.html".format(label))
