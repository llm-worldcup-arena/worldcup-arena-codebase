# processed · 加工成熟数据仓库
> **raw = 未加工**(收集过程留底,按时分切片、只记每次新增);**processed = 加工成熟**(按实体累积的仓库)。

- `match_broadcast/<日期>_<主>_vs_<客>/` — 每场赛事播报(raws原文 + ours我们的版本);做过不 remake。
- `team_news/<队>/<新闻日期>_<源>.json` — 世界杯开赛后(2026-06-11起)各队全部新闻原文,逐条累积;文件名=新闻日期(更有效时间),内含 news_date/published/fetched。
- `prematch_news/<队>/` — 世界杯**开赛前**(≤2026-06-10)发布的新闻。**来历**:开赛前收集时未留全文底,2026-06-13 回头补采——按当时引用的报道逐条重新检索、抓逐字全文入库(非"从旧 raw 提取",旧 raw 没有全文可提)。
- `match_env/<日期>_<主>_vs_<客>.json` — 比赛环境(=比赛+时间+地点三者确定):开球(美东/北京)、场馆(城市/海拔/顶棚)、天气(开球时段,open-meteo)、主裁+VAR(人名,FIFA 指派经 WebSearch 多源)。已踢场次也回填(历史天气可取)。
- `team_coach/<队>.json` — 各队**现任主帅**:① 结构化(姓名/国籍/执教生涯/带过的队;`collect_team_coach.py`,种子=赛前维基) + ② **可读多层简介 `brief`**(`coach_enrich.py` py-Kimi 生成:覆盖结构化 JSON + 融合该队新闻里的教练段落,分点)。换帅经 `--set` 更新(旧任压 history)。下游:match_header 出主帅对位行 + build_user 每队附主帅简介进 prompt。
- `match_referee/<场次>.json` — 各场**主裁**(比赛层人员数据,**独立文件夹、与 team_coach 同规格**):① 结构化(人名/国籍/VAR;`collect_match_referee.py`,FIFA 指派经 WebSearch 多源)+ ② **可读 brief**(`referee_enrich.py` py-Kimi:执法风格/牌量/大赛履历/对本场影响)。下游:match_header 出主裁行 + 执法风格块进预测 prompt。(注:`collect_match_env` 也曾带 referee 字段,2026-06-13 迁出独立成此仓库,prompt 以此为准、回退 env。)

**全文铁律**:本仓库只收**逐字全文**(`original_text` ≥300字、`status=ok`)。被反爬挡下的 blocked 存根不允许滞留——同轮内处理:重抓(Apify 兜底)→ 换源(同故事另一家媒体,`-sub` 后缀)→ 实在无源且已被同主题全文覆盖才删除;所有处置记 `_cleanup_log.md`。

新旧判断:身份键=URL(news)/源名(broadcast)/场次(env),**以本仓库为准**;新的才进 raw 时分目录 + 本仓库。news 全文只走 summary 块A,进块A前 LLM 三判(是否新/要不要/正确性),只增不改(纠错例外记各队 CHANGELOG)。
