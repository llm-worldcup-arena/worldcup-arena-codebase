[English](README.md) | **中文**

# 世界杯 2026 · 多模型预测基准

> 🌐 **在线演示:** https://llm-worldcup-arena.github.io/

6 家**最新旗舰、SOTA** 大模型(Claude / GPT / Gemini / Kimi / GLM / Seed)读 48 支球队的**赛前档案**,预测 2026 世界杯——单场盘口、小组头名、夺冠全局彩池——赛后用真实结果对照打分,排出模型积分榜。

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

# 2. 配置 API key
cp config/secrets.local.json.example config/secrets.local.json
#    DMX_API_KEY 必填(Claude/GPT/Gemini/Seed 经 DMXAPI 调)。
#    MOONSHOT_API_KEY / ZHIPU_API_KEY 选填——仅当要让 Kimi、GLM 也开联网搜索时填
#    (它俩经 DMXAPI 的通道没有服务端搜索,需各自官方 API 直连)。

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

## 6 个模型

均为各家**带思考(reasoning)的旗舰**,且都开了联网搜索。选型上取能吐思考过程的变体(如用 `claude-opus-4-6-thinking` 而非 4-8——后者经 DMXAPI 不返回思考过程):

Claude `claude-opus-4-6-thinking` · GPT `gpt-5.2` · Gemini `gemini-3.1-pro-preview-thinking` · Kimi `kimi-k2.6` · GLM `glm-5.1` · Seed `doubao-seed-2-0-pro-260215`。

Claude / GPT / Gemini / Seed 经 **DMXAPI**(OpenAI 兼容)调用;**Kimi、GLM 走各自官方 API 直连**(Moonshot / 智谱)——这俩经 DMXAPI 的通道没有服务端搜索,为让 6 家都"开卷"故用官方端点。每个模型的具体通道、温度、token 上限见 [`wc_eval/predict/models.json`](wc_eval/predict/models.json)。

## 更多文档

- 代码地图(收集→预测每个 py/skill 干啥)→ [`docs/CODEBASE.md`](docs/CODEBASE.md)
- 数据/档案设计 → [`docs/BG_DESIGN.md`](docs/BG_DESIGN.md)
- 整体方案 → [`docs/PLAN.md`](docs/PLAN.md)
- 预测喂法 & token 预算 → [`wc_eval/predict/FEED_DESIGN.md`](wc_eval/predict/FEED_DESIGN.md)
