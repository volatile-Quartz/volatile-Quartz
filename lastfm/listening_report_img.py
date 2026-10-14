#!/usr/bin/env python3
"""Last.fm 周报展示图（新管线）。

黑名单剔除只发生在出图阶段：榜单条目命中黑名单则隐藏，由后面的条目前推补满；
底层数据（01_report.json / 00_raw.json）原样保留，总量数字保持 last.fm 原值不重算。
Usage: python3 lastfm/listening_report_img.py 2026-10-02
输出: lastfm/artifacts/report_<start>/02_report.png
依赖：pillow + CJK 字体（scripts/setup_sandbox.sh 一键安装）。
"""
import json, os, glob, sys, re
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(BASE_DIR, "lastfm_rules.json")))
BL = [b.casefold() for b in RULES["blacklist_artists"]]
BL_TRACKS = [(t.split("|")[0].casefold(), t.split("|")[1].casefold()) for t in RULES["blacklist_tracks"]]

# ── 曲风口径（与旧管线一致：genre_tree 白名单 + merges + drops） ──
MERGES = RULES.get("style_tag_merges", {})
STYLE_DROP = set(RULES.get("style_drop_tags", []))
GENRE_WL = set()
def _flat(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if not k.startswith("_"): _flat(v)
    elif isinstance(o, list):
        for x in o: _flat(x)
    elif isinstance(o, str):
        GENRE_WL.add(o)
_tree = os.path.join(BASE_DIR, "genre_tree.json")
if os.path.exists(_tree):
    _flat(json.load(open(_tree)))
def canon_genre(t):
    t2 = MERGES.get(t, t)
    if t2 in STYLE_DROP or not t2 or len(t2) > 30: return None
    return t2 if t2 in GENRE_WL else None

TOP_N = 10  # 每个榜单展示条数（剔除后前推补满的上限）

if len(sys.argv) < 2:
    print("usage: listening_report_img.py 2026-10-02")
    sys.exit(1)
START = sys.argv[1]
REP = json.load(open(os.path.join(BASE_DIR, "artifacts", "report_" + START, "01_report.json")))
meta = REP["meta"]
totals = REP.get("totals") or {}
clock = REP.get("clock") or {}
tags_current = REP.get("tags_current") or []
decades = REP.get("decades") or []
community = REP.get("community") or {}
discovery = REP.get("discovery") or {}
music_ratio = REP.get("music_ratio") or {}
api = REP.get("api") or {}

def hidden(artist, name=""):
    al = (artist or "").casefold()
    if any(b in al for b in BL):
        return True
    nl = (name or "").casefold()
    return any(ba in al and bt in nl for ba, bt in BL_TRACKS)

def merge_list(page_list, api_list, simple):
    """页面 Top5 优先 + API 深度补位（按 name 或 artist+name 去重）。"""
    out = [dict(e, src="page") for e in page_list]
    if simple:
        keys = {e["name"].casefold() for e in page_list}
        for e in api_list:
            k = e["name"].casefold()
            if k not in keys:
                out.append(dict(e, src="api")); keys.add(k)
    else:
        keys = {(e.get("artist", "").casefold(), e["name"].casefold()) for e in page_list}
        for e in api_list:
            k = (e.get("artist", "").casefold(), e["name"].casefold())
            if k not in keys:
                out.append(dict(e, src="api")); keys.add(k)
    return out

def visible(entries, simple):
    res = []
    for e in entries:
        if simple:
            if not hidden(e["name"]):
                res.append(e)
        else:
            if not hidden(e.get("artist"), e["name"]):
                res.append(e)
    return res

artists = visible(merge_list(REP.get("page_top_artists", []), api.get("top_artists", []), True), True)
tracks = visible(merge_list(REP.get("page_top_tracks", []), api.get("top_tracks", []), False), False)
albums = visible(merge_list(REP.get("page_top_albums", []), api.get("top_albums", []), False), False)
for _lst in (artists, tracks, albums):
    _lst.sort(key=lambda e: -e["scrobbles"])  # 稳定排序：页面条目同分居前，消除 API 补位倒挂
artists, tracks, albums = artists[:TOP_N], tracks[:TOP_N], albums[:TOP_N]

# 曲风（带当前周计数，白名单过滤）
genre_items = []
for e in tags_current:
    g = canon_genre(e["name"].lower())
    if g and e.get("count"):
        genre_items.append((g, e["count"]))
genre_items = sorted(genre_items, key=lambda x: -x[1])[:8]

# ── 字体 ──
def find_cjk_font():
    p = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    if os.path.exists(p): return p
    for pat in ["/usr/share/fonts/**/wqy*", "/usr/share/fonts/**/NotoSans*", "/usr/share/fonts/**/CJK*"]:
        for f in glob.glob(pat, recursive=True):
            if os.path.exists(f): return f
    raise RuntimeError("未找到 CJK 字体，请先跑 scripts/setup_sandbox.sh")
FONT = find_cjk_font()
def F(sz, bold=False):
    return ImageFont.truetype(FONT, sz)

# ── 色板 / 画布 ──
W = 760
BG, CARD, GRAY, DARK = "#f4f2f8", "#ffffff", "#8a8a8e", "#222222"
P1, P2 = "#7c5cbf", "#4a90d9"
GREEN, RED = "#2a9d8f", "#e76f51"
ORANGE, ROSE = "#e98a2b", "#d96383"
INNER_PAD, HBAR_BOTTOM_EXTRA = 10, 8
im = Image.new("RGB", (W, 5000), BG)
d = ImageDraw.Draw(im)
y = 30

def ellipsize(s, font, maxw):
    if d.textlength(s, font) <= maxw:
        return s
    while s and d.textlength(s + "…", font) > maxw:
        s = s[:-1]
    return s + "…"

def draw_panel(y0, title_txt, data_h, bottom_extra=0):
    x0, x1 = W // 2 - 360, W // 2 + 360
    title_h = 34
    total_h = title_h + INNER_PAD + data_h + INNER_PAD + bottom_extra
    panel_bottom = y0 + total_h
    d.rounded_rectangle([x0, y0 + 2, x1, panel_bottom], radius=14, fill=CARD)
    d.text((x0 + 18, y0 + 12), title_txt, font=F(17, True), fill=DARK)
    content_top = y0 + title_h + INNER_PAD
    return panel_bottom, content_top, x0 + 18, x1 - x0 - 36

def wrap_list(items, font, avail_w):
    lines, cur = [], ""
    for g in items:
        cand = (cur + "、" + g) if cur else g
        if d.textlength(cand, font) > avail_w and cur:
            lines.append(cur)
            cur = g
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines

# ══════════ 头部（日期范围，不写周数） ══════════
sy, sm, sd = meta["start"].split("-")
ey, em, ed = meta["end"].split("-")
TITLE = "{}.{}.{} – {}.{} 听歌周报".format(sy, sm, sd, em, ed)
SUB = "last.fm listening report · @{}".format(meta.get("username", "volatile-Quartz"))
d.text((W // 2, y + 14), TITLE, font=F(28, True), fill=DARK, anchor="ma")
d.text((W // 2, y + 56), SUB, font=F(14), fill=GRAY, anchor="ma")
y += 92

# ══════════ 总量卡（总数保留 last.fm 原值，不做剔除重算） ══════════
sc = totals.get("scrobbles") if totals.get("scrobbles") is not None else api.get("total_scrobbles")
cards = [
    ("总 Scrobbles", "{} 次".format(sc), totals.get("scrobbles_vs_prev") or ""),
    ("收听时长", totals.get("listening_time") or "—", totals.get("listening_time_vs_prev") or ""),
    ("日均", "{} /day".format(totals.get("per_day")) if totals.get("per_day") is not None else "—", totals.get("per_day_vs_prev") or ""),
    ("最活跃日", "{} 次".format(totals["most_active"]["count"]) if totals.get("most_active") else "—",
     totals["most_active"].get("date", "") if totals.get("most_active") else ""),
]
cw, ch, gap = (W - 80 - 12) // 2, 88, 12
for i, (l, v, s) in enumerate(cards):
    cx = 40 + (i % 2) * (cw + gap)
    cy = y + (i // 2) * (ch + gap)
    d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=14, fill=CARD)
    d.text((cx + 16, cy + 12), l, font=F(13), fill=GRAY)
    d.text((cx + 16, cy + 32), str(v), font=F(24, True), fill=P1)
    d.text((cx + 16, cy + 64), ellipsize(str(s), F(11), cw - 32), font=F(11), fill=GRAY)
y += 2 * (ch + gap) + 16

# ══════════ 每日播放趋势（Fri→Thu） ══════════
daily = REP.get("daily") or {}
if daily:
    start_dt = datetime.strptime(meta["start"], "%Y-%m-%d")
    days = list(daily.keys())            # Fri..Thu，与报告周顺序一致
    vals = [daily[k] for k in days]
    labels = [(start_dt + timedelta(days=i)).strftime("%m.%d") for i in range(len(days))]
    chart_h = 168
    bottom, ct, px, pw = draw_panel(y, "每日播放趋势（scrobbles/日）", chart_h)
    mx = max(vals) or 1
    bar_bottom_y = ct + chart_h - 22
    bar_max_h = (ct + chart_h - 22) - ct - 6
    bw = pw / len(days)
    for i, (v, lb) in enumerate(zip(vals, labels)):
        bh = (v / mx) * bar_max_h
        x0 = px + i * bw + bw * 0.18
        bar_top = bar_bottom_y - bh
        d.rounded_rectangle([x0, bar_top, x0 + bw * 0.64, bar_bottom_y], radius=4, fill=P1)
        d.text((x0 + bw * 0.32, bar_top - 6), str(v), font=F(13), fill=DARK, anchor="mm")
        d.text((x0 + bw * 0.32, ct + chart_h - 6), lb, font=F(12), fill=GRAY, anchor="mm")
    y = bottom + 12

# ══════════ Top 歌手（hbars） ══════════
RH = 26; FC = RH / 2
n = len(artists)
rows_h = max(n, 1) * RH
bottom, ct, px, pw = draw_panel(y, "Top 歌手（黑名单已隐藏，前推补满）", rows_h, bottom_extra=HBAR_BOTTOM_EXTRA)
mx = max((e["scrobbles"] for e in artists), default=1) or 1
if not artists:
    d.text((px, ct + 6), "无", font=F(14), fill=GRAY)
for i, e in enumerate(artists):
    rc = ct + FC + i * RH
    d.text((px, rc), ellipsize(e["name"], F(13), 186), font=F(13), fill=DARK, anchor="lm")
    bw = (e["scrobbles"] / mx) * (pw - 210)
    d.rounded_rectangle([px + 190, rc - 9, px + 190 + max(bw, 4), rc + 9], radius=6, fill=P2)
    txt = str(e["scrobbles"])
    if bw > d.textlength(txt, F(12)) + 12:
        d.text((px + 190 + max(bw, 4) - 6, rc), txt, font=F(12), fill="#ffffff", anchor="rm")
    else:
        d.text((px + 190 + max(bw, 4) + 8, rc), txt, font=F(12), fill="#555", anchor="lm")
y = bottom + 12

# ══════════ Top 曲目 / Top 专辑（行式） ══════════
def rows_panel(y0, title, entries):
    RH2 = 24
    rows_h = max(len(entries), 1) * RH2
    bottom, ct, px, pw = draw_panel(y0, title, rows_h)
    if not entries:
        d.text((px, ct + 4), "无", font=F(14), fill=GRAY)
    for i, e in enumerate(entries):
        rc = ct + RH2 / 2 + i * RH2
        artist = e.get("artist")
        label = "{}. {}".format(i + 1, e["name"]) + (" — {}".format(artist) if artist else "")
        d.text((px, rc), ellipsize(label, F(13), pw - 52), font=F(13), fill=DARK, anchor="lm")
        d.text((px + pw, rc), str(e["scrobbles"]), font=F(13, True), fill=P1, anchor="rm")
    return bottom

y = rows_panel(y, "Top 曲目", tracks) + 12
y = rows_panel(y, "Top 专辑", albums) + 12

# ══════════ 听歌时钟（24 小时柱状） ══════════
hours = clock.get("hours") or {}
if hours:
    vals = [hours.get(str(h), 0) for h in range(24)]
    busiest_h = None
    m = re.match(r"(\d{1,2})", str(clock.get("busiest_hour") or ""))
    if m:
        busiest_h = int(m.group(1))
    chart_h = 150
    bottom, ct, px, pw = draw_panel(y, "听歌时钟（scrobbles/小时）", chart_h)
    mx = max(vals) or 1
    bar_bottom_y = ct + chart_h - 20
    bar_max_h = (ct + chart_h - 20) - ct - 6
    bw = pw / 24
    for h, v in enumerate(vals):
        bh = (v / mx) * bar_max_h if v else 2
        x0 = px + h * bw + bw * 0.15
        color = P1 if h == busiest_h else P2
        d.rounded_rectangle([x0, bar_bottom_y - bh, x0 + bw * 0.7, bar_bottom_y], radius=2, fill=color)
        if h == busiest_h:
            d.text((x0 + bw * 0.35, bar_bottom_y - bh - 7), str(v), font=F(11, True), fill=DARK, anchor="mm")
    for h in (0, 6, 12, 18, 23):
        d.text((px + h * bw + bw * 0.35, ct + chart_h - 5), str(h), font=F(11), fill=GRAY, anchor="mm")
    y = bottom + 12

# ══════════ 听歌画像（数据值用彩色胶囊高亮） ══════════
f13, f11b = F(13), F(11, True)
BADGE_H, PIC_LINE_H = 20, 28

def seg_t(txt, color=DARK):
    return ("t", txt, color)

def seg_b(txt, color):
    return ("b", str(txt), color)

def seg_w(s):
    kind, txt, _ = s
    return d.textlength(txt, f13) if kind == "t" else d.textlength(txt, f11b) + 12

def flow_rows(segs, maxw, indent=0):
    rows, x, have = 1, 0, False
    for s in segs:
        w = seg_w(s)
        if have and x + w > maxw:
            rows += 1
            x = indent
        x += w
        have = True
    return rows

def draw_flow(yy, segs, maxw, indent=0):
    x, have = 0, False
    for s in segs:
        kind, txt, color = s
        w = seg_w(s)
        if have and x + w > maxw:
            yy += PIC_LINE_H
            x = indent
        if kind == "t":
            d.text((px + x, yy), txt, font=f13, fill=color, anchor="lm")
            x += w
        else:
            d.rounded_rectangle([px + x, yy - BADGE_H / 2, px + x + w, yy + BADGE_H / 2],
                                radius=6, fill=color)
            d.text((px + x + w / 2, yy), txt, font=f11b, fill="#ffffff", anchor="mm")
            x += w + 6
        have = True
    return yy + PIC_LINE_H

blocks = []
if clock.get("busiest_hour") is not None:
    blocks.append(([seg_t("最繁忙时段："), seg_b(clock["busiest_hour"], P1), seg_t(" · ", GRAY),
                    seg_t("{} scrobbles".format(clock.get("scrobbles")), DARK)], 0))
if discovery:
    blocks.append(([seg_t("新发现：新艺人 "), seg_b("{}%".format(discovery.get("new_artists_pct")), P2),
                    seg_t(" · 新专辑 "), seg_b("{}%".format(discovery.get("new_albums_pct")), P2),
                    seg_t(" · 新曲目 "), seg_b("{}%".format(discovery.get("new_tracks_pct")), P2)], 0))
if music_ratio:
    blocks.append(([seg_t("独立计数：曲目 "), seg_b(music_ratio.get("tracks"), GREEN),
                    seg_t(" · 专辑 "), seg_b(music_ratio.get("albums"), GREEN),
                    seg_t(" · 歌手 "), seg_b(music_ratio.get("artists"), GREEN)], 0))
nz = sorted((d_ for d_ in decades if d_.get("count")), key=lambda x: -x["count"])[:4]
if nz:
    segs = [seg_t("年代：")]
    for i, d_ in enumerate(nz):
        if i:
            segs.append(seg_t(" · ", GRAY))
        segs += [seg_t(d_["name"] + " "), seg_b(d_["count"], ORANGE)]
    blocks.append((segs, 0))
if genre_items:
    segs = [seg_t("曲风：")]
    for i, (g, c) in enumerate(genre_items):
        if i:
            segs.append(seg_t("、 ", GRAY))
        segs += [seg_t(g + " "), seg_b("×{}".format(c), ROSE)]
    blocks.append((segs, int(d.textlength("曲风：", f13))))
else:
    blocks.append(([seg_t("曲风：—", GRAY)], 0))

total_rows = sum(flow_rows(segs, 684, ind) for segs, ind in blocks)
bottom, ct, px, pw = draw_panel(y, "听歌画像", total_rows * PIC_LINE_H)
yy = ct + PIC_LINE_H / 2
for segs, ind in blocks:
    yy = draw_flow(yy, segs, pw, ind)
y = bottom + 16

# ══════════ 页脚 ══════════
d.text((W // 2, y), "数据来源 last.fm listening report + API 原始 scrobble（共 {} 条） · 黑名单仅隐藏展示条目，底层数据保留".format(
    api.get("total_scrobbles", "?")), font=F(11), fill="#b0b0b4", anchor="ma")
y += 40

im = im.crop((0, 0, W, y))
out = os.path.join(BASE_DIR, "artifacts", "report_" + START, "02_report.png")
im.save(out)
print("saved", out, im.size)
print("shown: artists={} tracks={} albums={} | genres={} | candidate_merges={}".format(
    len(artists), len(tracks), len(albums), len(genre_items), meta.get("candidate_merges")))
