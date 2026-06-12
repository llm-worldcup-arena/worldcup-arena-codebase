---
name: wc-incremental-update
description: 世界杯开打后的「赛后增量更新」——每场比赛结束，增量采集该场权威信息（比分/阵容/缺阵/统计/xG + 叙事播报），增量更新进两队 summary，供 LLM 滚动预测下一场。强调"增量"：在 base 起点之上只加新踢的比赛，绝不重做全量、绝不泄露未踢比分。
---

# 世界杯 · 赛后增量更新（Incremental Update）

**一句话**：世界杯开打后，**每踢完一场 → 只把"这一场"的新信息增量加进两队 summary**，base 起点不动、不重做全量，供 LLM 预测下一场。

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

- **赛前 / 赛中文字动态（伤病 / 停赛 / 退赛 / 名单）**：agent 按上面三查**核实无误后，直接编辑对应队 summary 的 ⑦段**（标「多源核实」+ 列来源）。**核实是判断活、靠 agent 把关，不靠脚本计数**——数来源数量挡不住张冠李戴（ter Stegen 那次填俩错源照样过），真正要做的是「判断这人属于哪队」。
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
- **raw 全量留底** `raw/bg/<ts>/match_reports/`（macheta 的 `raw_game_data` ~120KB 整存）+ 每次 `_source.md`。
- Statistics 的 Type 是 365scores 编号（见 `collect_match.py` 的 STAT 表，推断映射）；以 raw 全量为准可校准。
- 升级路径：拿到 API-Football 免费 key 后，把它作为硬数据主力（更稳）、macheta 退为 xG 补充与校验。
