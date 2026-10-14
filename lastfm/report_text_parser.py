#!/usr/bin/env python3
"""listening-report 页面 innerText 解析器（固化提取，替代子代理手抄 JSON）。

输入：浏览器执行 report_extract_dump.js 得到的 document.body.innerText 全文。
输出：page JSON dict（schema 见 listening_report_pull.py docstring）。
用法：
  from report_text_parser import parse_report_text
  page = parse_report_text(open("/tmp/report_inner.txt").read())

解析锚点均来自真实页面文本（2026-10 抓取），字段缺失时填 None，不编造数字。
内部一致性自检（可选跑 check_consistency）：daily 求和 == clock 求和 == 总 scrobbles。
"""
import re

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def _int(s):
    try:
        return int(str(s).replace(",", "").strip())
    except Exception:
        return None

def _section_lines(lines, start_marker, end_marker):
    """返回 start_marker 行之后到 end_marker 行之前的非空行列表。"""
    out, on = [], False
    for ln in lines:
        s = ln.strip()
        if not on:
            if s == start_marker or s.startswith(start_marker):
                on = True
            continue
        if end_marker and (s == end_marker or s.startswith(end_marker)):
            break
        if s:
            out.append(s)
    return out

def _parse_entries(sec_lines):
    """解析 Top Artist/Album/Track 条目：#N [name] / [artist] / count( scrobbles)?"""
    entries, cur = [], None
    for s in sec_lines:
        m = re.match(r"^#(\d+)(?:\s+(.+))?$", s)
        if m:
            if cur and cur.get("scrobbles") is not None:
                entries.append(cur)
            cur = {"rank": int(m.group(1))}
            if m.group(2):
                cur["name"] = m.group(2).strip()
            continue
        if cur is None:
            continue
        m2 = re.match(r"^(\d[\d,]*)(?: scrobbles)?$", s)
        if m2:
            cur["scrobbles"] = _int(m2.group(1))
            entries.append(cur)
            cur = None
        elif "name" not in cur:
            cur["name"] = s
        elif "artist" not in cur:
            cur["artist"] = s
    if cur and cur.get("scrobbles") is not None:
        entries.append(cur)
    return entries

def parse_report_text(text):
    lines = text.replace("\r", "").split("\n")
    joined = "\n".join(lines)
    out = {"meta": {}, "totals": {}, "clock": {}, "discovery": {},
           "music_ratio": {}, "community": {}, "top_new": {}}

    # ── 日期范围 + 顶部总量 ──
    m = re.search(r"(\d{1,2} [A-Z]{3} \d{4})\s*-\s*(\d{1,2} [A-Z]{3} \d{4})", joined)
    if m:
        out["meta"]["range_text"] = "{} - {}".format(m.group(1), m.group(2))
        tail = joined[m.end():m.end() + 300]
        m2 = re.search(r"(\d[\d,]*)\s*scrobbles", tail)
        if m2:
            out["totals"]["scrobbles"] = _int(m2.group(1))
        m3 = re.search(r"(\d+)%\s*vs\.?\s*last week", tail)
        if m3:
            out["totals"]["scrobbles_vs_prev"] = "{}% vs. last week".format(m3.group(1))

    # ── 每日表（Fri..Thu，含上周对比） ──
    daily, daily_prev = {}, {}
    for wd, cnt, cmp_ in re.findall(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\t(\d+)\t(\d+)$", joined, re.M):
        daily[wd] = _int(cnt)
        daily_prev[wd] = _int(cmp_)
    if daily:
        out["daily"], out["daily_prev"] = daily, daily_prev

    # ── Top 歌手/专辑/曲目 + 新发现率 ──
    for key, top_marker, new_marker, pct_name in [
            ("top_artists", "Top Artist", "New Artists", "new_artists_pct"),
            ("top_albums", "Top Album", "New Albums", "new_albums_pct"),
            ("top_tracks", "Top Track", "New Tracks", "new_tracks_pct")]:
        sec = _section_lines(lines, top_marker, new_marker)
        out[key] = _parse_entries(sec)
        m = re.search(new_marker + r"\n(\d+)%", joined)
        if m:
            out["discovery"][pct_name] = _int(m.group(1))
        m = re.search(new_marker + r"\n\d+%\n[^\n]*\n#1 (.+)\n\d+ scrobbles", joined)
        if m:
            out["top_new"][key.split("_")[1]] = m.group(1).strip()

    # ── MUSIC RATIO（独立计数 + 上周对比） ──
    for name, key in [("Tracks", "tracks"), ("Albums", "albums"), ("Artists", "artists")]:
        m = re.search(r"\n" + name + r"\n(\d+)\nvs\. (\d+) \(last week\)", joined)
        if m:
            out["music_ratio"][key] = _int(m.group(1))
            out["music_ratio"][key + "_prev"] = _int(m.group(2))

    # ── LISTENING FINGERPRINT（User Data 列） ──
    fp = {}
    for row in re.findall(r"^(Consistency|Discovery rate|Variance|Concentration|Replay rate)\t[^\t]*\t(\d+)\t(\d+)\t", joined, re.M):
        fp[row[0]] = {"user": _int(row[1]), "global": _int(row[2])}
    if fp:
        mapping = {"Consistency": "consistency_pct", "Discovery rate": "discovery_pct",
                   "Variance": "variance_pct", "Concentration": "concentration_pct",
                   "Replay rate": "replay_pct"}
        for k, v in mapping.items():
            if k in fp:
                out["music_ratio"][v] = fp[k]["user"]
        out["fingerprint"] = fp

    # ── TOP TAGS（末列 = 当前报告周计数） ──
    tag_rows = re.findall(r"^(.+?)((?:\t\d+)+)$", joined, re.M)
    tag_header = re.search(r"^Tag\t((?:[^\t\n]+\t)+[^\t\n]+)$", joined, re.M)
    if tag_header and tag_rows:
        headers = tag_header.group(1).split("\t")
        ncol = len(headers)
        tags_table = []
        for name, counts in tag_rows:
            vals = [_int(x) for x in counts.strip().split("\t")]
            if len(vals) == ncol:
                tags_table.append({"name": name.strip(), "counts": vals})
        out["tags_table"] = {"headers": headers, "rows": tags_table}
        out["tags_current"] = [{"name": r["name"], "count": r["counts"][-1]} for r in tags_table]

    # ── MUSIC BY DECADE ──
    decades = []
    sec = _section_lines(lines, "Decade\tScrobbles", None)
    for s in sec:
        parts = s.split("\t")
        if len(parts) >= 2 and re.match(r"^(Pre-)?\d{4}s$", parts[0]) and _int(parts[1]) is not None:
            decades.append({"name": parts[0], "count": _int(parts[1])})
    if decades:
        out["decades"] = decades

    # ── LISTENING CLOCK ──
    hours = {}
    for h, c in re.findall(r"^(\d{1,2})\t(\d+)$", joined, re.M):
        if 0 <= int(h) <= 23:
            hours[int(h)] = _int(c)
    if hours:
        out["clock"]["hours"] = {str(k): hours[k] for k in sorted(hours)}
        m = re.search(r"Busiest hour\n([^\n]+)\nScrobbles in busiest hour\n(\d+)", joined)
        if m:
            out["clock"]["busiest_hour"] = m.group(1).strip()
            out["clock"]["scrobbles"] = _int(m.group(2))

    # ── QUICK FACTS ──
    m = re.search(r"Listening time\n(\d+)\n([^\n]+)\n", joined)
    if m:
        out["totals"]["listening_time"] = "{} {}".format(m.group(1), m.group(2).strip().lower())
    m = re.search(r"Average scrobbles\n(\d+)\n/DAY", joined)
    if m:
        out["totals"]["per_day"] = _int(m.group(1))
    m = re.search(r"Scrobbles in most active day\n(\d+)\n([^\n]+)\n", joined)
    if m:
        out["totals"]["most_active"] = {"count": _int(m.group(1)), "date": m.group(2).strip()}
    qf = joined[joined.find("QUICK FACTS"):joined.find("COMMUNITY")]
    vs = re.findall(r"vs\. ([^\n]+\(last week\))", qf)
    if len(vs) >= 3:
        out["totals"]["listening_time_vs_prev"] = "vs. " + vs[0]
        out["totals"]["per_day_vs_prev"] = "vs. " + vs[1]
        out["totals"]["most_active_vs_prev"] = "vs. " + vs[2]

    # ── COMMUNITY（先 scrobble 榜，后 discovery 榜） ──
    ranks = re.findall(r"volatile-Quartz's rank\n(\d+/\d+)", joined)
    if ranks:
        out["community"]["scrobble_rank"] = ranks[0]
        out["community"]["discovery_rank"] = ranks[1] if len(ranks) > 1 else None

    return out

def check_consistency(page):
    """内部一致性：每日求和 / 时钟求和 / 总 scrobbles 互相对账。返回 (ok, detail)。"""
    total = (page.get("totals") or {}).get("scrobbles")
    detail = []
    ok = True
    daily = page.get("daily") or {}
    if daily and total is not None:
        s = sum(daily.values())
        detail.append("daily_sum={} total={}".format(s, total))
        ok &= (s == total)
    hours = ((page.get("clock") or {}).get("hours")) or {}
    if hours and total is not None:
        s = sum(hours.values())
        detail.append("clock_sum={} total={}".format(s, total))
        ok &= (s == total)
    return ok, "; ".join(detail)

if __name__ == "__main__":
    import sys, json
    page = parse_report_text(open(sys.argv[1]).read())
    print(json.dumps(page, ensure_ascii=False, indent=1))
    ok, detail = check_consistency(page)
    print("consistency:", "OK" if ok else "FAIL", "|", detail)
