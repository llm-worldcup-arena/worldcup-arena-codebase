# 2026 世界杯预测 — Background 数据结构设计

> **范围**：background(bg)——「人、队、赛事结构」，整个项目的地基。
> **本轮收**：静态档案 + 实体自身 event（球员伤病/停赛/转会；球队换帅/退赛）+ 慢变状态值快照。
> **本轮不收**（留后续）：web/media 舆论内容；**比赛级动态**（赛果/进球/首发/牌，挂在比赛记录上）。
> **约定**：中文说明、英文字段名，JSON 存储，落盘 `ensure_ascii=False`。
> **数据根**：`worldcup_2026/wc_runs/bg/`（整摊 background）；原文 `wc_runs/raw/`；预测层 `wc_runs/rounds/`。

---

## 1. 四条原则

1. **两类数据，分开存。**
   - **死事实**：写一次、永不改（生日、成立年、世界杯历史战绩…）。
   - **会变的值**：随时间动，按 `asof=日期` 快照，有变才出新版（Elo、名单…）。
2. **实体 = 静态档案 + history，一条到底。** person 和 team、venue 一视同仁（coach/referee 都是 person）。
   - 一条记录：前面是**静态档案**（它"是什么"），后面挂 **`history[]`**（它"经历了什么"）。
   - `history` 每条带 `ts`，按时间排，**只追加、不改不删**旧条目。
3. **引用只放 id，不嵌属性。** 比赛放 `team_id`/`person_id`/`venue_id`；详情在各自文件存一份，取信息时 join 一次。绝不把人/队属性嵌进每场比赛（冗余、改一处要改全库）。
4. **id 当主键，绝不用名字。** `person_id`/`team_id`/`match_id`/`venue_id` 串起所有文件；跨数据源、跨中英文译名都靠 id 对齐。

---

## 2. 核心区分：history(事件) vs 快照(状态值)

**整套设计的关键，务必分清。** 两者装的不是同一种东西：

| | 装什么 | 形状 | 存哪 | 取当前值 |
|---|---|---|---|---|
| **history** | 某天**发生一件事** | 离散事件、数量少 | 实体的 `history[]` | 它本就是事件流 |
| **快照** | 某天起**这个数是多少** | 持续数值、一直动 | `snapshots/asof=日/` | 直接读 ≤T 的最新那版 |

- **事件**（受伤/停赛/换帅/退赛/转会）：有明确发生时刻、离散，一个实体一个周期就几条 → 进 `history`。
- **状态值**（Elo/身价/赛季进球/名单）：一直变，塞 history 会堆几百条糊在事件流里 → 单独按 `asof` 快照、有变才出新版。
- **`as_of`**：会变但本轮只灌一次的值（俱乐部/身价/caps）→ 并进实体、标 `as_of` 口径日期；以后要追踪变化，提成 `snapshots/asof` 快照即可，结构不变。
- **`ts`/`asof` 语义 = 信息"何时变得可知"**——为防数据泄漏（预测时刻 T 不能用 T 之后才知道的信息）预留。

---

## 3. 目录结构

```
wc_runs/bg/                       ← 整摊 background
├─ persons.json                   # 人(球员/教练/裁判)：静态档案 + history(伤病/停赛/转会)  ★实体
├─ teams.json                     # 队(48)：静态档案 + history(换帅/退赛)                  ★实体
├─ matches.json                   # 比赛：所有届一张表(edition 分届, result 空=未踢)        ★实体
├─ venues.json                    # 场地：静态属性 + history(翻新/改名)                     ★实体
│
├─ static/                        # ── 纯关系/结构，写一次、无 history ──
│  ├─ groups.json                 #   小组分组(谁和谁)
│  └─ bracket.json                #   淘汰赛晋级图 + 半区(怎么排)
│
└─ snapshots/                     # ── 慢变状态值，按 asof 快照、有变才出新版 ──
   └─ asof=2026-06-08/
      ├─ squad.json               #   26 人名单(person↔team 桥)
      └─ team_rank.json           #   FIFA 排名 + Elo + 阵容总身价
```

三类一眼分清：**实体**（带 history，在根）· **纯关系**（`static/`）· **慢变快照**（`snapshots/asof`）。
- 进 `static/` 的门槛：纯死事实、**自己不经历事件**（分组/晋级图）。某队退赛是记在**那支队的 history**，groups 只跟着改值。
- venues 是实体（会翻新/改名 → 能有 history），故在 `bg/` 根，不在 static。
- 多次采集 = `snapshots/` 下多几个 asof 目录；实体的 history 累积在原文件、不复制。
- raw 原文在 `raw/bg/<日期_时分>/`（整页全文、只增不改）；与 data 分开。

---

## 4. persons.json（实体 = 静态档案 + history）

player/coach/referee **都是 person，一个文件、一人一条**，`roles` 标角色，角色专属字段内联成同名段，没有的角色不写那段。退役转教练 = `roles` 两值、两段并存。

**共有字段（必填）**：`person_id`、`name_zh`、`name_en`、`birthdate`、`nationality`、`roles`、`history`

### `player` 段

| 类别 | 字段 |
|---|---|
| **静态**（写死） | `position`(GK/DF/MF/FW,强特征)、`sub_positions`、`foot`、`height_cm`/`weight_kg`、`wc_appearances`/`wc_goals`、`debut_year`、`club_history`、`is_captain` |
| **as-of 赛前**（会变、灌一次、标 `as_of`） | `club`、`value_m`(身价)、`intl_caps`、`intl_goals`/`intl_assists`、`season{apps,goals,assists,minutes}` |

### `coach` 段
`career_since`、`tenure_with_current_since`、`teams_coached`、`tournament_results[{event,result}]`、`style`、`birth_place`

### `referee` 段
`level`、`association`、`avg_yellow`/`avg_red`、`pen_per_match`、`tournaments`

### 样例
```jsonc
{"person_id":"per_messi","name_zh":"梅西","name_en":"Lionel Messi",
 "birthdate":"1987-06-24","nationality":"ARG","roles":["player"],
 "player":{ "position":"FW","sub_positions":["RW"],"foot":"left","height_cm":170,"weight_kg":72,
            "wc_appearances":26,"wc_goals":13,"debut_year":2005,
            "club_history":["Barcelona","PSG","Inter Miami"],"is_captain":true,
            "as_of":"2026-06-08","club":"Inter Miami","value_m":25,
            "intl_caps":191,"intl_goals":112,"intl_assists":58,
            "season":{"apps":28,"goals":20,"assists":15,"minutes":2400} },
 "history":[ {"ts":"2026-05-01","type":"injury","detail":"腿筋·出战存疑"},
             {"ts":"2026-05-09","type":"injury","detail":"恢复可战"} ]}
```
> `history.type`：`injury`/`suspension`/`transfer`/`status`。`ts` = 该事**何时变得可知**。起步可空 `[]`、结构先留好。
> 赛果/进球这类"关于比赛"的事**不进这里**，挂比赛记录、需要时用 `person_id` 关联。

---

## 5. teams.json（实体 = 静态档案 + history）

| 类别 | 字段 |
|---|---|
| **静态** | `team_id`、`name_zh`/`name_en`、`confederation`、`founded`、`nickname`、`home_stadium`/`style`、`coach_id`(当前主帅·指向 person)、`wc_titles`/`wc_best`/`wc_appearances`、`recent_wc` |
| **as-of**（预选赛已结束=已定格） | `qualifying{played,won,drawn,lost,gf,ga}`（反映近期状态，强特征） |

> 会变的实力评级（FIFA/Elo/阵容身价）**不在这**，放 `snapshots/team_rank.json`。

```jsonc
{"team_id":"ARG","name_zh":"阿根廷","name_en":"Argentina","confederation":"CONMEBOL",
 "founded":1893,"nickname":"潘帕斯雄鹰","home_stadium":"…","coach_id":"per_scaloni",
 "wc_titles":3,"wc_best":"champion","wc_appearances":18,
 "qualifying":{"played":18,"won":12,"drawn":2,"lost":4,"gf":31,"ga":10},
 "history":[ {"ts":"2026-06-06","type":"coach_change","detail":"…"} ]}
```
> 换帅：`coach_id` 记现状、`history` 记"几号换的"，两个都留。`history.type`：`coach_change`/`withdrawal`/`status`。

---

## 6. matches.json（所有届一张表）

`edition` 分届（筛本届/历史），`result` 空=未踢、有值=已踢（本届打完的 + 所有历届）。background 阶段：本届只填赛程结构、`result=null`；历届直接带 `result`。

```jsonc
{"match_id":"M1","edition":2026,"round":"group","group":"A",
 "date":"2026-06-11","kickoff_ts":"2026-06-11T13:00:00","venue_id":"estadio_azteca",
 "team_a":"MEX","team_b":"RSA","referee_id":null,"coach_a":"per_aguirre","coach_b":"per_broos",
 "result":null}                                    // 淘汰赛未定对手用占位符如 "1B"
{"match_id":"WC2022_F","edition":2022,"round":"final","date":"2022-12-18","venue_id":"lusail",
 "team_a":"ARG","team_b":"FRA","result":{"score_90":[3,3],"pens":[4,2],"winner":"a"}}
```

---

## 7. static/（纯关系，写一次）

```jsonc
// groups.json —— 小组分组
{"A":["MEX","RSA","KOR","CZE"],"B":["…"]}
// bracket.json —— 晋级图 + 半区
{"R32":[{"slot":"1A","from":"winner_A"}],"halves":{"top":["1A","2B"],"bottom":["1C","2D"]}}
```

## 8. venues.json（实体，key = venue_id）

```jsonc
{"estadio_azteca":{"name":"Estadio Azteca","city":"Mexico City",
   "altitude_m":2240,"climate":"high_altitude","surface":"grass","history":[]}}
```

## 9. snapshots/asof=日/（慢变快照，只增不改）

```jsonc
// squad.json —— 26 人名单(person↔team 桥)
{"ARG":{"players":[{"person_id":"per_messi","no":10,"pos":"FW","club":"Inter Miami"}]}}
// team_rank.json —— FIFA + Elo + 阵容身价(Elo 比纯 FIFA 排名预测更准,务必收)
{"ARG":{"fifa_rank":3,"elo":2114,"squad_value_m":null}}
```

---

## 10. 连接方式（全靠 id）

比赛不写人名队名、写 id；取信息时拿 id 去对应文件 join 一次。

| 文件 | 字段 | 指向 |
|---|---|---|
| teams | `coach_id` | persons |
| matches | `referee_id`、`coach_a`/`coach_b` | persons |
| matches | `team_a`/`team_b` | teams（淘汰赛未定=占位符） |
| matches | `venue_id` | venues |
| snapshots/squad | 顶层 key / `person_id` | teams / persons |
| static/groups | 列表值 | teams |

> 同一支队出现在几十场比赛里，每场嵌一份，改个名/更新 Elo 就要改几十处必然对不上 → 详情各存一份，比赛只放 id。

---

## 11. 灌库校验（铁律）

1. **关系只存一个权威方向，反向靠查。** `squad` 存 `team→[person]`；查"某人在哪队"扫 squad，**不在 persons 另存 national_team**（双向存必不一致）。
2. **引用完整性**（写入前跑 fk-check 扫全库、断链报错）：每个 `coach_id`/`referee_id`/`coach_a`/`coach_b`/squad 的 `person_id` → persons 必有；每个 `team_a`/`team_b`/squad key/groups 值 → teams 必有；每个 `venue_id` → venues 必有。占位符（如 `"1B"`）是合法未解析值，解析成真 `team_id` 后才纳入校验。
3. **`ensure_ascii=False`**（中文不存成 `\uXXXX`）。
4. **每类 JSON 配 schema 校验**，写入前 validate，避免字段拼错静默污染。
5. **静态写一次；快照有变才写、只增不改、永不原地 UPDATE；history 只追加不改旧条目。**

---

## 12. 采集优先级

1. **强特征/刚需**：球队 `Elo + 预选赛表现`；球员 `国家队生涯 + 当前赛季状态`；`groups`/`bracket`（出题直接依赖）。
2. **基础**：身份档案、FIFA 排名、squad、俱乐部/身价、世界杯史、赛程结构。
3. **做对应题才用、先留字段**：裁判执法统计、venues 海拔气候、history 事件、历届赛果。

**时间界（当前 ≈ 2026-06）**：档案/历史/赛程/分组现在即可抓；26 人正式名单赛前才陆续锁定，等 FIFA 锁定后存首个 `squad` 快照。
**采集执行**（数据源、维基方法、各采集器）见 [`wc_skills/wc-data-collect`](wc_skills/wc-data-collect/SKILL.md)。
