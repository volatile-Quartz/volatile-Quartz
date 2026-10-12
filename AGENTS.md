# AGENTS.md — 本仓库约定（AI 助手 / 协作者必读）

## 仓库是什么

`volatile-Quartz/volatile-Quartz` 是 GitHub 个人主页仓库。`README.md` 的动态区块由
`.github/workflows/update-homepage.yml` 每周一 03:00 UTC（北京 11:00）统一刷新，
对应 5 个 fetch 脚本：`fetch_diary.js`（周记）、`fetch_releases.js`（草稿纸）、
`fetch_issues.js`（动漫/影视/唱歌）、`fetch_whatpulse.js`（WhatPulse）、`fetch_lastfm.js`（Last.fm 概览）。

Last.fm 详细周报由 `lastfm-weekly-phase1`（手动触发拉数据出预览 PR）和
`lastfm-weekly-phase2`（预览合入 main 后自动生成正式周报）两条流水线产出。

> 注意：主页 README 只有在**仓库名与用户名完全一致**时才展示。若后续再次改名，仓库需同步改名。

## 极重要：push 前必须先同步

`main` 分支会被机器人每周一自动提交一次（"更新时间"变化即产生新提交），
所以临近周一晚上 push 时可能报 `! [rejected] HEAD -> main (fetch first)`。
**这是 Git 的正常保护行为，不是配置错误。**

- push 前必须执行：`git pull --rebase origin main`，然后 `git push origin main`
- 遇到 fetch-first 被拒时：禁止 `git push --force`，一律 `git pull --rebase origin main` 后重试
- 推荐直接使用一键脚本（自动完成同步 + 提交 + 推送）：
  `GITHUB_TOKEN=<token> ./scripts/push.sh "提交信息" [文件...]`
  脚本不会把 token 写入仓库；token 仅通过环境变量传入。
- 脚本未指定文件时的默认暂存列表：`fetch_lastfm.js`、`scripts/push.sh`、`AGENTS.md`
  （脚本会显式 `git add` 这些文件，避免 `git add -A` 误带入无关文件）

## README.md 不要手改

`<!-- LASTFM_START -->` 与 `<!-- LASTFM_END -->` 之间的内容由工作流重新生成，
手改会被覆盖。要调整展示内容，必须改 `fetch_lastfm.js` 中的模板。

## 已知注意点

- Last.fm `user.getweeklychartlist` 返回**升序（最旧在前）**，取最近 3 周要先按 `from` 倒序
  （`getWeeklyPlayCount` 依赖此顺序，参见第 7 步注释）
- GitHub Actions 使用的 secrets：`LASTFM_API_KEY`、`LASTFM_USERNAME`
- 提交身份统一用 `-c user.name=volatile-Quartz -c user.email=50004335+volatile-Quartz@users.noreply.github.com`（不写全局 config）