# 世界杯 2026 预测项目 · Codebase 地图

> 一句话：**采集球队资料 → 格式化成"一队一份 summary" → 赛前冻结成 base → 世界杯开打后每场赛后增量更新 → 跟着赛程滚动预测**。
> 给 LLM 喂这些 summary 当背景，预测每场/每轮结果。

---

## 全流程总览

```
①收集数据        ②格式化          ③team_data          ④增量更新(赛后)        ⑤预测(跟赛事)
collect_*.py  →  gen+agent扩写  →  一队一 summary.md  →  collect_match           →  [待做]
(维基/TM/Elo)    update_value      48 队 · 14 列阵容      +WebSearch+integrate       跟世界杯赛程
                                   +8段叙述+近期赛果      只加新踢的、防泄露          每轮预测
     ↓                ↓                  ↓                      ↓                      ↓
  raw 全量留底     data 加工层        team_data/<快照>/      raw/match_reports/      （预测结果评分）
```

---

## ① 收集数据（赛前背景）— skill `wc-data-collect`

| py | 干什么 | 数据源 |
|---|---|---|
| **`collect_all.py`** | **一键总入口**（一次收集=一个快照，命名/落盘写死、自动合规） | — |
| `collect_squads.py` | 球员层·阵容（维基队页整页全文→当前名单） | 维基 |
| `collect_players.py` | 球员个人页（全名/出生地/身高/俱乐部生涯） | 维基 |
| `collect_coaches.py` | 主教练 | 维基 infobox |
| `collect_names.py` | 中文名（大陆简体优先） | Wikidata |
| `collect_transfermarkt.py` | 身价/档案（批量·便宜） | Apify·automation-lab |
| `collect_elo.py` | Elo 排名 | eloratings.net（直连） |
| `collect_fixtures.py` | 小组赛结构 | 维基 |
| `collect_qualifying.py` | 预选赛战绩 | 维基 |

**产出**：`wc_runs/bg/`（persons/teams/matches/venues + snapshots）+ `wc_runs/raw/bg/<ts>/`（全量留底）

---

## ② 格式化 → team_data — skill `wc-data-collect`

| py | 干什么 |
|---|---|
| `gen_summary.py` | 从 data+raw 拼 summary **骨架**（速览/阵容表/近期/征程） |
| *(agent 扩写)* | 每队 1 个 agent 补 8 段叙述（概况/历史/核心球员/动态/定位） |
| `update_summary_value.py` | 把身价补进阵容表 + 末尾「市值段」（幂等，不动叙述） |
| `replace_squad_table.py` | 重刷阵容表（⚠️**慎用**：会冲掉手补内容） |

**产出**：`team_data/<快照>/<队>/summary.md`（每队 14 列阵容表 + 8 段叙述 + 近期赛果 + 市值段）

---

## ③ team_data 版本（快照）

| 快照 | 角色 |
|---|---|
| **`2026-06-08_base`** 🏁 | **基础起点·不可变基线**（赛前·已全量核对·补充档案已并入 14 列主表） |
| `2026-06-10_0228` | 迭代版（往后增量更新用；含 `_persons.json`/`_squad.json` 数据层快照） |
| `2026-06-08_2336` | 原始工作版（过程存档，内容同 base） |

---

## ④ 增量更新（赛后·跟赛事）— skill `wc-incremental-update`

| 步 | py / 动作 | 干什么 | 渠道 |
|---|---|---|---|
| 1 | **`collect_match.py`** | 采"这一场"权威硬数据（比分/进球/阵容/缺阵/控球/xG/射门） | macheta(有xG·第三方) / API-Football(官方·最稳·需key) |
| 2 | *(agent WebSearch)* | 补叙事播报/采访原话/球员评分/伤病解读 | WebSearch/WebFetch |
| 3 | **`integrate_match.py`** | 把这一场**增量**加进两队 summary（近期赛果+1行、⑦伤停）+ raw 留底 | — |

**🚨 防泄露**：只加**已踢完、非待预测**的场次；按预测点出快照 `team_data/<日期>_R<轮>/`；`integrate_match.py` 兜 `date≤today` 校验。

---

## ⑤ 预测（跟世界杯赛程）— **【待做】**

- 跟着世界杯赛程，每轮用「截至该轮开赛前的干净快照」喂 LLM，预测比赛结果（胜平负/比分）。
- 待设计：预测题目格式、评分（参考全局 `predict-*` skills 的 Brier/MAE 思路）、与赛果对照打分。

---

## ⚠️ 代码性质:正式管线 vs 探索（做 codebase 时务必分清）

| 类 | 文件 | 进 codebase？ |
|---|---|---|
| **正式核心管线** | `collect_all`+squads/coaches/elo/names/fixtures、`gen_summary`、`update_summary_value`、`collect_match`、`integrate_match` | ✅ 保留 |
| **独立采集块**（没进一键、已固化进 persons.json） | `collect_players`、`collect_transfermarkt`、`collect_qualifying` | 🟡 待决定（集成进 collect_all / 或标"已固化、不再跑"） |
| **探索性工具**（慎用） | `replace_squad_table`（会冲掉手补，基本弃用） | 🟡 |
| **纯探索·一次性** | `/tmp/*.py`(fetch_full/fetch_mv/gap_check/test_phase_b)、47 个中间 json、**所有 Bash 内联修复脚本**（繁简转换/合并补充档案/全量审查/补身价…执行完即弃、没存文件） | ❌ 不进 |

> **真相**：这一路的修复/补充/核对**绝大多数是探索性临时脚本和内联代码**——完成使命就丢，数据结果已固化在 summary/persons。**codebase = 上面 ✅ 那几个正式管线 + 2 个 skill，仅此而已。**

## 数据目录 & 铁律

```
wc_runs/
├── team_data/<快照>/<队>/summary.md   ← ③ 最终产物（给 LLM 读）
├── bg/                                 ← ② data 加工层(persons/teams/matches…)
└── raw/bg/<ts>/<采集种类>/             ← ① raw 全量留底(只增不改)
```

**铁律**（详见 `CLAUDE.md`）：① raw 只增不改、全量留底、命名到分钟+分子文件夹+`_source.md`；② `base/` 只读；③ 防泄露：summary 不含待预测比分；④ 增量只用 `integrate_match.py` 追加，**绝不重跑 gen/replace/update**（冲掉手补）。

## 🎯 做 codebase 的达标差距（按"可复现"，非"一键"）

> **合格标准 = 正确性·可追溯·防泄露·可重跑·清晰·【可复现】**，不是"一键全自动"。
> **base 当黄金基线固化**（141 处人工精修不强求脚本化）；真正要可复现的是**增量更新 + 预测**。

| # | 有效方法 | 整合结果（已处理，全程未动数据/未重跑） |
|---|---|---|
| 1 | 音译名身价（handsome 链接采） | ✅ 已正式化为 **`collect_tm_byurl.py`**（补充工具；默认只采+留 raw、`--apply` 才写库） |
| 2 | 补充档案合并 14 列 | ✅ 已并进 **`gen_summary`**（直接出 14 列、删单独补充表） |
| 3 | 繁简转换 | ✅ 已并进 **`gen_summary`**（strip_cell 繁→简，297 字、等长守卫） |
| 4 | 近期赛果采集 | 🟡 **判断不脚本化**：赛前一次性、已固化在 base；方法留 skill §4b，赛后改用 `integrate_match` |
| 5 | 同名三层校验 | 🟡 **判断不脚本化**：规则已在 skill §4b、执行含人工判断；base 已校验固化 |
| — | 增量管线串通 | 🟡 待 11 号首场实测（`collect_match`/`integrate_match` 已就位、单测过） |
| — | base 来源说明 | ✅ 见本文「代码性质」+ 本表 |
| 6 | 141 处审查修复 | ✅ **接受固化**：一次性、已在 base，不脚本化 |

> 注：gen 改 14 列后**未重跑任何 summary**（base/0228 数据保持不动）；改动只对**将来**新生成的 summary 生效。
