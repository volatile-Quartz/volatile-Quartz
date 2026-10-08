#!/usr/bin/env python3
"""Generate weekly listening report as a single PNG image.
Reads /tmp/lastfm_prep.json + /tmp/lastfm_enrich.json + lastfm_rules.json + genre_tree.json.
Usage: python3 lastfm/weekly_stats_img.py
Output: /workspace/<year>week<no>_report.png  (e.g. 2026week40_report.png)
依赖：pillow + CJK 字体（文泉驿微米黑已预装）。"""
import json, os, glob, collections, re
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(BASE_DIR, "lastfm_rules.json")))
STYLE_DROP = set(RULES.get("style_drop_tags", []))
MERGES = RULES.get("style_tag_merges", {})

# ── genre_tree.json 作为唯一白名单真源（跳过 _ 开头元数据 key） ──
GENRE_WL = set()
_tree_path = os.path.join(BASE_DIR, "genre_tree.json")
def _flat(o, skip="_"):
    if isinstance(o, dict):
        for k, v in o.items():
            if not k.startswith(skip): _flat(v)
    elif isinstance(o, list):
        for x in o: _flat(x)
    elif isinstance(o, str):
        GENRE_WL.add(o)
if os.path.exists(_tree_path):
    _flat(json.load(open(_tree_path)))

prep = json.load(open("/tmp/lastfm_prep.json"))
enr = json.load(open("/tmp/lastfm_enrich.json"))
durations, tags_by_artist = enr["durations"], enr["tags_by_artist"]
meta = prep["meta"]
label = meta["week_range"].split(" ~ ")[0][:4] + meta["week_label"].replace(" ", "").lower()

full_counts = prep["full_counts"]
plays = sum(full_counts.values())
unique = len(full_counts)
unique_artists = len({k.split("||")[0] for k in full_counts})
new_tracks = prep["new_tracks"]
rep_tracks = prep["rep_tracks"]
pct_new = round(new_tracks / unique * 100) if unique else 0
daily = prep["daily"]
top_artists = prep["top_artists"]

# ── 时长估算（与 report.py 同口径） ──
def fmt_dur(sec):
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return "{}:{:02d}:{:02d}".format(h, m, s) if h else "{}:{:02d}".format(m, s)

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

# ── canon 风格清洗 ──
UNKNOWN_GENRES = collections.Counter()
def canon(t):
    t2 = MERGES.get(t, t)
    if t2 in STYLE_DROP or not t2 or len(t2) > 30: return None
    if t2 not in GENRE_WL:
        UNKNOWN_GENRES[t2] += 1
        return None
    return t2

tag_cnt = collections.Counter()
for artist, cnt in top_artists:
    for t in tags_by_artist.get(artist, []):
        c = canon(t.lower())
        if c: tag_cnt[c] += cnt

genres_top = [t for t, c in tag_cnt.most_common(30)]
genres_set = set(genres_top)

# ── 曲风对比（与 report.py 一致逻辑） ──
def prev_label_from(lb):
    m = re.match(r"(\d{4})week(\d+)", lb)
    if not m: return ""
    year, wk = int(m.group(1)), int(m.group(2))
    pw, py = wk - 1, year
    if pw < 1: pw, py = 53, year - 1
    return f"{py}week{pw}"
prev_genres_set = set()
prev_tracks = prev_artists = prev_pct_new = None
for p in [f"{BASE_DIR}/artifacts/{prev_label_from(label)}/04_report.json",
          f"/workspace/lastfm/artifacts/{prev_label_from(label)}/04_report.json",
          f"/tmp/lastfm_report.json"]:
    if os.path.exists(p):
        try:
            prev_report = json.load(open(p))
            prev_genres_set = set(prev_report.get("all_tags", prev_report.get("top_tags", [])))
            prev_tracks = prev_report.get("tracks")
            prev_artists = prev_report.get("artists")
            prev_pct_new = prev_report.get("pct_new")
            break
        except Exception: pass
genres_new = sorted(genres_set - prev_genres_set)
genres_gone = sorted(prev_genres_set - genres_set)

def fmt_diff(cur, prev):
    """±N / ±N% 格式，prev=None 或 0 时返回空。"""
    if prev is None or prev == 0:
        return ""
    d = cur - prev
    pct = d / prev * 100
    return "{}（{}{}%）".format(
        "{:+d}".format(d) if d else "持平",
        "+" if pct >= 0 else "", round(pct))

# ── 字体 ──
def find_cjk_font():
    cands = ["/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"]
    for p in cands:
        if os.path.exists(p): return p
    for pat in ["/usr/share/fonts/**/wqy*", "/usr/share/fonts/**/NotoSans*", "/usr/share/fonts/**/CJK*"]:
        for f in glob.glob(pat, recursive=True):
            if os.path.exists(f): return f
    raise RuntimeError("未找到 CJK 字体")
FONT = find_cjk_font()
def F(sz, bold=False):
    return ImageFont.truetype(FONT, sz)

# ── 色板 ──
W, PAD = 760, 40
TITLE = "{} {} 听歌周报".format(meta["week_range"].split(" ~ ")[0][:4], meta["week_label"].lower())
SUB = "{} · last.fm @volatile-Quartz".format(meta["week_range"])
BG, CARD, GRAY, DARK = "#f4f2f8", "#ffffff", "#8a8a8e", "#222222"
P1, P2 = "#7c5cbf", "#4a90d9"
GREEN, RED = "#2a9d8f", "#e76f51"

# ── 画布（先铺 4000px 够大，最后裁） ──
im = Image.new("RGB", (W, 4000), BG)
d = ImageDraw.Draw(im)
TOP_PAD = 30          # 整张图顶部留白
CHG_LINE_H = 20       # 曲风变化每行高度
INNER_PAD = 10        # panel 标题下 / 数据底 对称 padding
HBAR_BOTTOM_EXTRA = 8 # Top歌手/曲风分布 panel 底部额外 +8（让条底部不贴边）

y = TOP_PAD

def draw_panel(y0, title_txt, data_h, bottom_extra=0):
    """画 panel 外框 + 标题，返回 (panel_bottom, content_top, content_bottom, px, pw)。
    内容区 = 标题底 (y0+34) + INNER_PAD → 标题底 + data_h + INNER_PAD。"""
    x0, x1 = W // 2 - 360, W // 2 + 360
    title_h = 34
    total_h = title_h + INNER_PAD + data_h + INNER_PAD + bottom_extra
    panel_bottom = y0 + total_h
    d.rounded_rectangle([x0, y0 + 2, x1, panel_bottom], radius=14, fill=CARD)
    d.text((x0 + 18, y0 + 12), title_txt, font=F(17, True), fill=DARK)
    content_top = y0 + title_h + INNER_PAD
    content_bottom = y0 + title_h + INNER_PAD + data_h
    return panel_bottom, content_top, content_bottom, x0 + 18, x1 - x0 - 36

# ══════════ 头部 ══════════
d.text((W // 2, y + 14), TITLE, font=F(28, True), fill=DARK, anchor="ma")
d.text((W // 2, y + 56), SUB, font=F(14), fill=GRAY, anchor="ma")
y += 92

# ══════════ 6 张指标卡（反复播放 → 曲风数量） ══════════
tracks_sub = fmt_diff(unique, prev_tracks)
artists_sub = fmt_diff(unique_artists, prev_artists)
# 新歌占比 diff：用百分点差
if prev_pct_new is not None:
    pd = pct_new - prev_pct_new
    pct_sub = "相比上周新听 {} 首（{}{:.0f}pp）".format(new_tracks, "+" if pd >= 0 else "", pd)
else:
    pct_sub = "相比上周新听 {} 首".format(new_tracks)
stats = [
    ("本周播放", "{} 次".format(plays), "有效记录，日均 {} 次".format(round(plays / 7))),
    ("独立曲目", "{} 首".format(unique), tracks_sub),
    ("独立歌手", "{} 位".format(unique_artists), artists_sub),
    ("曲风数量", "{} 种".format(len(genres_set)),
     "+{} 新增 -{} 消失".format(len(genres_new), len(genres_gone)) if prev_genres_set else ""),
    ("累计时长", fmt_dur(total_sec), "直查 {} + 插值 {}".format(direct, interpolated)),
    ("新歌占比", "{}%".format(pct_new), pct_sub),
]
cw, ch, gap = (W - PAD * 2 - 24) // 3, 92, 12
for i, (l, v, s) in enumerate(stats):
    cx = PAD + (i % 3) * (cw + gap)
    cy = y + (i // 3) * (ch + gap)
    d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=14, fill=CARD)
    d.text((cx + 16, cy + 12), l, font=F(13), fill=GRAY)
    d.text((cx + 16, cy + 34), v, font=F(24, True), fill=P1)
    d.text((cx + 16, cy + 66), s, font=F(11), fill=GRAY)
y += 2 * (ch + gap) + 16

# ══════════ 每日播放趋势 ══════════
days = sorted(daily)
vals = [daily[dd] for dd in days]
chart_h = 180  # bars + 日期标签的精确高度
bottom, ct, cb, px, pw = draw_panel(y, "每日播放趋势（播放次数/日）", chart_h)
mx = max(vals) or 1
# bars 区：从 ct 到 cb - 22（底部日期标签留 22px）
bar_bottom_y = cb - 22
bar_max_h = (cb - 22) - ct - 6  # 顶部留 6px 间距
bw = pw / len(days)
for i, (dd, v) in enumerate(zip(days, vals)):
    bh = (v / mx) * bar_max_h
    x0 = px + i * bw + bw * 0.18
    bar_top = bar_bottom_y - bh
    d.rounded_rectangle([x0, bar_top, x0 + bw * 0.64, bar_bottom_y], radius=4, fill=P1)
    d.text((x0 + bw * 0.32, bar_top - 6), str(v), font=F(13), fill=DARK, anchor="mm")
    d.text((x0 + bw * 0.32, cb - 6), dd, font=F(12), fill=GRAY, anchor="mm")
y = bottom + 12

# ══════════ Top 歌手（hbars，与 HTML 同样的垂直居中公式） ══════════
n_art = min(len(top_artists), 8)
RH = 26; FC = RH / 2
rows_h = n_art * RH
bottom, ct, cb, px, pw = draw_panel(y, "Top 歌手（按播放次数）", rows_h, bottom_extra=HBAR_BOTTOM_EXTRA)
mx_a = max(c for _, c in top_artists[:8]) or 1
rows_top = ct  # 从 content_top 起正好贴住 padding
for i, (a, c) in enumerate(top_artists[:8]):
    row_center = rows_top + FC + i * RH
    d.text((px, row_center), str(a), font=F(13), fill=DARK, anchor="lm")
    bww = (c / mx_a) * (pw - 200)
    d.rounded_rectangle([px + 190, row_center - 9, px + 190 + max(bww, 4), row_center + 9],
                        radius=6, fill=P2)
    txt = str(c)
    if bww > d.textlength(txt, F(12)) + 12:
        d.text((px + 190 + max(bww, 4) - 6, row_center), txt, font=F(12), fill="#ffffff", anchor="rm")
    else:
        d.text((px + 190 + max(bww, 4) + 8, row_center), txt, font=F(12), fill="#555", anchor="lm")
y = bottom + 12

# ══════════ 曲风分布（bar 列表，Top 8） ══════════
tag_items = tag_cnt.most_common(8)
n_t = len(tag_items)
rows_h = max(n_t, 1) * RH
bottom, ct, cb, px, pw = draw_panel(y, "曲风分布（按播放次数）", rows_h, bottom_extra=HBAR_BOTTOM_EXTRA)
mx_t = max((c for _, c in tag_items), default=1) or 1
if not tag_items:
    d.text((px, ct + RH // 2), "无", font=F(14), fill=GRAY)
else:
    rows_top = ct
    for i, (t, c) in enumerate(tag_items):
        row_center = rows_top + FC + i * RH
        d.text((px, row_center), str(t), font=F(13), fill=DARK, anchor="lm")
        bww = (c / mx_t) * (pw - 200)
        d.rounded_rectangle([px + 190, row_center - 9, px + 190 + max(bww, 4), row_center + 9],
                            radius=6, fill=P2)
        txt = str(c)
        if bww > d.textlength(txt, F(12)) + 12:
            d.text((px + 190 + max(bww, 4) - 6, row_center), txt, font=F(12), fill="#ffffff", anchor="rm")
        else:
            d.text((px + 190 + max(bww, 4) + 8, row_center), txt, font=F(12), fill="#555", anchor="lm")
y = bottom + 12

# ══════════ 重复播放（≥2 次的歌曲，内联 badge） ══════════
rep_items = [(k, v) for k, v in full_counts.items() if v >= 2]
rep_items.sort(key=lambda x: -x[1])
rep_items = rep_items[:8]
n_r = len(rep_items)
if n_r > 0:
    rows_h = n_r * RH
    bottom, ct, cb, px, pw = draw_panel(y, "重复播放（多次听的歌曲）", rows_h, bottom_extra=HBAR_BOTTOM_EXTRA)
    rows_top = ct
    for i, (k, c) in enumerate(rep_items):
        artist, _, title = k.partition("||")
        row_center = rows_top + FC + i * RH
        # 主标签（左对齐）：歌手 —《歌曲》
        d.text((px, row_center), "{} —《{}》".format(artist, title), font=F(13), fill=DARK, anchor="lm")
        # 紧贴数字 badge（绿色胶囊）
        txt = "×{}".format(c)
        label_w = d.textlength("{} —《{}》".format(artist, title), F(13))
        badge_h = 18
        badge_w = d.textlength(txt, F(11, True)) + 12
        bx0 = px + label_w + 8
        bx1 = bx0 + badge_w
        by0 = row_center - badge_h / 2
        d.rounded_rectangle([bx0, by0, bx1, by0 + badge_h], radius=5, fill=GREEN)
        d.text(((bx0 + bx1) / 2, row_center), txt, font=F(11, True), fill="#ffffff", anchor="mm")
    y = bottom + 12
else:
    bottom, ct, cb, px, pw = draw_panel(y, "重复播放（多次听的歌曲）", 24)
    d.text((px, ct + 4), "本周无重复播放，全是新歌 🔥", font=F(13), fill=GRAY)
    y = bottom + 12

# ══════════ 曲风变化（新增/消失，自动换行防溢出） ══════════
def wrap_genres(prefix, genres, font, avail_w):
    """把 genre 列表按 avail_w 自动拆成多行。
    第一行用 prefix（含冒号），后续行用纯空格缩进对齐冒号后位置；
    被截断的行末保留顿号表示未完。"""
    lines = []
    # indent = prefix 去掉最后那个冒号后的纯空格，长度 = len(prefix)
    # 例如 "+21 新增：" → indent = 8 个空格，对齐到冒号后第一个字符
    indent = " " * len(prefix)
    cur = prefix
    for g in genres:
        sep = "、" if cur != prefix else ""
        cand = cur + sep + g
        if d.textlength(cand, font) > avail_w and cur != prefix:
            lines.append(cur + "、")  # 截断行末尾加顿号
            cur = indent + g
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines

chg_font = F(13, True)
chg_lines = []
if not prev_genres_set:
    chg_lines.append(("缺少上周对比数据（首次运行？）", GRAY, False))
elif not genres_new and not genres_gone:
    chg_lines.append(("与上周持平，曲风无变化", GRAY, False))
else:
    if genres_new:
        chg_lines.extend((l, GREEN, True) for l in wrap_genres(
            "+{} 新增：".format(len(genres_new)), genres_new, chg_font, pw))
    if genres_gone:
        chg_lines.extend((l, RED, True) for l in wrap_genres(
            "-{} 消失：".format(len(genres_gone)), genres_gone, chg_font, pw))

chg_data_h = len(chg_lines) * CHG_LINE_H
bottom, ct, cb, px, pw = draw_panel(y, "曲风变化", chg_data_h)
yy = ct
for line_text, color, bold in chg_lines:
    d.text((px, yy + 4), line_text, font=F(13, bold), fill=color)
    yy += CHG_LINE_H
y = bottom + 16

# ══════════ 页脚 ══════════
d.text((W // 2, y), "数据来源 last.fm API · 清洗规则 lastfm_rules.json · 曲风白名单 genre_tree.json · 时长为曲目时长估算",
       font=F(11), fill="#b0b0b4", anchor="ma")
y += 42

im = im.crop((0, 0, W, y))
out = os.path.join(BASE_DIR, "artifacts", label, "08_{}_report.png".format(label))
im.save(out)
print("saved", out, im.size)
if UNKNOWN_GENRES:
    print("⚠️ unknown genres:", dict(UNKNOWN_GENRES))
