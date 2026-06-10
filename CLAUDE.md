# worldcup_2026 · 必守铁律

> 每次操作本工作区**必看**。详细见 [README.md](README.md) 与 [wc_skills/wc-data-collect](wc_skills/wc-data-collect/SKILL.md);这里是精简版,不许违反。

## 数据采集 & 备份

1. **一次收集 = 一个完整快照** —— 一次采齐,raw 落**一个** `raw/bg/<YYYY-MM-DD_HHMM>/` 目录,data 全基于这一次;**绝不多次 raw 拼**。
2. **全文留底** —— raw 存**整页全文**(不是 WebFetch 摘要、不是只某段)。
3. **命名精确到分钟 + 分子文件夹** —— raw 目录带时分;data 快照 `data/bg/asof=<YYYY-MM-DD>/`(按日);一次采集一目录、**按采集种类分子文件夹** + 每次留 `_source.md` 来源说明(如 `<ts>/transfermarkt/`;旧维基目录混装为历史例外)。
4. **备份** —— 统一 `backup/<YYYY-MM-DD_HHMM>/` + 被备份的 data+raw + `说明.md`。
5. **raw=原文、data=加工**,分开;raw 只增不改。
6. **历史数据**(历届比赛)先不采。

## 工作区

- `base/` **只读不动**(要改:改 release 再同步)。
- 采集**走 `wc_eval/bg_collect/collect_all.py`**(一键总入口,一次收集=一个快照)—— 命名/路径/落盘已写死在代码里,跑脚本自动合规,别手动绕开。
