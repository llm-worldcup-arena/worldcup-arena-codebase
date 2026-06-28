# 预测模块（CODEBASE ⑤）

6 家旗舰模型(经 DMXAPI · `wc_eval/llm_client.py`)读 `team_data` 的 summary 做预测,赛后对照真实赛果打分 → 前端积分榜。

## 评测对象（`models.json`，实测可调通 2026-06-10）

| 显示名 | DMXAPI 模型 |
|---|---|
| Claude | claude-opus-4-8 |
| GPT | gpt-5.2 |
| Gemini | gemini-3.1-pro-preview |
| Kimi | kimi-k2.5 |
| GLM | glm-5 |
| Seed | doubao-seed-2-0-pro-260215 |

## 两种预测

### A. 全量预测（赛前一次 · `predict_global.py`）
开赛前,每个模型读 48 队 summary,一次性预测整届走向:

| 维度 | 分值 | 预测 |
|---|---|---|
| 夺冠 | **+10** | 1 支冠军 |
| 进决赛 | **+3 / 队** | 2 支决赛队 |
| 四强 | **+2 / 队** | 4 支四强 |
| 夺冠大洲 | **+2** | 冠军来自哪洲(欧洲/南美/…) |
| 总进球 | **+2** | 整届总进球 **大 / 小**(盘口 285.5) |

### B. 逐日预测（赛中滚动 · `predict_daily.py`）
跟赛程,每个预测点用 `snapshot_round` 出的**当轮最新快照**,预测接下来的比赛。
**【待定·需确认】** 逐日预测的具体维度:每场胜平负?具体比分?当日多场打包?

### C. 淘汰赛阶段新增步骤（不改旧预测流）
淘汰赛先跑新增脚本解析已确定对阵，再继续使用原来的单场预测链路。

```bash
# 先看清楚哪些场已能落地、哪些第三名分配还需人工指定
python3 wc_eval/predict/resolve_knockout.py --dry-run

# 写入已确定的对阵:matches.json + 网页 knockout 表
python3 wc_eval/predict/resolve_knockout.py --write-matches --write-web

# 若 FIFA 官方第三名分配已出,用 override 明确指定,不要让脚本猜
python3 wc_eval/predict/resolve_knockout.py --write-matches --write-web \
  --third-overrides M74=ECU,M77=SWE
```

原则:
- `predict_match.py / merge_batch.py / archive_pred.py / update_web.py` 旧链路保留;
- `resolve_knockout.py` 只把 bracket slot 转成真实 `HOME-AWAY`;
- 最佳第三名有多个候选时保留“暂定”,必须用官方分配或人工 override;
- 对阵落地后仍需补该场 `match_env` 和 `_HANDICAP` 固定盘口,再跑预测门禁。

一键编排可选打开:

```bash
python3 wc_eval/matchday.py --resolve-ko 1 --snapshot 2026-06-28_1223 \
  --env NED-MAR,BRA-JPN --predict NED-MAR,BRA-JPN --ts 2026-06-29_0900
```

## 评分（`score.py`）
赛后用真实赛果对照,按上面分值结算,累加成积分榜(单场分 + 全局分)。

## 🚨 防泄露（铁律）
预测时模型**只读「该预测点之前」的干净快照**:
- 全量预测 → 赛前快照(base / 最新版,无任何正赛);
- 逐日预测 → 当轮快照(含已踢、不含待预测)。
绝不把待预测结果喂进去。

## 待确认的设计点
1. **全量预测怎么喂 48 队**:48 份完整 summary 太长(超 context)→ 用每队「速览/关键摘要」?还是分批?
2. **逐日预测预测什么**:胜平负 / 比分 / 每日打包?
3. **"soda 模型"** 指什么(预测系统代号?prompt 角色?)——确认后写进 prompt。
