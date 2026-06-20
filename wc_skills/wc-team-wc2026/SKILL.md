---
name: wc-team-wc2026
description: team_data 每队 summary.md 末尾的「世界杯2026 专项整理」段(块B)的生成与维护——先分比赛(每场=我们自己的赛事播报 long+逐分钟 timeline+对本队影响)、最后赛前/通用动态。块B 只放内容不放说明文字。与 wc-incremental-update(块A=原结构吃全部信息)配套;赛事播报由 match_broadcast 子项目供给(单一真源,做过不 remake)。
---

# 世界杯 · team_data 块B（summary 末尾「世界杯 2026 · 专项整理」段）

**一句话**：块A（summary 前面各节，原结构）**吃全部新信息**；块B（summary **最末尾一段**）把其中**世界杯相关**的再统一整理一遍——以"我们自己的赛事播报"为主体。

## 块B 结构（py：`bg_collect/wc2026_build.py` 的 `append_block_b`）
```
## 世界杯 2026 · 专项整理
### 🏟 <日期> · <轮次> · <主/客/中> vs <对手>（<比分 胜/负/平>）   ← 先分比赛,每场一节
  #### ①比分速览 ②进球与关键事件 ③红牌争议 ⑤数据现场 ⑥赛后采访 ⑦看点    ← 我们的赛事播报(取 long 叙事)
  #### 逐分钟时间线                                                  ← timeline(精简、形式独特,一并带)
  **对本队后续的影响**：…                                            ← 停赛/伤情对下一场的直接影响
### 📋 赛前 / 通用动态                                               ← 不属于某场的:伤停/状态/下一场指引
```
- **🚫 块B 里只放内容,不放说明文字**——"取自哪里 / 块A块B怎么分工 / raw 在哪留底"这类 meta 注记一律不进 summary(教训:曾把'(看多源后我们自己的版本,取自 match_broadcast/.../long.md)'写进正文);规则只写在本 skill。
- 维护性行(macheta/待 Apify/data.json 指针)摘录时自动过滤(`_MAINT`)。

## 赛事播报版本怎么选（实测判断）
| 版本 | 是否带入块B | 理由 |
|---|---|---|
| `long.md` | ✅ 主体（去 ④阵容长名单、去来源/存疑脚注，##→#### 降级） | 信息最全，但**不是全覆盖**（无完整名单/全统计） |
| `timeline.md` | ✅ 一并带（~1-2KB） | 精简且**形式独特**（一眼看全场脉络），long 替代不了 |
| `short.md` | ❌ 不带 | 纯 long 的浓缩，**无信息增量**，带了只是重复 |
| `data.json` | ❌ 不带（机器用） | 完整 26 人名单+全统计在此；块A/评测按需读 |

## 与 match_broadcast 的融合（单一真源，做过不 remake）
详见 [`wc-match-broadcast`](../wc-match-broadcast/SKILL.md)「并入主流程」（子项目位于 `wc_runs/data_processed/match_broadcast/`）：没做过→自动完整跑；做过→新信息**扩充 raws + LLM 判断**有实质增量才改 ours；该场 raws **归档进 `data_raw/<收集时分>/match_broadcast/<场次>/`**（块A 吃所有信息，主项目 raw 必须完整；`archive_broadcast_raws()` 幂等只增）。
**块B 现由 `bg_collect/broadcast_round.py` 自动构建(2026-06-19 起,matchday ⑤ 调)**:它对每队【所有已踢场】调 `append_block_b` 从 ours 单一真源重嵌(轮次/主客中/比分视角/影响 全自动算,可复现),不再 agent 手搓 `played`。开关 `config/wc_pipeline.json: auto_run_match_broadcast`(默认 on);硬门禁 `broadcast_preflight.py` 预测前强制每已结算场都嵌好。

## 配套纪律
- 每条带**日期+来源**；多数权威一致→直接陈述（不夹"谁记多少"）；真分歧只进 long 文末「存疑」。
- 改动逐条记该队 `CHANGELOG.md`（`changelog_util.append_change`，块A/块B 共用）。
- 不新建快照时就地更新（开发期固定 `2026-06-13_0247`）；新轮次用 `snapshot_round.py` 复制最新版再做。
