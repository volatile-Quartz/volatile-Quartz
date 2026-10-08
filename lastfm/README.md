# lastfm-tools · Last.fm 周报工具链

长期维护分支 `lastfm-tools`，与 master（周记内容 + Actions 自动更新）分离。
**所有 lastfm 相关改动只推本分支，不碰 master。**

## 流水线（三步）

```bash
# 1. 拉取 + 清洗 + 聚合（参数=周一起始日，北京时间）
python3 lastfm/weekly_stats_prep.py 2026-09-28

# 2. 时长 + 歌手标签（读 prep，写入缓存）
python3 lastfm/weekly_stats_enrich.py          # 缓存默认 /tmp/lastfm_dur_cache.json

# 3. 生成统计 md 块 + HTML 报告
python3 lastfm/weekly_stats_report.py

# 4.（可选）直接生成周报图片（PIL 画图，无需浏览器）
python3 lastfm/weekly_stats_img.py    # 输出 /workspace/<year>week<no>_report.png
```

- 中间产物：`/tmp/lastfm_prep.json`、`/tmp/lastfm_enrich.json`、`/tmp/lastfm_report.json`
- 成品：统计块打印到 stdout + 写 `/workspace/week{no}.md`；报告 `/workspace/week{no}_report.html`

## 产物留存（防止重复拉取/重复处理）

每周处理完成后，将当周全部产物归档到 `lastfm/artifacts/YYYYweekNN/` 并随分支提交，后续可直接读取，无需重新拉取 API：

| 文件 | 内容 |
| :--- | :--- |
| `01_raw.json` | 当周原始听歌记录（API 原样，含 album） |
| `02_prep.json` | 清洗+聚合结果（clean / full_counts / daily / top_artists 等） |
| `03_enrich.json` | 时长与歌手标签补充结果 |
| `04_report.json` | 统计指标摘要（时长/词云标签/新歌占比/对比上周） |
| `05_*_week*.md` | 最终统计块（发布用） |
| `06_*_week*_report.html` | 最终 HTML 周报 |
| `07_rules_snapshot.json` | 当时清洗规则快照（黑名单/白名单等，便于日后对照） |
| `08_*_week*_report.png` | 报告整页截图（同时复制一份到 `.screenshots/`） |

归档命令示例：

```bash
mkdir -p lastfm/artifacts/2026week40/
cp /tmp/lastfm_prep.json   lastfm/artifacts/2026week40/02_prep.json
cp /tmp/lastfm_enrich.json lastfm/artifacts/2026week40/03_enrich.json
cp /tmp/lastfm_report.json lastfm/artifacts/2026week40/04_report.json
cp 2026week40.md           lastfm/artifacts/2026week40/05_2026week40.md
cp 2026week40_report.html  lastfm/artifacts/2026week40/06_2026week40_report.html
cp lastfm/lastfm_rules.json lastfm/artifacts/2026week40/07_rules_snapshot.json
# 截图：整页渲染后存 08_* 与 .screenshots/2026week40_report.png
```

## 口径约定

| 项 | 口径 |
| :--- | :--- |
| 有效记录 | 清洗后播放次数（含重复播放） |
| 独立曲目 / 独立歌手 | 清洗后去重 |
| 日均 | 有效记录 ÷ 7（自然周） |
| 每日「最猛/最冷清」 | 独立曲目/日（单位「首」） |
| 累计时长 | 每首曲目时长×播放次数求和；Last.fm duration 为**毫秒**，脚本归一为秒；缺失按同歌手均值插值（单位「次」） |
| 风格分布 | Top 歌手标签 × 播放次数，经 `style_genre_whitelist` 过滤、`style_tag_merges` 合并（如 drum and bass→dnb） |
| 对比上周 | 清洗后有效记录 vs 上周 |

## 规则文件 `lastfm_rules.json` 字段

| 字段 | 作用 |
| :--- | :--- |
| `blacklist_artists` | 按歌手名片段剔除（视频号/ASMR 主播等） |
| `filter_keywords` | 曲名关键词剔除（asmr/水音世界观/翻唱等） |
| `blacklist_tracks` | `歌手\|曲名` 整条剔除 |
| `solo_alias` | 同人异名合并（如 Yukiyanagi→YUKIYANAGI） |
| `feat_map` | 主创 feat. 演唱（如 MIMI/初音ミク/重音テト） |
| `amp_map` | 并列合作 &（如 TIC/Paperman） |
| `no_split` | 含分隔符但不可拆的组合名（22/7、Leo/need 等） |
| `artist_by_song` | 按歌修正歌手归属（如猎豹游戏→闫东炜） |
| `title_by_song` | 按歌修正曲名（精确或前缀匹配，优先于后缀剥离；用于双括号清洗、尾部 `(` 清理、拼写修正） |
| `title_suffix` | 曲名须省略的版本/风格后缀（Remix、Instrumental 等） |
| `style_genre_whitelist` | 风格分布保留的纯曲风词（语言/人声描述/来源标签一律不算） |
| `style_tag_merges` | 风格标签同义合并 |
| `extra_rules` | 行为开关 |

新增/修改条目直接编辑本文件即可，无需改代码。

## 每周维护流程

1. `git fetch origin && git checkout lastfm-tools`（沙箱工作区可能被重置，先拉最新）
2. **拉取 → 先确认 → 再处理**：跑 `weekly_stats_prep.py` 得到清洗后逐行清单/统计后，**先把原始条数、过滤项、去重结果展示给用户确认**，确认后再继续 enrich/report，不做未确认的自动处理
3. 有清洗问题 → 编辑 `lastfm_rules.json`（或修脚本）
4. 归档当周产物到 `lastfm/artifacts/YYYYweekNN/`（见上文「产物留存」）
5. `git add lastfm/ .screenshots/ 2026week*.md 2026week*_report.html && git commit && git push origin lastfm-tools`

## GitHub Actions 自动执行

`.github/workflows/weekly-lastfm-report.yml`：每周一 01:30（北京时间）自动生成上一自然周周报 →
归档到 `lastfm/artifacts/YYYYweekNN/` → 推 `lastfm-tools-preview` 分支 → 开/更新 PR（base=lastfm-tools），
人工确认后才合入，保留"先确认再处理"。

- 依赖：`pillow`、`wordcloud`、`numpy` + 中文字体 `fonts-wqy-microhei`（CI 内自动安装）
- **注意**：GitHub Actions 只扫描默认分支(master)的 workflow，本分支内的 yml 需同步一份到 master 才生效
- 手动触发：仓库 Actions 页 → lastfm-weekly-report → Run workflow
