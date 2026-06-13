---
name: wc-incremental-update
description: 世界杯开打后的「赛后增量更新」——每场比赛结束，增量采集该场权威信息（比分/阵容/缺阵/统计/xG + 叙事播报），增量更新进两队 summary，供 LLM 滚动预测下一场。强调"增量"：在 base 起点之上只加新踢的比赛，绝不重做全量、绝不泄露未踢比分。
---

# 世界杯 · 赛后增量更新（Incremental Update）

**一句话**：世界杯开打后，**每踢完一场 → 只把"这一场"的新信息增量加进两队 summary**，base 起点不动、不重做全量，供 LLM 预测下一场。

> **本 skill = 块A**(summary.md 原结构增量:赛果进近期状态、停伤进⑦关键动态——保持精炼、直接喂预测)。
> **块B**(每队 `wc2026/` 世界杯专属详细块:赛后播报/伤停/状态…多文件)由 [`wc-team-wc2026`](../wc-team-wc2026/SKILL.md) 维护,**别把块B详细内容倒灌进 summary**。
> **每队 `CHANGELOG.md`**(监督用,每队一份):块A/块B 所有改动都用 `bg_collect/changelog_util.py` 逐条登记。

- **增量 = 链式**：每轮在 **team_data 最新日期版本的副本** 上加，**不是每次从 base、更不重跑全量**。
- **版本链**：`base`(赛前) →复制→ `2026-06-12_1252` →复制→ `2026-06-15_<时分>` … 每个新快照 = **复制上一个最新版 + integrate 本轮新踢的比赛**；起点 `base` 永久不动。
- 🚨 **快照命名铁规 = `YYYY-MM-DD_HHMM`(日期_时分,与预测批次同规范)** 或基底 `YYYY-MM-DD_base`；`snapshot_round.py` **强制校验**,`_R1`/`_rerun` 之类花名直接报错。"本轮第几/含哪些已踢"写进 `_snapshot.md` 说明,不进目录名。

---

## 🚨 第一铁律：防泄露

要预测的那场 **及其之后** 的任何结果，**绝不能进 summary**——否则等于把答案告诉模型，benchmark 作废。

- 只增量 **已踢完、非待预测** 的场次；
- 按预测点出快照 `team_data/<日期>_<时分>/`（每个快照 = 该轮开赛前的干净信息）；
- `integrate_match.py` 再兜一道 `date ≤ today` 硬校验。

---

## 🔬 第二铁律：信息核实（写进 summary 前必做）

🚨 **任何增量信息，必须 ≥2 个独立源交叉验证、确认无误，才能写入。**

**反例教训（ter Stegen 事件 · 2026-06-10）**：一次综合搜索说"ter Stegen 缺席"，顺手当成**西班牙**门将加进 ESP —— 实际他是**德国**门将（缺的是德国队）。**张冠李戴，正是 benchmark 最怕的数据污染**；多源核实才挡得住。

**核实三查**：
1. **多源**：≥2 个独立来源（ESPN / SI / FotMob / Goal / 官方…）说同一件事；单源、转述、社媒不算；
2. **归属**：确认人物属于**哪队 / 哪国**、职位对不对（防张冠李戴）；
3. **时效**：是当前的、非旧闻（看日期）；确认赛前 / 已踢（防泄露）。

核实通过 → summary 标「多源核实」+ 列来源；**不通过 → 不加**。

- **赛前 / 赛中文字动态（伤病 / 停赛 / 退赛 / 名单）**：
  0. 🔎 **找源有成文依据（不许临场乱编）**：检索词用标准模板（`collect_team_news.py --suggest --team <码> [--opp <码>]` 打印；= 队名+World Cup 2026+主题词 injury/squad/lineup+对手/日期锚点，**中/英都搜**）；选源按 **NEWS_TIERS 分层名单**（T1 官方/AP/路透 → T2 ESPN/Sky/FOX/CBS/NBC/Yahoo/Goal → T3 RotoWire/SportsMole/当地大报/中文 网易·新浪·直播吧），**每队≥3-5源、T1/T2优先、≥2源交叉**；避开 live/导视页。名单与模板**写死在 py 里**，谁来跑都一样。
  1. 🗄️ **先 raw 全量留底（铁律，别再只写摘要）**：把选中的 URL 写进 `urls.json`，跑 `python3 bg_collect/collect_team_news.py --team <码> --asof <日> --ts <时分> --urls <json>` → **逐字全文**存进 `data_raw/<时分>/team_news/<队>/`（复用 match_report 抓取 + Apify 兜底 + 质量门）。
     - **新旧判断（身份键=URL）**：历史已抓过的 URL **默认跳过**（不重复落盘、不建空抽屉，并提示原件在哪个时分目录）；`--refresh`（或条目 `"refresh": true`）强制重抓=**重拍快照**，只用于"内容会更新的实时页"（如 ESPN 伤停追踪）。与 match_broadcast 增量归档同一思路：**每份原文只在"它被收集的那个时分目录"出现一次**。
     - **全文铁律（processed 不留存根）**：被反爬挡下的 `status=blocked` 记录**当轮处理完**——重抓（Apify 兜底，逐条慢跑避并发限流）→ 换源（同故事另一家媒体，文件名 `-sub` 后缀）→ 已被同主题全文覆盖/确无替代源才删除；所有处置记 `data_processed/_cleanup_log.md`。
  2. 🧠 **news 全文 → 只进 summary 块A（原结构），进之前 LLM 三判**（块B 的赛事播报由 match_broadcast 供给，news 不直接进块B）：
     - 🚨 **三判走 py，不靠对话临场做(2026-06-13 定)**：`bg_collect/news_pipeline.py`(调 `wc_eval/wc_llm.py` 的 DMXAPI 顶尖 Kimi)——对每队本轮新抓(fetched==ts)的 ok 新闻,**先 `clean_loop` 清洁循环(脏不脏/废话多不多 → 修,≤3轮),再 `judge_news` 三判**,过则追加进 ⑦ + 记 CHANGELOG。队内多条、队间都并行(线程池)。**换个对话也能跑 `python3 news_pipeline.py --snapshot <快照> --ts <ts> --teams ALL`**。
     - **是否新**：对照 `data_processed/team_news/<队>/`（文件名带新闻日期）+ summary ⑦ 已写——已写过的不重复写；
     - **要不要加**：对预测下一场有用才加（伤停/停赛/名单/首发/状态拐点）；花絮/赔率/纯预热不进；
     - **正确性**：≥2 源交叉、人物归属（哪队哪国）、时效（防旧闻防泄露）。
     三判通过 → 按原结构落位（赛果进近期状态、伤停进⑦…），标「多源核实」+ 列来源。**触发口径**:不同种类信息都触发三判,关键步骤(如赛果)可触发两次(整合时 + 终审官复查时)。**没有新信息的队 → 不动 summary**(news_pipeline 自动跳过)。
     - **质量监督**:Kimi 三判/终审官可能误报(实测把"近期状态客场对手比分在前"的命名约定误判为矛盾)——结论需抽样核,别盲信。
  3. ➕ **只增不改**：所有更新都是**追加**形式；**唯一例外=发现既有内容是错的**（如 ter Stegen 张冠李戴）才允许修正旧条目，且必须记入该队 `CHANGELOG.md`（改了什么、为什么、依据哪些源）。
  - **核实是判断活、靠 agent 把关，不靠脚本计数**——数来源数量挡不住张冠李戴（ter Stegen 那次填俩错源照样过），真正要做的是「判断这人属于哪队」。
  - 🌍 **每轮收集范围 = 全部 48 队（不只比赛队,别忘）**：
    - **比赛队(本轮要踢/刚踢)= 深抓**：news 多源 + 赛事播报(match_broadcast) + 比赛环境(见下)；
    - **非比赛队 = 轻扫 news**：队伍没比赛,但新闻照样有(伤病恢复/训练/场外)——每轮 48 队都过一遍 news 更新,新 URL 才落盘(仓库挡重复),无新增也在 CHANGELOG 记一笔。
  - 🌦️ **比赛环境（开球/海拔/天气/裁判 = 比赛+时间+地点 三者确定）**：每场赛前跑
    `python3 bg_collect/collect_match_env.py --home <主> --away <客> --ts <时分>`
    → 双写 `data_processed/match_env/<场次>.json`(仓库) + `data_raw/<时分>/match_env/`(过程)。
    天气=open-meteo 开球时段(临近开球 `--refresh` 刷新;**已踢场次也回填**——open-meteo 取得到近期过去日期)；裁判=主裁人名(FIFA 指派公告经 WebSearch 多源后 `--referee "名(国籍)" [--var "VAR名(国籍)"]` 写入,ESPN/Athlon/Scotsman 等转载即算源)；开球时间/海拔/顶棚并入同一份。**`match_header()` 自动读仓库 → 环境行(天气+主裁/VAR)进预测 prompt**。
  - 👔 **主教练(队伍层人员,与裁判同款待遇)**:成熟仓库 `data_processed/team_coach/<队>.json`(48 队已种子化,种子=赛前维基采集);每轮 news 若发现**换帅/代理**(≥2 源)→
    `python3 bg_collect/collect_team_coach.py --team <队> --ts <时分> --set "新帅(国籍)" --src "..."`(旧任自动压 history,只增不改)。**`match_header()` 主帅对位行自动进预测 prompt**。
  - 🔭 **收集口径与顺序（彻底做好）**：分两步走——
    1. **先「自己收集」这一轮**：之前的普通检索源【一个不能少】(WebSearch 多语种 + 各新闻源),先把本轮该采的采齐(raw 全文留底 → 块A ⑦ + 块B)。
    2. **这一轮完成后,再按 `match_broadcast` 的力度(10-13 源)补**：把我们自己的赛事播报接进块B。融合机制(详见 [`wc-match-broadcast`](../wc-match-broadcast/SKILL.md)「并入主流程」)：该场**没做过→自动完整跑**子项目;**做过→绝不 remake**,本轮检索到的**新**播报信息→原文扩充进该场 `raws/` + **LLM 判断**有实质增量才改 ours;该场 `raws/` 同时归档进 `data_raw/<收集时分>/match_broadcast/<场次>/`(**要写入主项目 raw——块A 吃所有信息,raw 必须完整**)。开关 `auto_run_match_broadcast` 默认 off(只复用已有)。
    - 别一上来就奔 13 源;**先自己收集完整,再叠加 match_broadcast**。
- **赛后单场硬数据**：`collect_match`(macheta) 是结构化数据源、相对可靠；但其叙事 / 伤病解读字段仍须按上面三查核实。

---

## 渠道分层（实测 2026-06，按稳定性排）

| 层 | 信息 | 首选渠道 | 稳定性 |
|---|---|---|---|
| **权威硬数据** | 比分/进球/牌/阵容/缺阵/统计 | **API-Football**（官方 API，世界杯全覆盖，需免费 key）<br>或 **macheta**（Apify，第三方抓取，**带 xG**） | 官方 ⭐⭐⭐ / Apify ⭐⭐ |
| **xG 预期进球** | xG / xGOT | **macheta**（API-Football 的 xG 弱） | ⭐⭐ |
| **文字** | 叙事播报 / 采访原话 / 球员评分 / 伤病解读 | **WebSearch / WebFetch** | ⭐⭐⭐ |

- **最稳做法 = 多源交叉**：API-Football（主）+ macheta（补 xG / 互相校验）+ WebSearch（文字）；**比分/统计两边对不上就标 ⚠️ 警告**。
- 专业站（ESPN/Sofascore/FBref）**直连反爬 403**，别用 WebFetch 试；它们的数据被新闻引用，WebSearch 能间接拿。

---

## 版本链（轮级：每轮先复制最新版，再往副本里加）

🚨 **每轮增量都在「最新日期版本的副本」上做，绝不在旧版本 / base 上直接改。**

```
base(赛前) ─复制→ R1 ─复制→ R2 ─复制→ R3 …
预测R1用          预测R2用       预测R3用
(无世界杯正赛)    (+R1已踢)      (+R2已踢)
```

每轮三步：
1. **复制最新版** → 新快照：`python3 snapshot_round.py --name 2026-06-15_1400`（自动找 team_data 最新日期版、cp 成新快照 + `_snapshot.md`）
2. 对本轮**已踢完**的每场，跑下面「三步流程」，`integrate_match --td 2026-06-15_1400` 加进**这个新快照**
3. 预测下一轮：LLM 只读这个新快照（干净、含截至本轮的所有已踢结果、不含待预测场）

## 三步流程（每场赛后）

```
① collect_match.py   ── 采"这一场"的权威硬数据(比分/进球/阵容/缺阵/控球/xG/射门)，py 全自动
② 1 个 agent WebSearch ── 补叙事/采访/评分/伤病解读，写回 ① 留的 6 个空位
③ integrate_match.py ── 把这一场【增量】加进两队 summary(近期赛果+1行、⑦伤停) + raw 留底 + 防泄露
   (2026-06-13 起:队名自动解析 macheta 英文名→FIFA 码;伤停 dict 条目按 side 分边防张冠李戴;自动记两队 CHANGELOG)
```

**命令**：
```bash
# ⓪ 本轮开始：复制最新版 → 新快照（版本链；自动找 team_data 最新日期版）
python3 snapshot_round.py --name 2026-06-15_1400
# ① 采（先按日期+队名找 matchId，再采）
APIFY_TOKEN=xxx python3 collect_match.py --date 11/06/2026 --team Mexico        # 列出当天比赛+id
APIFY_TOKEN=xxx python3 collect_match.py --match <id> --date 11/06/2026 \
    --comp "世界杯·A组" --ha 中 --ts 2026-06-11_2300 --out /tmp/m.json
# ② agent WebSearch 补 m.json 的 injuries/suspensions/ratings/quotes/narrative/prediction_note
# ③ 增量整合进 summary
python3 integrate_match.py /tmp/m.json --ts 2026-06-11_2300 --today 2026-06-11 --td 2026-06-12_1252
```

---

## 铁律

- **绝不重跑 gen / replace_squad_table / update_summary_value**——base 的大量修复在 summary、不在 persons，重跑会冲掉（登贝莱行/年龄/叙述订正）。**增量只用 `integrate_match.py` 追加**。
- **raw 全量留底** `data_raw/<ts>/match_reports/`（macheta 的 `raw_game_data` ~120KB 整存）+ 每次 `_source.md`。
- Statistics 的 Type 是 365scores 编号（见 `collect_match.py` 的 STAT 表，推断映射）；以 raw 全量为准可校准。
- 升级路径：拿到 API-Football 免费 key 后，把它作为硬数据主力（更稳）、macheta 退为 xG 补充与校验。
