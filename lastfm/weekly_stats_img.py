#!/usr/bin/env python3
"""Generate weekly listening report as a single PNG image (no HTML/browser needed).
Reads /tmp/lastfm_prep.json + /tmp/lastfm_enrich.json + lastfm_rules.json (style rules).
Usage: python3 lastfm/weekly_stats_img.py
Output: /workspace/<year>week<no>_report.png  (e.g. 2026week40_report.png)
依赖：pillow、wordcloud、numpy、CJK 字体（找不到字体时给出明确报错）。
"""
import json, os, glob, collections
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(BASE_DIR, "lastfm_rules.json")))
STYLE_DROP = set(RULES.get("style_drop_tags", []))
MERGES = RULES.get("style_tag_merges", {})

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
played = prep.get("played_again", [])

# ---------- 时长：直接查到 + 同歌手均值插值（与 weekly_stats_report.py 同口径） ----------
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

def canon(t):
    t2 = MERGES.get(t, t)
    if t2 in STYLE_DROP or not t2 or len(t2) > 30:
        return None
    return t2

tag_cnt = collections.Counter()
for artist, cnt in top_artists:
    for t in tags_by_artist.get(artist, [])[:6]:
        c = canon(t)
        if c:
            tag_cnt[c] += cnt

# ---------- 字体 ----------
def find_cjk_font():
    cands = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/System/Library/Fonts/PingFang.ttc", "C:/Windows/Fonts/msyh.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    for pat in ["/usr/share/fonts/**/wqy*", "/usr/share/fonts/**/NotoSans*", "/usr/share/fonts/**/CJK*"]:
        for f in glob.glob(pat, recursive=True):
            if os.path.exists(f):
                return f
    raise RuntimeError("未找到 CJK 字体，请先安装 fonts-wqy-microhei（周报图片生成前置依赖）")

FONT = find_cjk_font()
def F(sz, bold=False):
    return ImageFont.truetype(FONT, sz)

# ---------- 布局 ----------
W, PAD = 760, 40
TITLE = "{} {} 听歌周报".format(meta["week_range"].split(" ~ ")[0][:4], meta["week_label"].lower())
SUB = "{} · last.fm @volatile-Quartz".format(meta["week_range"])
BG, CARD, GRAY, DARK, P1, P2 = "#f4f2f8", "#ffffff", "#8a8a8e", "#222222", "#7c5cbf", "#4a90d9"

im = Image.new("RGB", (W, 4000), BG)
d = ImageDraw.Draw(im)
y = 0

def draw_panel(y, title_txt, inner_h):
    """白底圆角卡片；返回 (卡片底部y, 左边距px, 内容宽pw)"""
    x0, x1 = W // 2 - 360, W // 2 + 360
    d.rounded_rectangle([x0, y + 2, x1, y + 34 + inner_h + 18], radius=14, fill=CARD)
    d.text((x0 + 18, y + 12), title_txt, font=F(17, True), fill=DARK)
    return y + 34 + inner_h + 18, x0 + 18, x1 - x0 - 36

# 头部
d.text((W // 2, y + 6), TITLE, font=F(28, True), fill=DARK, anchor="ma")
d.text((W // 2, y + 48), SUB, font=F(14), fill=GRAY, anchor="ma")
y += 92

# 统计卡片 2 列
stats = [
    ("{} 次".format(plays), "本周播放", "有效记录，日均 {} 次".format(round(plays / 7))),
    ("{} 首".format(unique), "独立曲目", "{} 组独立歌手".format(unique_artists)),
    ("约 " + fmt_dur(total_sec), "累计时长", "直查 {} + 插值 {}".format(direct, interpolated)),
    ("{}%".format(pct_new), "新歌占比", "相比上周新听 {} 首".format(new_tracks)),
]
cw, ch, gap = (W - PAD * 2 - 16) // 2, 88, 12
for i, (v, l, s) in enumerate(stats):
    cx = PAD + (i % 2) * (cw + gap)
    cy = y + (i // 2) * (ch + gap)
    d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=14, fill=CARD)
    d.text((cx + 18, cy + 12), v, font=F(26, True), fill=P1)
    d.text((cx + 18, cy + 48), l, font=F(14), fill=DARK)
    d.text((cx + 18, cy + 66), s, font=F(11), fill=GRAY)
y += 2 * (ch + gap) + 16

# 每日播放趋势（独立曲目/日）
days = sorted(daily)
vals = [daily[dd] for dd in days]
inner_h = 210
bottom, px, pw = draw_panel(y, "每日播放趋势（独立曲目/日）", inner_h)
mx = max(vals) or 1
plot_h = inner_h - 30
bw = pw / len(days)
for i, (dd, v) in enumerate(zip(days, vals)):
    bh = (v / mx) * (plot_h - 26)
    x0 = px + i * bw + bw * 0.18
    d.rounded_rectangle([x0, bottom - 24 - bh, x0 + bw * 0.64, bottom - 24], radius=4, fill=P1)
    d.text((x0 + bw * 0.32, bottom - 34 - bh), str(v), font=F(13), fill=DARK, anchor="mm")
    d.text((x0 + bw * 0.32, bottom - 10), dd, font=F(12), fill=GRAY, anchor="mm")
y = bottom + 16

# Top 歌手横向条
n_art = min(len(top_artists), 8)
inner_h = n_art * 30 + 8
bottom, px, pw = draw_panel(y, "Top 歌手（按播放次数）", inner_h)
mx_a = max(c for _, c in top_artists[:8]) or 1
for i, (a, c) in enumerate(top_artists[:8]):
    yy = bottom - inner_h + 10 + i * 30
    d.text((px, yy), str(a), font=F(13), fill=DARK)
    bww = (c / mx_a) * (pw - 200)
    d.rounded_rectangle([px + 190, yy + 4, px + 190 + max(bww, 4), yy + 22], radius=6, fill=P2)
    txt = str(c)
    d.text((px + 190 + max(bww, 4) + 8, yy), txt, font=F(12), fill="#555")
y = bottom + 16

# 风格分布词云（wordcloud 生成 PNG 贴入）
items = [(t, c) for t, c in tag_cnt.most_common(40)]
if items:
    try:
        import numpy as np
        from wordcloud import WordCloud
        WCD, HCD = 720, 420
        mask_im = Image.new("L", (WCD, HCD), 255)
        ImageDraw.Draw(mask_im).ellipse([8, 8, WCD - 9, HCD - 9], fill=0)
        wc = WordCloud(font_path=FONT, mask=np.array(mask_im), background_color="white",
                       colormap="viridis", min_font_size=10, max_font_size=130,
                       prefer_horizontal=0.92, relative_scaling=0.5,
                       collocations=False, margin=4, random_state=42
                       ).generate_from_frequencies(dict(items))
        wimg = wc.to_image()
        ratio = min(1.0, (pw - 20) / wimg.width)
        wimg = wimg.resize((int(wimg.width * ratio), int(wimg.height * ratio)), Image.LANCZOS)
        inner_h = wimg.height + 14
        bottom, px, pw = draw_panel(y, "风格分布", inner_h)
        im.paste(wimg, (px + (pw - wimg.width) // 2, bottom - inner_h + 8))
    except Exception as e:
        inner_h = 60
        bottom, px, pw = draw_panel(y, "风格分布", inner_h)
        d.text((px, bottom - 44), "词云生成失败: {}".format(e), font=F(13), fill="#cf222e")
else:
    inner_h = 60
    bottom, px, pw = draw_panel(y, "风格分布", inner_h)
    d.text((px, bottom - 44), "无", font=F(14), fill=GRAY)
y = bottom + 16

# 反复播放 Top
n_pl = max(len(played), 1)
inner_h = n_pl * 26 + 10
bottom, px, pw = draw_panel(y, "反复播放 Top（本周 ≥2 次）", inner_h)
for i, x in enumerate(played[:10]):
    yy = bottom - inner_h + 12 + i * 26
    f_art = F(13, True)
    d.text((px, yy), x["artist"], font=f_art, fill=DARK)
    aw = d.textlength(x["artist"], font=f_art)
    d.text((px + aw + 6, yy), "《{}》 × {}".format(x["title"], x["count"]), font=F(13), fill=DARK)
y = bottom + 30

# 页脚
d.text((W // 2, y), "数据来源 last.fm API · 清洗规则 lastfm_rules.json · 时长为曲目时长估算（缺失按同歌手均值插值）", font=F(11), fill="#b0b0b4", anchor="ma")
y += 42

im = im.crop((0, 0, W, y))
out = "/workspace/{}_report.png".format(label)
im.save(out)
print("saved", out, im.size)