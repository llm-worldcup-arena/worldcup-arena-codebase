# 采集来源说明 · 维基 bg 主采集

- **采集时间**：2026-06-08_1033（精确到分钟）
- **采集种类（本目录混装，类型靠文件名前缀区分）**：
  - `<三字码>.wikitext` —— 48 队维基**整页全文**（球员阵容 + 主教练 + 世界杯史 + 荣誉 + 近期赛果都在里面）
  - `player_<person_id>.wikitext` —— ~1250 名球员**个人页全文**（全名/生日/身高/位置/国脚/俱乐部生涯）
  - `fixt_group_<X>.wikitext` / `fixt_knockout.wikitext` —— 12 小组子页 + 淘汰赛（赛程/分组/bracket）
  - `qual_<洲>*.wikitext` —— 各洲预选赛积分榜模板
  - `fifa_rankings.txt` —— FIFA 排名模板 expandtemplates 展开留底
  - `World.tsv` —— Elo 原始数据
- **数据源**：
  - **en.wikipedia.org**（MediaWiki API `action=parse&prop=wikitext`，整页全文；FIFA 排名 `expandtemplates`）
  - **www.wikidata.org**（球员中文名：enwiki→Q 号→zh-cn）
  - **www.eloratings.net**（Elo，World.tsv 静态文件）
- **合规**：User-Agent 标明学术用途 + 邮箱（浏览器伪装会被 403）
- **提取去向**：`bg/persons.json`、`teams.json`、`matches.json`、`venues.json`、`snapshots/`、`static/`
- **入口脚本**：`wc_eval/bg_collect/collect_all.py`（+ collect_players / collect_qualifying）
- **用途**：世界杯 2026 预测 benchmark 背景数据
- **注**：本目录为旧规范（一次采集一目录、类型靠文件名前缀区分）。自 Transfermarkt 采集起改新规范：raw/bg/<ts>/<采集种类>/ 分子文件夹，详见各 `transfermarkt/_source.md`。
