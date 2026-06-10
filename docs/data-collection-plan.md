# bg 采集方案 · 完整清单（尽可能全）

- **更新**：2026-06-08（从「只球员层」扩成「BG_DESIGN 全字段」）
- **数据根**：`worldcup_2026/wc_runs/`
- **执行**：一键 `wc_eval/bg_collect/collect_all.py`（规范见 [SKILL](wc_skills/wc-data-collect/SKILL.md)）
- **原则**：一次收集 = 一个快照；raw 整页全文留底；static 死事实 / bg 按 `asof` 快照（见 [BG_DESIGN](BG_DESIGN.md)）

---

## 采集全景（对照 BG_DESIGN · ✅已采 / 🔧待写 / ⏳难）

| 块 | 采什么 | 数据源 | 落哪个文件 | 状态 |
|---|---|---|---|---|
| **1 球队页·整页** | 球员阵容（号/位/生日/俱乐部/caps/goals/队长） | 维基队页·整页 | persons.player + squad | ✅ |
| | 主教练（名字） | 维基队页 infobox | persons.coach + teams.coach_id | ✅ |
| | 世界杯史（夺冠/最佳/参赛数） | 维基队页 | teams | ✅（可从 raw 刷新） |
| | **昵称 / 主场 / 成立年** | 维基队页 infobox（**raw 现成**） | teams | 🔧 |
| **2 排名** | FIFA 当前排名 | 维基 `{{FIFA World Rankings}}` 模板展开 | team_rank | ✅ |
| | Elo | eloratings `World.tsv` | team_rank | ✅ |
| **3 球员·个人页** | 全名 / 出生地 / 身高 / 生涯俱乐部 / 国家队 caps·goals | 维基球员页（**~1250 页**） | persons.player | 🔧 |
| | ⚠️ 惯用脚 = 维基 infobox **无**；球员世界杯出场数 = 正文非 infobox | | | |
| **4 教练·个人页** | 国籍 / 执教生涯 / 带过的队 / 大赛成绩 | 维基教练页（48 人，**页名需消歧**） | persons.coach | 🔧 |
| **5 赛事结构** | 小组赛赛程（date / venue / 对阵） | 维基「2026 FIFA World Cup」· Match schedule / Group | matches.json | 🔧 |
| | 淘汰赛对阵树 + 半区 | 同页 · Bracket 段 | bracket.json | 🔧 |
| | 场地（城市 / 海拔 / 气候） | 同页 · Venues 段 | venues.json | 🔧 |
| | 小组分组 | （已有） | groups.json | ✅ |
| **6 预选赛战绩** | played/won/drawn/lost/gf/ga（**胜负强特征**） | 维基队页 · Qualification 段（raw 已有） | teams.qualifying | 🔧 |
| **7 身价 / 赛季** | 球员身价、阵容总身价、赛季 apps/goals/assists | Transfermarkt / FBref（**非维基**） | player_club / player_season / team_rank | ⏳ TM 反爬；FBref 待探 |
| 中文名 | name_zh（大陆简体） | enwiki → Wikidata `zh-cn` | persons.name_zh | ✅ |

---

## 执行
一键 `python3 wc_eval/bg_collect/collect_all.py`：共用一个时间戳，按块依次跑，raw 落**一个目录 = 一个完整快照**。

## 优先级（BG_DESIGN §7）
1. **强特征 / 刚需**：块 5 赛程对阵、块 6 预选赛、块 2 Elo、块 3 国家队统计
2. **基础完善**：块 1 球队字段、块 4 教练段、块 3 球员档案
3. **冷门可选**：块 7 身价、venues、裁判（默认不收）

## 时效（重要）
- 现在（6 月初）多为**初选大名单**（人数 ≠ 26 正常，非 bug）；赛前定 26 人，**重抓得最终版**，靠 `asof` 快照记录时间差。

---

## 附：API-Football 方案（已弃用，留档）

原计划见 `wc_eval/bg_collect/_attic/collect_bg.py`。试调结论：`league=1` = World Cup 确认存在，但免费档 `/teams?league=1&season=2026` 报错 **"Free plans do not have access to this season, try from 2022 to 2024."** → 免费档拿不到 2026，须升付费档，故弃，改走维基。
