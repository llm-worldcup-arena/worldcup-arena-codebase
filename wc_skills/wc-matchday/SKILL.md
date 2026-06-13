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

**「跟进比赛」= 全自动推网页**:`matchday.py --settle ... --news 1 --coach 1 --env ... --plong 1 --predict ... --push-web 1 --reveal <日>`
**「跟进数据」= 只更新不推**:同上但 `--predict "" --push-web 0`。

## 全流程(matchday.py 编排;LLM 步骤全 py 调 Kimi)

```
⓪ 找新闻 URL(检索步,唯一需 agent/WebSearch 的环节)→ collect_team_news 抓全文进 raws
    (全 48 队;身份键=URL 自动判重,只抓新的。这一步在 matchday.py 之前/之外,见 wc-incremental-update)
① 结算   --settle:integrate_match → results.json → score.py(积分榜)
② 环境   --env:collect_match_env --refresh(天气+裁判)→ referee_enrich(裁判可读材料)
③ 教练   --coach:coach_enrich(48队;结构化 JSON + py-Kimi 可读多层简介,覆盖JSON+融合新闻)
④ news三判 --news:news_pipeline(对每队本轮新抓的 ok 新闻,py-Kimi:clean_loop 清洁循环 + 三判)
            → 无新增的队【自动跳过、不动 summary】;有新闻才 LLM 判(新?要?对?)→ 进⑦
⑤ 播报   --plong:predictable_long_gen(long→可预测版);新踢的场 broadcast_synth(raws→ours,见下)
⑥ 复盘   --review:review_round(已结算且有预测的场 → 6模型误差分析 → archive/reviews.json)
⑦ 预测   --predict:preflight(机械体检)+ --llm-audit(快照终审官,有泄露/矛盾就拦)
            → predict_match × 每场 → merge_batch → archive_pred --daily
⑧ 推送   --push-web:update_web --reveal → (git push 中性作者,手动确认)
```

## 几条铁律(都已固化在 py,不靠对话记忆)

- **先判断再生成**:没有新信息的队**不重新生成 summary**(news_pipeline 自动跳过)。有新闻才触发三判。
- **三件套(新?要?对?)**:`wc_llm.judge_news`——① is_new 对照仓库+⑦判新;② should_add 只收伤停/停赛/名单/首发/状态拐点;③ is_correct ≥2源/归属/时效。**不同种类信息都触发,关键步骤(如赛果)可触发两次**(整合时 + 终审时)。
- **清洁循环**:`wc_llm.clean_loop`——所有收集到的文本进 summary 前,LLM 判脏不脏/废话多不多 → 修 → 复检,**最多 3 轮**。
- **全队伍 + 并行**:每轮收集都是全 48 队;小数据(教练/环境/天气/播报)并行采、py-Kimi 并行判(线程池 8-10)。
- **赛事播报自动化 + 延后**:新踢的场 raws 齐了 → `broadcast_synth`(py-Kimi:raws→long/可预测long/short/timeline);**信息约 3 小时后才全**,故播报是【延后步】(赛后即结算,播报隔几小时补)。开关 `config/wc_pipeline.json: auto_run_match_broadcast`。
- **可预测版 long**:`predictable_long`——long 的"硬信息全留、情感高度概括"版;块B 优先取它(`long_predictable.md`),原 long 保留。
- **summary 后面(块B)不止放播报**:还放 赛前/通用动态、对本队影响、(可扩展)其它世界杯专项;见 wc-team-wc2026。
- **LLM 调用统一走 wc_llm.py**(DMXAPI 顶尖 `Kimi-K2-Thinking`);**被测的 6 个模型**走 llm_client.chat_search(另一回事)。**监督质量**:终审官/三判可能误报(如把"近期状态客场对手比分在前"的约定误判为矛盾),结论需抽样核。

## 防泄露(贯穿)

- 只结算/整合**已踢完**的场;待预测场及其之后的结果**绝不进 summary/prompt**;
- 带搜索的预测**只在开球前跑**;终审官(--llm-audit)再兜一道语义级泄露排查。
