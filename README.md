# 世界杯预测工作区 · worldcup_2026

> 三份顶层文档:**本 README** 讲「工作区怎么组织」;[`PLAN.md`](PLAN.md) 讲「要做什么、基于什么」;[`CODEBASE.md`](CODEBASE.md) 讲「**代码地图**——收集→格式化→team_data→增量→预测，每个 skill/py 干什么」。

## 目录结构(✅ 已定 / 🟡 待细化)

| 目录 / 文件 | 是什么 | 状态 |
|---|---|---|
| `README.md` | 工作区结构 + 约定(本文件) | ✅ |
| `PLAN.md` | 整体方案:基于什么 / 做什么 / 4 个待定决策 | ✅ |
| `base/` | `societybench_release` 的**只读镜像**:`base/skills` + `base/eval` + `base/VERSION`(记来源版本),不动 | ✅ |
| `wc_skills/` `wc_eval/` | 世界杯**专属**代码(新写;改造细节见 `PLAN.md`) | ✅ |
| `config/` | 需人工定的配置(绑定 PLAN 决策) | ✅ 层定 · 内容待决策 |
| `wc_runs/` | 运行数据 & 产物 | 🟡 内部初步规划 |

## 约定(钉死)

1. **`base/` 只读不动。** 整个工作区基于 `societybench_release`;要改基底逻辑,**改 release、再同步过来**(`cp -r societybench_release/{skills,eval} → base/`,并更新 `base/VERSION`),**绝不在 base 里改**。release 是唯一真源。
2. **顶层 = 代码 / 配置**(base · wc · config);**`wc_runs/` = 流动的数据与产物**。
3. 文档就近原则:`wc_runs/` 带就近 README(结构动态);`wc_skills` / `wc_eval` 的说明并进本 README + `PLAN.md`;`base/` 只读不带。

## 数据采集 & 备份约定(钉死)

1. **一次收集 = 一个完整快照。** 一次把该采的全采齐,raw 落**一个**时间戳目录,data 全部基于这一次;**不允许多次 raw 拼**(否则各部分时点不一致)。
2. **全文留底。** raw 存**整页全文**(不是 WebFetch 摘要、不是只某段),以后扩充字段直接从 raw 挖、**不用重采**。
3. **命名精确到分钟 + 分子文件夹。** raw 目录 `raw/bg/<YYYY-MM-DD_HHMM>/`;data 快照 `data/bg/asof=<YYYY-MM-DD>/`(按日)。一次采集一目录、**按采集种类分子文件夹**(如 `<ts>/transfermarkt/`、`<ts>/match_reports/`)+ 每次留 `_source.md` 来源说明。
4. **备份。** 统一 `backup/<YYYY-MM-DD_HHMM>/`,里面放被备份的 `data`+`raw` + 一个 `说明.md`(记:什么时间、什么内容、为什么备)。
5. **raw = 原文、data = 加工**,两者分开;raw 永久留底,只增不改。
6. **历史数据**(历届比赛)先不采。
7. **采集执行细节**(数据源、维基直连方法、解析、字段 schema)见 [`wc_skills/wc-data-collect`](wc_skills/wc-data-collect/SKILL.md) —— 本节是钉死原则,skill 是 how-to。

## wc_runs 内部(🟡 初步规划 · 跑到再定死)

> 还没最终定,先作为现有 plan 写着;实际跑起来再细化。

| 子目录 | 预期装什么 | 何时长出 |
|---|---|---|
| `data/` | teams / fixtures / results / odds | 开始采集时 |
| `raw/` | raw_web / raw_media | 开始采集时 |
| `rounds/` | 每切一刀一套:timeline + 题库 + 预测 + 成绩单 | 每个切点 |
