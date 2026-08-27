# AGENTS.md — 本仓库约定（AI 助手 / 协作者必读）

## 仓库是什么

`bingdu748/bingdu748` 是 GitHub 个人主页仓库。`README.md` 中的「音乐世界」板块由
`.github/workflows/update-lastfm.yml` 每 30 分钟从 Last.fm API 拉取数据自动生成并自动提交到 `main`。

## 极重要：push 前必须先同步

`main` 分支会被机器人每 30 分钟自动提交一次（"更新时间"变化即产生新提交），
所以本地 push 时经常报 `! [rejected] HEAD -> main (fetch first)`。
**这是 Git 的正常保护行为，不是配置错误。**

- push 前必须执行：`git pull --rebase origin main`，然后 `git push origin main`
- 遇到 fetch-first 被拒时：禁止 `git push --force`，一律 `git pull --rebase origin main` 后重试
- 推荐直接使用一键脚本（自动完成同步 + 提交 + 推送）：
  `GITHUB_TOKEN=<token> ./scripts/push.sh "提交信息" [文件...]`
  脚本不会把 token 写入仓库；token 仅通过环境变量传入。

## README.md 不要手改

`<!-- LASTFM_START -->` 与 `<!-- LASTFM_END -->` 之间的内容由工作流重新生成，
手改会被覆盖。要调整展示内容，必须改 `fetch_lastfm.js` 中的模板。

## 已知注意点

- Last.fm `user.getweeklychartlist` 返回**升序（最旧在前）**，取最近 3 周要先按 `from` 倒序
  （`getWeeklyPlayCount` 依赖此顺序，参见第 7 步注释）
- GitHub Actions 使用的 secrets：`LASTFM_API_KEY`、`LASTFM_USERNAME`
- 提交身份统一用 `-c user.name=bingdu748 -c user.email=50004335+bingdu748@users.noreply.github.com`（不写全局 config）