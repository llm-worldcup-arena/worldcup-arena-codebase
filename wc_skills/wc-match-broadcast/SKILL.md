---
name: wc-match-broadcast
description: 世界杯每场比赛的「多源赛事播报」流水线——CC 找权威源 + fetch_sources.py 直抓逐字原文（内置质量门，必要时 Apify 绕反爬）+ CC 交叉合成两个给人看的产物 long（最全最广）/ short（简要）。独立于 bg/预测线，只借用 wc_runs。每踢完一场跑一遍。
---

# 世界杯 · 多源赛事播报 流水线（Match Broadcast Pipeline）

**一句话**：每踢完一场 → **找权威源 → 直抓逐字原文 →（可选 Apify 补）→ 合成 long+short**。

- **独立流水线**：与 bg 采集 / 增量更新 / 预测**互不混**，只借用 `wc_runs/` 存。
- **只用两样工具**：① CC 自己联网（WebSearch 找源 + urllib 直抓原文）；② **Apify**（绕反爬抓顶级源、macheta 硬数据）。**不用 DMXAPI**。
- **原文是底线**：raws 存网页**逐字赛报正文**（机械抽取、不经任何模型）。

```
① 定位+找源(CC)  →  ② 抓原文(py)            →  ③ Apify补(可选)        →  ④ 合成(CC)
matches.json      fetch_sources.py            website-content-crawler     读 raws 全部原文
WebSearch 权威源   直抓HTML+质量门→raws/*.json  自动兜底 + harddata.py硬数据   → long/short/timeline/data.json
```

---

## 存储结构（每场一文件夹：`<date>_<HOME>_vs_<AWAY>`）
```
wc_runs/data_processed/match_broadcast/<date>_<HOME>_vs_<AWAY>/
├── raws/<source>/<source>.json   ← 每源一文件夹一 JSON，original_text=逐字赛报正文（只增不改）
└── ours/                          ← 我们做的产物（给人看，非原文），7 种：
    ├ long.md / short.md / timeline.md       叙事全本 / 简版 / 逐分钟时间线
    ├ data.json                              结构化数据卡（harddata.py·macheta 自动生成）
    └ promo_report.md / promo_predict_pre.md / promo_predict_post.md   社媒宣传版（结合 AI 预测，promo.py 自动生成预测两版）
```

---

## 源 · 权威分层（找源时**按此优先**，这是「更权威」的关键）
| 层 | 媒体 | 直抓现状（urllib，2026-06 实测） |
|---|---|---|
| **T1 官方/通讯社** | **FIFA 官方**、**AP 美联社**、**Reuters**、各国足协 | AP✅(经转载站) · FIFA🟥(JS App,需Apify) · Reuters🟥(爬虫屏蔽) |
| **T2 顶级体育/主流** | **ESPN**、**Sky**、**FOX**、**CBS**、**NBC**、**beIN**、**Al Jazeera**、BBC、Guardian、Yahoo | Sky✅ FOX✅ NBC✅ beIN✅ AlJazeera✅ · ESPN🟥/Yahoo🟥(JS/429,需Apify) · BBC/Guardian🟥(爬虫屏蔽) |
| **T3 地方大报/聚合/中文** | La Nación、Crónica、El Espectador、RPP、World Soccer Talk；**中文**：网易/新浪/直播吧/中华网 | 多数✅可直抓（中文站注意 GBK 编码、清中文页脚） |

> **第三方转发（repost）也用**：被反爬挡的权威源（AP/路透/BBC）常被别站**原文转载**，抓转载站即可拿到——如 **AP 原稿经 KKTV 转载**已直抓到、**中文站多为转载**（网易转、新浪转直播吧、新京报转央视）。找源时可专门搜「<权威社名> + 转载/据…报道」。

- **优先抓 T1/T2**；T3 补语种/视角多样性与交叉。
- ⚠️ **找 URL 避开直播/导视页**：链接里带 `live / en vivo / minuto a minuto / live-score / liveblog / how to watch / cómo ver` 的多是**电视推广/直播流**，正文全是订阅价、转播台，**不是赛报**（教训：Outlook 那条 `original_text` 全是"Welcome to live coverage…INR 799"）。挑 `report / crónica / highlights / 标题即比分` 的文章页。

---

## 步骤详解

### ① 定位 + 找源（CC）
1. `wc_runs/data_reference/matches.json`：`match_id → date / team_a / team_b / group`，**只做已踢完（有最终结果）的场次**——不是只看 date：同一天的晚场当天可能还没踢（如 6/12 的 CAN-BIH/USA-PAR），`harddata.py` 跑出 macheta 比分 `-1--1` 即未踢，先等结果。
2. `WebSearch`（**中/英/西多语种**都搜，覆盖更广），按上表挑 T1/T2 优先的**赛报文章** URL。
3. 写 `urls.json`：`[{"name","source","url","tier","lang"}]`（name=源 slug，作 raws 子文件夹名）。

### ② 抓原文（py）— `wc_eval/match_report/fetch_sources.py`
```bash
python3 fetch_sources.py --match <id> --urls urls.json
```
它做的事（全机械、不经模型）：直抓每个 URL 原始 HTML → **优先取出版方 JSON-LD `articleBody`**（最干净）→ 抓不到退「去 script/导航 + 抽 <p> 段落」→ **质量门**（见下）→ 干净赛报存 `raws/<name>/<name>.json`。

### ③ Apify（`APIFY_TOKEN` 已配，存 `config/secrets.local.json`）
- **顶级源原文**：FIFA 官方 / ESPN / Yahoo（JS App、urllib 抓回空壳）→ fetch_sources.py **直抓被挡时自动用 `website-content-crawler` 兜底**（无需另跑）。
- **硬数据 →（同时是产物 data.json）**：跑 **`python3 harddata.py --match <id>`**（Apify **`macheta`**，复用 [collect_match.py](../../wc_eval/bg_collect/collect_match.py)）→ `raws/apify_macheta/harddata.json` + `ours/data.json`。**自动试比赛日±1（365scores 按 UTC、晚场算次日）+ 队名首词**；**未踢守卫**：macheta 比分 `-1--1`/无阵容 → 判未踢、不生成。

### ④ 合成产物（CC）—— `ours/`，三种给人看的播报
读 `raws/` 全部源 JSON（+ harddata），写：
- **`ours/long.md`（全本·最全最广）**：①比分速览 ②进球与关键事件(按分钟) ③红黄牌/争议 ④阵容/换人/教练 ⑤数据与现场 ⑥赛后采访 ⑦看点纪录 + 来源 + 存疑。
- **`ours/short.md`（短版）**：~300-600 字球迷向速览，流畅叙述、不堆来源标注。
- **`ours/timeline.md`（逐分钟战况时间线）**：关键事件按分钟排（⚽进球🟥红牌🅥VAR🔄换人🥅扑救），直播复盘体——最贴「播报」的形态。
- **`ours/data.json`（结构化数据卡）**：比分/射手/红黄牌/首发/控球/射门/xG，机器可读（给网站/评测）。**由 `harddata.py`（Apify macheta）自动生成、非手写**。

**社媒宣传版（小红书/抖音，钩子+emoji+话题标签）：**
- **`ours/promo_report.md`（赛事播报·宣传版）**：CC 由 long/short 提炼的创意社媒战报。
- **`ours/promo_predict_pre.md` + `promo_predict_post.md`（AI 预测·宣传版 = 没看到结果版 / 看到结果版）**：由 **`python3 promo.py --match <id>`** 自动生成——读 web `worldcup_2026_web/site/worldcup-data.js`（6 模型 7 盘口预测）+ `ours/data.json`（实际比分），算**共识**（赛前版）与**各模型命中/满分**（赛后版），出社媒文案。**结合了我们的 AI 预测**。

---

## 质量门（fetch_sources.py 内置，自动执行）
1. **整源弃用**：头部含 `live coverage / telecast / INR / Kick-off time / cómo ver…`（直播/电视推广页）→ 删目录、不留进 raws。
2. **截尾**：正文之后的 `Rate the players / In pictures / minuto a minuto / 电视转播 / 版权 / Instagram-TikTok 社媒 / Con información de` 等一律截掉；去嵌入推文、开头署名；结尾去残句。
3. **`<300 字` = 反爬挡** → 标 blocked、不留，待 Apify。

## 合成铁律
以原文为准并标来源；**≥2 源交叉**，单源/矛盾标「⚠️ 存疑」；**权威源(T1/T2)优先采信**；**防张冠李戴**（核对人物哪队/哪国，教训见 bg 线 ter Stegen）；原文没有的不编造、标「待 Apify 补」。
- 🚫 **别把"已定"写成"不确定"**：权威**多数一致**(≥2 源同值、无同级多数反对)→ 正文**直接陈述定值**，不夹"（X 记 67'；Y 记 66'）"这类注记（教训：MEX-RSA 曾写"FIFA+Sky+DD 确认 67'；仅 AP 记 66'"——三家权威一致还摆出不确定的样子）。**真分歧**（权威各执一词、无多数）→ 正文取多数/主依源的**单一值**，分歧只集中写在文末「存疑」段；timeline 行内也不夹注。

## 并入主流程（融合机制）
本子项目已**真正接进** matchday 自动流程(2026-06-19 接线 = `bg_collect/broadcast_round.py`,由 matchday ⑤ 调;此前只有 `broadcast_synth` 散步骤、未串成主流程,导致 6/15 起播报漏采的 bug)。**子项目文件夹不变 = 赛事播报类信息的单一真源**,规则:
0. **找源 URL 是 agent 在 ⓪b 做的**(WebSearch 权威赛报,写进 `data_raw/<ts>/_broadcast_urls/<Mid>.json`,与 team_news 的 URL 发现同构)——这是唯一需 agent 的环节;其余(抓→合成→归档→嵌块B)全 py、`broadcast_round.py` 自动串。
1. **没做过**（该场无 `ours/long.md`）→ `broadcast_round` 自动:`fetch_sources`(读 ⓪b 的 urls)抓原文→`broadcast_synth` 合成 long/short/timeline→`archive_broadcast_raws` 归档→`wc2026_build.append_block_b` 把该队**所有已踢场**重嵌块B(从 ours 单一真源生成,可复现)。
2. **做过 → 直接复用、不重搜(2026-06-21 改为增量)**。`broadcast_round` 每轮**只收没做过的场(刚结算的)**,做过的场(有 `ours/long.md`)直接跳过,**不再每轮重新搜索/扩充**(那样太慢)。确需补全/重抓该场 → 手动 `broadcast_round --slug-only` 或 `broadcast_synth --refresh`。嵌块B 也增量:只重嵌**本轮新收集场**涉及的队(`--embed-only`/`--refresh` 才全嵌)。
3. **raw 写入主项目（增量归档,版本语义勿破坏）**：子项目按【场次】累积、data_raw 按【采集时刻】切片——`archive_broadcast_raws()` 只归档**尚未在 data_raw 任何时分出现过的源** → 每个源文件只在【它被收集的那个时分目录】出现一次：首次收集→全部源进当时时分；1 小时后再来(扩充了新源)→**只有新源进新时分目录**，旧源绝不重复归档、也绝不混进旧时刻目录。没有新源 → 不建目录。
4. 开关 `config/wc_pipeline.json` 的 `auto_run_match_broadcast`（**2026-06-19 起默认 on**）：on=按上面自动跑与扩充；off=只**复用已有**(不跑不扩充)。**硬门禁 `bg_collect/broadcast_preflight.py`**:预测前强制"每已结算场都有 ours/long.md + 两队块B 均已嵌",不达标拒预测。

---

## 现状（2026-06-12）
- ✅ 2 场已完成（均 long+short+timeline+**data.json**）：
  - `2026-06-11_MEX_vs_RSA`（**13 源**：FIFA官方/AP/Sky/beIN/FOX/NBC + WST/Crónica/Diario + **中文×4** 网易×2/新浪/中华网）+ macheta 硬数据。
  - `2026-06-11_KOR_vs_CZE`（**10 源**：FIFA官方/Sky/半岛 + La Nación/El Espectador/RPP + **中文×4** 网易×2/新浪/大纪元）+ macheta 硬数据。
- ✅ **`APIFY_TOKEN` 已配**：FIFA 官方（JS App、urllib 只回空壳）已用 `website-content-crawler` 抓到；macheta 硬数据（控球/xG/完整阵容）已补。ESPN（整日专栏非专稿）/Yahoo（串稿）经核验弃用。
- ⏳ **CAN-BIH、USA-PAR（6/12 晚场）当天未踢完**：`harddata.py` 跑出 macheta 比分 `-1--1` 即未踢，流水线已就位，等结果出来一键跑。
