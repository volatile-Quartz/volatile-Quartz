#!/usr/bin/env python3
"""W39 清洗前统计：全部原始记录（324 条，不应用任何过滤），供用户圈定上/下预览图。"""
import sys, json, collections
sys.argv = ["x", "2026-09-21"]
sys.path.insert(0, "/workspace/lastfm")
import weekly_stats_prep as prep

recs = prep.fetch(*prep.WEEK)
recs.sort(key=lambda r: r["ts"])

# 去重（原始名，小写判重，保留最新）
seen = {}
for r in recs:
    seen[(r["artist"].strip().lower(), r["track"].strip().lower())] = r
uniq = list(seen.values())

byday = collections.Counter(prep.datetime.fromtimestamp(r["ts"] + 8 * 3600).strftime("%m-%d") for r in recs)
art = collections.Counter(r["artist"].strip() for r in recs)
trk = collections.Counter((r["artist"].strip(), r["track"].strip()) for r in recs)

lines = []
lines.append("## 第 39 周 清洗前统计（全部原始记录，未过滤）")
lines.append("")
lines.append("- 本周范围：2026-09-21 ~ 2026-09-27")
lines.append("- 原始记录：**{} 条**（含重复播放），去重后独立曲目 **{} 首**，独立歌手 **{} 组**".format(len(recs), len(uniq), len(art)))
lines.append("- 按天（原始条数）：{}".format("、".join("{}={}".format(d, byday[d]) for d in sorted(byday))))
lines.append("")
lines.append("### Top 歌手（按原始名播放次数，含可能需过滤的非音乐频道）")
for a, c in art.most_common(25):
    lines.append("- {}（{}）".format(a, c))
lines.append("")
lines.append("### 重复播放 ≥2 次（原始名，去重后）")
played = {k: v for k, v in trk.items() if v >= 2}
for (a, t), c in sorted(played.items(), key=lambda x: -x[1]):
    lines.append("- {}《{}》×{}".format(a, t, c))
lines.append("")
lines.append("### 完整逐行清单见 w39_raw_lineup.txt（324 条，含清洗规则命中标注）")

open("/workspace/w39_清洗前统计.md", "w").write("\n".join(lines) + "\n")
print(json.dumps({"raw": len(recs), "uniq": len(uniq), "artists": len(art)}, ensure_ascii=False))