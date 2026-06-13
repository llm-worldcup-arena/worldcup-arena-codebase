# worldcup_2026 · 必守铁律

> 每次操作本工作区**必看**。详细见 [README.md](README.md) 与 [wc_skills/wc-data-collect](wc_skills/wc-data-collect/SKILL.md);这里是精简版,不许违反。

## 🚨 仓库结构(别再搞混!2026-06-13 踩坑)

- **`/home/ubuntu/worldcup_2026/`** = **工作目录**(在这里干活)。**它本身不是 git 仓**。
- **`/home/ubuntu/worldcup_2026_release/`** = **公开代码仓**(GitHub `llm-worldcup-arena/worldcup-arena-codebase`,论文/公开 codebase 的唯一真源)。
- **`worldcup_2026_web/site/`** = 网页仓(GitHub Pages 展示)。
- **发布代码 = 同步 + 推**:改完工作目录 → `rsync -a --delete --exclude=.git --exclude=secrets.local.json --exclude=base/ --exclude=backup/ --exclude=__pycache__ 工作目录/{wc_eval,wc_skills,wc_runs,config,docs}/ → release仓/` + 拷 CLAUDE.md/README → 在 release 仓 `git commit && git push`(中性作者)。**光推网页≠推代码;两个都要推,否则代码仓 vs 网页不一致(砸"唯一真源")。**
- 安全铁律:`config/secrets.local.json`(真 key)**永远只在本地、被 gitignore**,**绝不进任何 git 仓**;同步/提交前必扫一遍全树无 key。data_raw 按用户决定**带进 release**(可重跑但要全)。

## 数据采集 & 备份

1. **一次收集 = 一个完整快照** —— 一次采齐,raw 落**一个** `data_raw/<YYYY-MM-DD_HHMM>/` 目录,data 全基于这一次;**绝不多次 raw 拼**。
2. **全文留底** —— raw 存**整页全文**(不是 WebFetch 摘要、不是只某段)。
3. **命名精确到分钟 + 分子文件夹** —— raw 目录带时分;data 快照 `data_reference/snapshots/asof=<YYYY-MM-DD>/`(按日);一次采集一目录、**按采集种类分子文件夹** + 每次留 `_source.md` 来源说明(如 `<ts>/transfermarkt/`;旧维基目录混装为历史例外)。
4. **备份** —— 统一 `backup/<YYYY-MM-DD_HHMM>/` + 被备份的 data+raw + `说明.md`。
5. **raw=原文、data=加工**,分开;raw 只增不改。
   - **数据三层(2026-06-13 定型)**:`data_raw/`=未加工·收集过程(按时分,只记每次新增)· `data_processed/`=加工成熟仓库(按实体累积:match_broadcast 每场/team_news 每队/prematch_news/match_env 每场环境/team_coach 每队主帅/match_referee 每场主裁)· `data_reference/`=基础参考数据(原名 bg)。新旧判断以 processed 为准(身份键:news=URL、broadcast=源名、env=场次)。**processed 只收逐字全文**,blocked 存根当轮重抓/换源/清理,记 `_cleanup_log.md`。
6. **历史数据**(历届比赛)先不采。

## 工作区

- `base/` **只读不动**(要改:改 release 再同步)。
- **赛前基础采集**走 `wc_eval/bg_collect/collect_all.py`(一键总入口,一次收集=一个快照);**开赛后增量线**走专用采集器:`collect_team_news.py`(队伍新闻双写)/ `collect_match_env.py`(环境:开球/天气/裁判)/ `collect_match.py`+`integrate_match.py`(赛后硬数据→summary,自动记 CHANGELOG),配 skill `wc-incremental-update` —— 命名/路径/落盘都写死在代码里,跑脚本自动合规,别手动绕开。
