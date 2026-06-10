# World Cup 2026 · Multi-LLM Prediction Benchmark

6 家旗舰大模型(Claude / GPT / Gemini / Kimi / GLM / Seed)读 48 支球队的**赛前档案**,预测 2026 世界杯——单场盘口、小组头名、夺冠全局彩池——赛后用真实结果对照打分,排出模型积分榜。

## 做什么

- **数据**:为 48 队各建一份赛前档案(`wc_runs/team_data/`)——阵容、近期状态、伤病、世界杯历史、身价,多源采集(Wikipedia / Transfermarkt / Elo)并交叉核对;
- **预测**:6 模型读档案,做三类预测(下表);
- **评分**:赛后用真实赛果对照打分 → 模型积分榜。

> 防泄露:只喂「该预测点之前」的干净快照,绝不把待预测的赛果喂进去。

## 三类预测

| 类型 | 喂什么 | 预测什么 |
|---|---|---|
| **单场 7 市场** | 对阵两队完整档案 | 胜平负 / 让球 / 大小 2.5 / 双方进球 / 单双 / 半全场 / 正确比分 |
| **小组头名** | 该组 4 队档案 | 12 组各押头名 |
| **全局彩池** | 48 队速览(`extract_brief` 压缩版) | 夺冠 / 进决赛 / 四强 / 夺冠大洲 / 总进球 |

## 快速开始

```bash
# 1. 零第三方依赖,Python 3.8+ 即可(标准库 urllib 调 API)

# 2. 配置 API key(经 DMXAPI 统一调 6 模型)
cp config/secrets.local.json.example config/secrets.local.json
#    编辑它,填入你的 DMX_API_KEY

# 3. 跑预测(以 6/11 揭幕场为例)
cd wc_eval/predict
python3 predict_match.py  --home MEX --away RSA --snapshot 2026-06-10_1310   # 单场 7 市场
python3 predict_group.py  --snapshot 2026-06-10_1310                          # 12 组头名
python3 predict_global.py --snapshot 2026-06-10_1310                          # 全局彩池
python3 merge_batch.py    <批次时间戳>                                          # 合成统一 json
```

## 结构

| 目录 | 内容 |
|---|---|
| `wc_eval/` | 代码:`bg_collect/`(数据采集)+ `predict/`(6 模型预测) |
| `wc_skills/` | 三个 skill:数据采集 / 增量更新 / 预测的操作规则 |
| `config/` | LLM 配置(`llm.json` + key 模板) |
| `wc_runs/` | 数据与产物:`team_data/`(48 队档案)、`predictions/`(预测结果)、`bg/`(结构化数据) |
| `docs/` | 设计文档:代码地图、数据设计、整体方案、采集计划 |

## 6 模型

Claude `claude-opus-4-8` · GPT `gpt-5.2` · Gemini `gemini-3.1-pro` · Kimi `kimi-k2.5` · GLM `glm-5` · Seed `doubao-seed-2-0-pro` —— 统一经 DMXAPI(OpenAI 兼容)调用。

## 更多文档

- 代码地图(收集→预测每个 py/skill 干啥)→ [`docs/CODEBASE.md`](docs/CODEBASE.md)
- 数据/档案设计 → [`docs/BG_DESIGN.md`](docs/BG_DESIGN.md)
- 整体方案 → [`docs/PLAN.md`](docs/PLAN.md)
- 预测喂法 & token 预算 → [`wc_eval/predict/FEED_DESIGN.md`](wc_eval/predict/FEED_DESIGN.md)
