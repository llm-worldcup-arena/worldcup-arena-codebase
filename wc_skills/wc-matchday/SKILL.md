---
name: wc-matchday
description: 世界杯比赛日一键跟进。py 入口 wc_eval/matchday.py 把全流程串成带参数的"按钮"(参数控制:是否推web/是否预测/是否跑播报等)。所有 LLM 判断/生成走 py 调 DMXAPI 顶尖 Kimi(wc_llm.py),换个对话也能复现。用户说「跟进比赛 [参数]」即按本 SOP 执行。
---

# 世界杯 · 比赛日一键跟进(matchday.py = 带参数的按钮)

**一句话**:`python3 wc_eval/matchday.py [参数]` 把全流程的 py 步骤串起来;**所有 LLM 判断/生成都在 py 里调 Kimi**(wc_llm.py),不是对话里临场做 → 谁跑都一样、可复现。

## 🎛 按钮参数(用户要求"按钮有参数")

| 参数 | 作用 | 默认 |
|---|---|---|
| `--ts` | 本轮时分(raw/快照/批次共用) | 当前时分 |
| `--snapshot` | 喂哪个快照预测 | team_data 最新 |
| `--settle A-B,..` | 要结算的已完赛场次 | 空 |
| `--news 1/0` | 跑 news_pipeline(py-Kimi 三判) | 1 |
| `--coach 1/0` | 跑 coach_enrich(48队教练可读简介) | 0 |
| `--env A-B,..` | 刷新环境(天气/裁判)的场次 | 空 |
| `--plong 1/0` | 为已收集 raws 的播报生成可预测版 long | 0 |
| `--predict A-B,..` | 要预测的场次(空=不预测) | 空 |
| `--audit 1/0` | 预测前跑 LLM 快照终审官(语义把关) | 1 |
| `--review 1/0` | 对已结算且有预测的场跑赛后复盘官 | 1 |
| **`--push-web 1/0`** | **是否把预测+积分榜推到网页**(外发动作,需显式开) | **0** |
| `--reveal 6.13` | 配 --push-web,解锁网页到某日 | 空 |
| `--env-workers N` | 环境刷新按场并发数 | 6 |
| `--coach-workers N` | 教练简介队伍并发数 | 16 |
| `--news-workers N` | 新闻三判队伍并发数 | 10 |
| `--broadcast-workers N` | 赛事播报采集/合成按场并发数 | 3 |
| `--predict-workers N` | 预测按场并发数;每场内部仍并发 6 模型 | 2 |

**「跟进比赛」= 全自动推网页**:`matchday.py --settle ... --news 1 --coach 1 --env ... --plong 1 --predict ... --push-web 1 --reveal <日>`
**「跟进数据」= 只更新不推**:同上但 `--predict "" --push-web 0`。

## 全流程(matchday.py 编排;LLM 步骤全 py 调 Kimi)

```
⓪ 找 URL(检索步,唯一需 agent/WebSearch 的环节)——**两类都要找全(播报不是旁支,是"全部信息"的一类)**:
    a) 新闻 URL → collect_team_news 抓全文进 raws(全 48 队;身份键=URL 判重,只抓新的;见 wc-incremental-update)
    b) 赛事播报源 URL → 为【本轮新结算的每一场】WebSearch 找 3-5 个权威赛报(T1/T2 优先,见 wc-match-broadcast),
       写进 data_raw/<ts>/_broadcast_urls/<Mid>.json;matchday ⑤ 自动抓取→合成→嵌入(无需手动跑 fetch_sources)。
    (这一步在 matchday.py 之前/之外)
① 结算   --settle:integrate_match → results.json → score.py(积分榜)
② 环境   --env:collect_match_env --refresh(天气+裁判)→ referee_enrich(裁判可读材料)
③ 教练   --coach:coach_enrich(48队;结构化 JSON + py-Kimi 可读多层简介,覆盖JSON+融合新闻)
④ news三判 --news:news_pipeline(对每队本轮新抓的 ok 新闻,py-Kimi:clean_loop 清洁循环 + 三判)
            → 无新增的队【自动跳过、不动 summary】;有新闻才 LLM 判(新?要?对?)→ 进⑦
⑤ 播报   broadcast_round.py(自动):为【每一场已结算但还没做播报的场】跑整条线 ——
            fetch_sources 抓⓪b 的源 → broadcast_synth 合成 ours(long/short/timeline)→ 归档 → 嵌进两队 summary 块B。
            开关 config/wc_pipeline.json: auto_run_match_broadcast(2026-06-19 起默认 on)。--plong 仍可单独补可预测版。
⑥ 复盘   --review:review_round(已结算且有预测的场 → 6模型误差分析 → archive/reviews.json)
⑦ 预测   --predict:news_preflight + **broadcast_preflight(每已结算场必有播报)** + verify_kickoffs + preflight(机械体检)
            + --llm-audit(快照终审官,有泄露/矛盾就拦)→ predict_match × 每场 → merge_batch → archive_pred --daily
⑧ 推送   --push-web:update_web --reveal → (git push 中性作者,手动确认)
            update_web 会同步做前端 UI 契约检查:已结算淘汰赛竞猜卡列表显示比分;未结算已确定对阵显示阶段;未定对阵显示暂定。
```

## 并行策略

- `collect_news_auto.py` 本身已支持 `--workers`,负责 48 队新闻 URL 自动发现 + 抓取并行;它仍在 matchday 之前/之外跑。
- `matchday.py` 对互不依赖的阶段做受控并行:环境按场并行,教练/新闻把 workers 传给子脚本,播报按场并行,预测按场并行。
- `--predict-workers` 不宜过大:`predict_match.py` 每场内部已并发 6 个被测模型;日常建议 `2`,API 稳定时可试 `3`,遇到限流/超时降到 `1`。
- 播报采集/合成建议 `--broadcast-workers 3`;太高会同时打 Apify、网页抓取和 Kimi 合成,收益不线性。

## 几条铁律(都已固化在 py,不靠对话记忆)

- **先判断再生成**:没有新信息的队**不重新生成 summary**(news_pipeline 自动跳过)。有新闻才触发三判。
- **三件套(新?要?对?)**:`wc_llm.judge_news`——① is_new 对照仓库+⑦判新;② should_add 只收伤停/停赛/名单/首发/状态拐点;③ is_correct ≥2源/归属/时效。**不同种类信息都触发,关键步骤(如赛果)可触发两次**(整合时 + 终审时)。
- **清洁循环**:`wc_llm.clean_loop`——所有收集到的文本进 summary 前,LLM 判脏不脏/废话多不多 → 修 → 复检,**最多 3 轮**。
- **全队伍 + 并行**:每轮收集都是全 48 队;小数据(教练/环境/天气/播报)并行采、py-Kimi 并行判(线程池 8-10)。
- **赛事播报 = 全部信息收集的一类(2026-06-19 接进主流程,修复"播报漏采"bug)**:matchday ⑤ 的 `broadcast_round.py` 自动为【每一场已结算但没做播报的场】跑完整条线(fetch_sources 抓⓪b 的源 → broadcast_synth 合成 → 归档 → `wc2026_build.append_block_b` 嵌进两队块B);唯一需 agent 的是 ⓪b 找源 URL。开关 `config/wc_pipeline.json: auto_run_match_broadcast`(默认 on)。**硬门禁 `broadcast_preflight.py`**:预测前强制"每已结算场都有 ours/long.md + 两队块B 均已嵌",不达标拒预测(防这条线再被悄悄跳过)。**延后特性**:赛后信息约 3h 才全,先跑一遍、更全后 `broadcast_round --refresh` 补;做过的场不 remake。
- **可预测版 long**:`predictable_long`——long 的"硬信息全留、情感高度概括"版;块B 优先取它(`long_predictable.md`),原 long 保留。
- **summary 后面(块B)不止放播报**:还放 赛前/通用动态、对本队影响、(可扩展)其它世界杯专项;见 wc-team-wc2026。
- **LLM 调用统一走 wc_llm.py**(DMXAPI 顶尖 `Kimi-K2-Thinking`);**被测的 6 个模型**走 llm_client.chat_search(另一回事)。**监督质量**:终审官/三判可能误报(如把"近期状态客场对手比分在前"的约定误判为矛盾),结论需抽样核。
- **开球时间核对(防"西部时区场把美东时间算错",已犯两次:AUS-TUR午夜 / 6-15西雅图·亚特兰大)**:预测前 matchday 的 ⑦.0 自动跑 `predict/verify_kickoffs.py`——交叉核对 **FIX(网页显示源)↔ matches.json(预测prompt源)** 美东时间一致 + venue 城市→时区反推【当地开球时刻】合理性 + **非美东场(PT/CT/MT)一律标"务必外部核对"**(FIX↔matches 不一致或当地越界则硬拦)。⚠️ 自动核对挡不住"貌似合理的错值"(如西雅图 12pm↔3pm 都像真)——**最终防线 = agent 每轮 WebSearch 权威赛程(FIFA/CBS/Al Jazeera)核对【当地↔美东】换算**,绝不盲信网页 FIX 表里人工填的美东值。
- **网页 reveal 自动化(2026-06-15 改)**:预测卡解锁不再靠手动 `--reveal` bump——前端 `isRevealed()` 按**今日美东**自动揭晓当天及之前【有真预测数据】的场;`REVEAL_THROUGH` 降级为"手动提前揭晓更晚日期"的可选覆盖。
- **竞猜卡列表尾标自动化(2026-06-29 固化)**:`update_web.py` 注入 `RESULTS` 后,前端必须自动把【已结算淘汰赛】尾标显示为比分(如 `0:1`),和小组赛完场行一致;【未结算但已确定对阵】显示阶段(如 `32 强`);【未确定对阵】显示 `暂定`。这条有 `update_web.py` UI 契约检查,不能靠手工页面修。

## 防泄露(贯穿)

- 只结算/整合**已踢完**的场;待预测场及其之后的结果**绝不进 summary/prompt**;
- 带搜索的预测**只在开球前跑**;终审官(--llm-audit)再兜一道语义级泄露排查。
