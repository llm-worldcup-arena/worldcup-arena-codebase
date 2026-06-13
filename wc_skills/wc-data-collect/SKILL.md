---
name: wc-data-collect
description: 世界杯2026 bg背景数据采集规范——命名规则、数据分层、各数据源策略、维基采集方法与字段schema。采集或更新球队/球员/排名等 bg 数据时遵循此规范。
---

# 世界杯 2026 · bg 数据采集规范

本文件是 bg（背景）数据采集的**唯一规则源**。代码（`wc_eval/bg_collect/`，总入口 `collect_all.py`）是**执行臂**，照此实现；**改规矩改本文件，代码跟着改**，不在脚本里另立规则。

数据根：`worldcup_2026/wc_runs/`

## 1. 数据分层（整摊 background 在 `data_reference/` 下(原名 `bg`,2026-06-13 更名)，按"会不会变"三分）

| 层 | 装什么 | 路径 |
|---|---|---|
| **实体** | persons/teams/matches/venues —— 静态档案 + `history[]`（事件） | `data_reference/`（根） |
| **纯关系** | groups（分组）/ bracket（晋级图）—— 写一次、无 history | `data_reference/static/` |
| **慢变快照** | squad / team_rank —— 会变数值，按 asof 拍快照、只增不改 | `data_reference/snapshots/asof=<日>/` |
| **raw** | 未加工**整页全文原文**留底 | `data_raw/<日期_时分>/`（一次采集一目录） |

- **核心区分**：离散**事件**（伤病/换帅/转会/退赛）→ 进实体的 `history[]`；持续变的**数值**（Elo/身价/名单）→ `snapshots/asof` 快照。
- **`as_of`**：会变但本轮只灌一次的值（俱乐部/身价/caps）→ 并进实体、标 `as_of` 口径日期。
- **`ts`/`asof` 语义 = 信息"何时变得可知"**（防数据泄漏：预测时刻 T 不用 T 之后才知的）。
- raw 存原文、data 存加工，**两者分开**；raw 只增不改、**永远整页原文**。

## 2. 命名规范（重点）

| 对象 | 规则 | 例 |
|---|---|---|
| **raw 采集目录** | `data_raw/<日期_时分>/<采集种类>/` —— **带分钟**；一次采集一目录，**按采集种类分子文件夹** + 每次留 `_source.md` 来源说明 | `…_1059/transfermarkt/`（旧维基目录混装为历史例外） |
| **data 快照目录** | `data/bg/asof=<日期>/` —— 按日（快照=截至某日，**不带分钟**） | `data/bg/asof=2026-06-07/` |
| 球队 | FIFA 三字码 | `ESP` `FRA` `ARG` |
| 球员/教练 id | `per_<英文名小写、去重音、空格转_>` | `per_lamine_yamal` |
| raw 文件 | `<三字码>.<后缀>`，一队一文件 | `ESP.wikitext` |

- raw 目录时分由代码 `run_ts()` = `datetime.now().strftime("%Y-%m-%d_%H%M")` 自动生成，**每次采集一个新目录**。
- 所有 JSON 落盘 `ensure_ascii=False`（中文/重音原样）。

## 3. 数据源策略

| 数据 | 来源 | 方法 |
|---|---|---|
| 球员阵容（名单/号码/位置/生日/俱乐部/caps/goals）**+ 主教练** | 各队维基主页**【整页全文】** | 直连维基 API 抓整页 → **同一份原文**解析阵容段 + infobox 教练 |
| **FIFA 当前排名** | 维基 `{{FIFA World Rankings\|<码>}}` 模板 | `action=expandtemplates` 展开取数字（整页 wikitext 里是模板、**无明文当前排名**） |
| **Elo** | eloratings.net/`World.tsv` | 静态文件直连（Elo 比 FIFA 排名预测更准，做主特征） |
| **中文名** | enwiki → Wikidata | `name_en`→Q 号→`zh-cn` 大陆简体标签（**队**中文名 48 队已手补进 `teams.name_zh`） |
| **球员身价/惯用脚/合同/伤病** | Transfermarkt（经 **Apify** 平台 Actor） | Actor `jungle_synthesizer/transfermarkt-global-football-player-scraper`，`searchQuery` 搜球员名 → `market_value_eur`/`foot`/`contract_until`/`injuries`（详见 §4b） |
| API-Football | **免费档拿不到 2026**，已弃用（留档 `bg_collect/_attic/`） | — |

> 经验：WebFetch 返回的是加工结果**非原文、且只某段**；要真 raw 须直连源站抓**整页全文**（世界杯史/主场/近期阵型都在整页里，以后挖字段不重采）。

## 4. 维基采集方法（关键坑）

1. **合规 UA 必须**：`User-Agent` 标用途+邮箱；**浏览器伪装（Mozilla）会被 `403 Too Many Reqs`**。
2. **抓整页全文**：`action=parse&page=<页>&prop=wikitext`（**不带 section**）→ 整页源码；再用正则截 "Current squad" 段（标题后到下一个**同级**标题前），**只在段内找球员**，免得混入 "Recent call-ups" 等同样用 `{{nat fs}}` 的段。
3. **`redirects=1`**：跟随重定向（如南非队页是重定向，否则全空）。
4. **FIFA 当前排名靠 expandtemplates**：`action=expandtemplates&text={{FIFA World Rankings|<码>}}` → 展开后**第一个数字 = 当前排名**，括号里日期 = `fifa_asof`（48 队可拼成一次请求、按分隔符切回）。
5. **解析** `{{nat fs g player|no=|pos=|name=|age={{birth date and age|y|m|d}}|caps=|goals=|club=}}`：括号配平提取整块、顶层 `|` 切分、`[[A|B]]→B`、`{{sortname|名|姓}}→名 姓`、生日取 y/m/d；队长 = `other/captain` 含 captain 且非 vice。
6. **教练**：整页含 infobox，取 `| manager =`（值读到**行尾**，因含链接 `|`）→ 去 flagicon → 人名。
7. **人数 ≠ 26 是正常的**：初选大名单/伤退，属真实名单阶段，**非 bug**；赛前重抓得最终 26（靠 asof 快照记录时间差）。

## 4b. Apify 第三方采集（身价等 —— raw 全量 + 分子文件夹 + 来源说明）

维基没有的字段（身价/惯用脚/合同/双国籍/转会史）经 **Apify**（知名网页抓取平台）现成 Actor 补。**两步铁律**：
1. **raw 全量留底 + 分子文件夹**：Actor 返回的【完整 JSON】一字不改存 `data_raw/<ts>/<采集种类>/`（**按采集种类分子文件夹**，如 `transfermarkt/tm_<队>.json`），并写 `_source.md` 记来源/方式/字段（**每次采集都留说明**）；空结果也留。
2. **再从 raw 提取**进 data —— **提取从宽**（多留 `tm_*` 字段免遗漏），想补别的（转会史/经纪人…全在 raw）回 raw 再挖，不重采。

- **Actor**：`automation-lab/transfermarkt-scraper` —— `searchQueries` **数组批量、一次运行采全队**，**$0.005/运行 + ~$0.003/人 → 48 队约 $2.6**（远比单查的 `jungle_synthesizer`($0.1/人, 字段含 injuries 但贵) 划算）。
- **token 安全**：`APIFY_TOKEN` 从**环境变量**读，**绝不写进代码 / 不提交 git**（凭证）。
- **同名校验（三层，缺一不可）**：① TM `dateOfBirth` ⨯ 维基 `birthdate` 比**出生年份** → 不符 = TM 同名搜错 `tm_verified=false`、剔除 TM。② 同名搜错会**污染整条维基记录**（full_name/position/birth_place/国脚数都成了错人的，**不只 TM 字段**）→ `tm_verified=false` 的人要逐个核实 位置/全名/出生地/国脚数，写 `*_verified` 字段由 gen 覆盖。③ **同名合并**：squad 按名字 slug 化 `person_id`，同名不同人会被**合并成一个 id** → 查「`person_id` 被多个 (队,号) 引用」即合并，从名单 wikitext(含 `pos/age/caps/club`) 拆回真人（如 BRA 两个 Ederson、URU 中场 Martínez 与 ARG 大马丁；污染大马丁的 Toranza/Punta del Este 正是 URU 那个真中场的）。
- **不一致以更权威源为主（经独立源核对修正）**：身价/合同/惯用脚 → **TM**；**出生日期 → TM**（维基爱把日/月颠倒，如 Toni Fruk 04-09 实为 03-09）；**身高大差异(≥10cm) → 独立源核实**（TM 易抓错同名人，反而维基/官方更准，如 Antonisse 真 177）；出生地/中文名/详细生涯/球队历史 → 维基；认人以维基生日为锚。
- **独立第三方核对法**：Sofascore/官方 API 被反爬封死(403)，热门 actor 多只采**比赛数据、不采球员档案页** → 改用 **WebSearch 读多独立源**(FBref/ESPN/FotMob/UEFA/俱乐部官网/各国足协)交叉判定，**绝不拿维基当裁判**（它是被核对对象）。差异大的真疑点逐个核(性价比高)；差异小的(身高 3–9cm)是测量口径差、不值得核。
- **TM 采集盲区(实测)**：automation-lab 搜索对**韩文/阿拉伯/中亚音译名彻底无效**（孙兴慜/Kim Min-jae 都搜空，换搜索词也没用）→ KOR/EGY/中东/UZB 这些队 TM 补不了，直接 **WebSearch 批量补第二源**（多 agent 并行、按队分组、写 `height_cm_verified`）。并发采集还会**丢整队**（timeout/异常，如 MAR/NED 整队没文件）→ 采完务必**按队核对覆盖率**，漏的重采。单源排查记得**排除主教练**（不在 squad.players、无需档案）。
- **音译名队的身价怎么补(实测通)**：① WebSearch `<name> transfermarkt` 找每人 TM 页的**数字 id**（8 agent 分队并行，命中 100%）→ ② 用 `handsome_apostrophe/transfermarkt-scraper-v2` 的 `playerUrls`、**slug 占位** `transfermarkt.us/x/profil/spieler/<id>` 批量采（**并发 4、每批 12**；40 个/批会超 250s）→ `market_value_numeric` 精确(身价 80%→99%)。注意该 actor 的 **foot/height/club 字段解析错位、不可用**，惯用脚改用 WebSearch 读。身价直读 WebSearch 不行（动态估值，€50m/€15m 会混）。**→ 此法已正式化为补充工具 `collect_tm_byurl.py`（`--tmids ids.json`，默认只采+留 raw，`--apply` 才写库）。**
- **防泄露**：身价非赛果、`marketValue` 带更新日（标 asof）、确认赛前。
- **球队近期赛果(近期状态)**：Sofascore actor 采不了按队赛果（azzouzana 球队页也 NO data、macheta `FIXTURES` 是按日期不按队、id 体系还对不上）→ 用 **WebSearch 按队采近 8-10 场**（48 队 agent 并行、约 467 场），日期/主客/对手中文名/比分/性质(友谊·世预·欧国联)，替换 summary「近期状态」段。**防泄露铁律**：只要 **≤ 当日已踢完**的（世界杯 6-11 开幕），代码再兜一道剔除 `date≥开幕日` 或 type 含「世界杯/World Cup」的。
- 其他源（已探）：天气 `cloud9_ai/open-meteo-scraper`（**球场属性、不绑队伍**）、xG `parseforge/fbref-scraper`、SofaScore/FlashScore（实时比分，泄露风险高慎用）。

## 5. 字段 schema（完整见 [BG_DESIGN.md](../../BG_DESIGN.md)，这里给要点）

**bg/persons.json**（实体·一人一条 = 静态档案 + history）：
```jsonc
{"person_id":"per_xxx","name_zh":"","name_en":"","birthdate":"…","nationality":"ESP","roles":["player"],
 "player":{ /*静态*/ "position":"MF","foot":"left","height_cm":170,"club_history":[],"is_captain":false,
            /*as-of*/ "as_of":"2026-06-08","club":"…","value_m":null,"intl_caps":40,"intl_goals":5,"season":{} },
 "history":[ {"ts":"2026-05-01","type":"injury","detail":"…"} ]}   // 事件: injury/suspension/transfer
```
**bg/teams.json**（实体 + history）：`team_id/name/confederation/founded/nickname/home_stadium/coach_id/wc_titles/wc_best/wc_appearances/qualifying{played,won,drawn,lost,gf,ga}` ＋ `history[]`（换帅/退赛）
**bg/matches.json**（所有届一张表）：`match_id/edition/round/group/date/venue_id/team_a/team_b/referee_id/coach_a/coach_b/result`（本届 result=null）
**bg/venues.json**（实体）：`{venue_id:{name,city,altitude_m,climate,surface,history:[]}}`
**bg/static/**：groups `{A:[team_id…]}`、bracket `{R32:[{slot,from}],halves:{}}`
**bg/snapshots/asof=日/**：squad `{ESP:{players:[{person_id,no,pos,club}]}}`、team_rank `{ESP:{fifa_rank,elo,squad_value_m}}`

## 6. 执行（代码 = 执行臂）

**一键总入口** `collect_all.py` —— 一次收集 = 一个完整快照（共用一个时间戳，raw 落一个目录）：
```bash
python3 wc_eval/bg_collect/collect_all.py                          # 全 48 队：整页全文→球员+教练+FIFA+Elo+中文名
python3 wc_eval/bg_collect/collect_all.py --only ESP,ARG           # 测几队
python3 wc_eval/bg_collect/collect_all.py --only ESP --skip-names  # 测试跳过（较慢的）中文名
```
单独 / 补充采集器：
```bash
python3 wc_eval/bg_collect/collect_squads.py [--only ESP|--from-raw]   # 球员阵容 + 球队字段
python3 wc_eval/bg_collect/collect_players.py [--only ESP|--limit 20]  # 块3 球员个人页(~1250页,慢)
python3 wc_eval/bg_collect/collect_qualifying.py                       # 块6 预选赛战绩→teams.qualifying
APIFY_TOKEN=xxx python3 wc_eval/bg_collect/collect_transfermarkt.py [--only ARG]  # 块7 身价/惯用脚/合同/双国籍(Apify automation-lab,批量~$2.6全量,见§4b)
APIFY_TOKEN=xxx python3 wc_eval/bg_collect/collect_tm_byurl.py --tmids ids.json   # 块7补:音译名队身价(automation-lab搜不到的→WebSearch找id→TM链接采,见§4b)
python3 wc_eval/bg_collect/update_summary_value.py [--only ARG]              # 块7后:身价补进 team_data 阵容表+「球队市值段」(幂等,不动叙述)
python3 wc_eval/bg_collect/collect_elo.py   /   collect_names.py
python3 wc_eval/bg_collect/gen_summary.py [--only ARG] [--ts <时分>]   # 整合 bg → team_data/<ts>/<队>/summary.md（供LLM预测，见§8）
```
> `collect_all` 含：整页(球员+教练详情+球队字段)·FIFA·Elo·中文名·赛程(matches/bracket/venues/groups)。
> `collect_players` / `collect_qualifying` / `collect_transfermarkt` 较慢/花钱、独立跑(前提 teams.json 已由 collect_all 建好)。

## 7. 待办 / 难采（字段都已留好，采到再填，采不到留 null/空）

- **身价 / 惯用脚 / 合同 / 双国籍 / 转会史**：✅ Transfermarkt（Apify automation-lab 批量，§4b）已通，**全量约 $2.6**（48 队）→ `update_summary_value` 补进 summary
- **球队总身价 / 平均年龄**：✅ 由球员身价汇总（update_summary_value 的「球队市值段」，$0）
- **球场海拔 / 气候**：venues 字段（**球场属性，不绑队伍**）；待另采（Open-Meteo 等）
- **history 事件**（伤病/停赛/转会）：TM 已带 `injuries`/`suspensions`/`career_history`（在 raw 里），**待结构化进 `history[]`**；换帅维基无表
- **同名张冠李戴**：维基阵容链接消歧错（如「大马丁」串成他人档案）→ TM 生日校验 `tm_verified=false` 可揪出，**待批量重定位修**
- **裁判** referee、**历届比赛**（matches `result`）：做对应题再采，字段已留
- teams：**世界杯史**已能从队页 Honours 段解析（gen_summary）；**中文队名 48 队已补**
- 预选赛 `qualifying`：CONMEBOL 已通；UEFA/CAF/AFC 各洲 table 结构不一，**采到多少算多少**
- 中文名仍缺约 340（小国球员 Wikidata 无 `zh` 标签）

## 8. team_data —— 队伍背景资料（供 LLM 预测）

从 bg 各源整合出**每队一份** `team_data/<日期_时分>/<三字码>/summary.md` ——「以队伍为载体」的赛前全量背景，喂 LLM 做比赛预测（预测时**只读这一份**，故所有信息都内联进来）。

- **生成（三步）**：
  1. `gen_summary.py [--only X]` —— 从 data + raw 拼 **data 骨架**（速览/世界杯战绩/近期/本届征程/**14 列阵容表**：号·位·名·全名·年龄·身高·脚·国脚·身价·合同·双国籍·加盟·生涯·出生地，**补充档案已并入主表、港译繁体自动转简体**）；
  2. **每队一个 agent 扩写**（workflow 并行，参照标杆队如 CAN）—— 读队页 raw（History/Honours/Rivalries/Results）深挖，**用 Edit 原地补** ①概况②历史③近4年⑥核心球员⑦关键动态⑧综合定位 等叙述段（**保留骨架表格不动**）；
  3. `update_summary_value.py [--only X]` —— Transfermarkt 身价**补进阵容表身价列** + 末尾追加「球队市值与年龄结构」段（**幂等、绝不动叙述**）。
- **内容（8 段，中位约 4000 字）**：速览 / ①概况 / ②历史与世界杯战绩 / ③近4年表现 / ④本届征程 / ⑤阵容全名单(**14 列**：号·位·名·全名·年龄·身高·脚·国脚·**身价**·合同·双国籍·加盟·俱乐部生涯逐段·出生地) / ⑥核心球员 / ⑦关键动态 / ⑧综合定位 ＋ 球队市值段。
- **铁律**：① 数值用 data 锁死**不编**、可回溯 raw；② **不含赛事结果**（防泄露；2026 本届别误写成"已出局/止步"，未踢就是未踢）；③ 后续补字段（身价等）**只追加、不删叙述**（update 脚本幂等）。

## 9. 世界杯期间「赛后增量更新」

→ 见独立 skill **`wc-incremental-update`**：世界杯开打后，每场赛后**增量**采集（API-Football / macheta 硬数据 + WebSearch 文字）并增量整合进两队 summary，含渠道分层、防泄露铁律、`collect_match.py` + `integrate_match.py` 两步。**本 skill（wc-data-collect）只管赛前 base 的全量生成。**
