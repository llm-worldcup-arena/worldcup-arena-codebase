# wc_runs/ — 数据与产物

2026 世界杯多模型预测 benchmark 的数据目录。

## 结构

| 目录 / 文件 | 是什么 |
|---|---|
| `data_reference/` | 基础参考数据(原名 `bg`,2026-06-13 更名):`matches`(赛程 72 场,kickoff_ts 逐场补)/ `persons` / `teams` / `venues`(含坐标/海拔/顶棚) / `static`(分组) / `snapshots`(慢变快照) |
| `data_raw/` | **未加工·收集过程留底**(按时分切片、只记每次新增、只增不改;时分下按种类分 `team_news/`、`prematch_news/`、`match_broadcast/`、`match_env/`、`match_reports/` 等子文件夹 + `_source.md`) |
| `data_processed/` | **加工成熟数据仓库**(按实体累积):`match_broadcast/<场次>/`(每场赛事播报,做过不 remake)· `team_news/<队>/<新闻日期>_<源>.json`(开赛后各队全部新闻)· `prematch_news/<队>/`(世界杯开赛前的新闻,2026-06-13 回头补采全文)· `match_env/<场次>.json`(比赛环境=开球/场馆/天气/裁判)。**全文铁律**:只收逐字全文,blocked 存根必须处理(重抓/换源/删除),处置记 `_cleanup_log.md` |
| `team_data/<快照>/<队>/summary.md` | 48 队档案(版本链快照 `YYYY-MM-DD_HHMM`;块A=原结构吃全部信息,块B=末尾世界杯专项整理;每队 `CHANGELOG.md` 逐轮登记) |
| `predictions/<日期_时分>/` | 每次跑预测的**原始批次**留档:各类 json + `_meta.md` + `_prompts/`(留存的真实 prompt)+ `_unified.json`(合并) |
| `prompt_preview/` | 不调模型的 prompt 成品预览(供开跑前人工审看) |
| **`archive/`** | ★ **官方档案**(网页 + 算分的唯一真源,见下) |

## ★ archive/ — 档案系统(开赛后逐日的核心)

```
archive/
├── predictions.json   预测档案:累加固定预测(赛前全量 + 逐日单场,只增不覆盖)。网页数据由此生成。
├── results.json       现实档案:真实赛果,逐日收集(matches 填比分即可,score.py 自动推各市场)。
└── scorecard.json     算分结果:score.py 把上两档案对照 → 积分榜(网页积分榜由此来)。
```

### 数据流

```
① 跑预测 ───────────→ predictions/<批次>
② 固定写入档案 ─────→ archive_pred.py <批次>  --full(赛前一次) / --daily(逐日单场,累加 matches)
                                                └→ archive/predictions.json
③ 刷新网页 ─────────→ update_web.py [--reveal 6.12]
                        (从预测档案读:只换 PRED + 运行时验证 + cache-bust + 解锁当天)
④ 收集赛果 ─────────→ 填 archive/results.json
⑤ 算分 ─────────────→ score.py
                        (predictions.json × results.json → scorecard.json → 网页积分榜)
```

### 关键原则

- **预测档案只增不覆盖**:逐日单场用 `archive_pred.py --daily` 累加 matches,绝不动赛前已固定的头名/全局/旧场 ——「逐日是增加,不是替换」;
- **网页数据 = 预测档案**:`update_web.py` 一律从 `archive/predictions.json` 读,不再手动转批次;
- **算分 = 两档案对照**:`score.py` 填多少赛果算多少(没填的项不计),可随赛程多次重算;
- 脚本都在 `wc_eval/predict/`(`archive_pred.py` / `update_web.py` / `score.py`),操作规则见 skill `wc-predict`。
