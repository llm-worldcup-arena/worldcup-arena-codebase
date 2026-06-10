---
name: wc-predict
description: 世界杯预测评测——6 家 SOTA 旗舰模型(经 DMXAPI)读 team_data 的 summary 做预测,赛后对照真实赛果打分→积分榜。赛前跑全量(单场+头名+全局),开赛后逐日只跑单场。两条铁律:开跑前必先汇报、防泄露只喂干净快照。
---

# 世界杯预测评测

6 家 SOTA 旗舰模型读 `team_data` 的 summary 做预测,赛后对照真实赛果打分 → 前端积分榜(`worldcup-arena-web`)。

## 🚨 两条铁律

1. **开跑前必先汇报**:真正调模型跑测评(烧 DMX API)前,**必须先向用户汇报**(测什么 / 哪 6 模型 / 调用量·成本 / 防泄露确认),**等用户确认才跑**。见记忆 `feedback-eval-report-first`。
2. **防泄露**:只喂「该预测点**之前**」的干净快照——赛前=base/最新版;逐日=当轮快照(`snapshot_round` 出的)。**绝不把待预测的赛果喂进去。**

## 评测对象(6 家带 thinking 的 SOTA · `wc_eval/predict/models.json`)

Claude `claude-opus-4-6-thinking` · GPT `gpt-5.2` · Gemini `gemini-3.1-pro-preview-thinking` · Kimi `Kimi-K2-Thinking` · GLM `glm-5` · Seed `doubao-seed-2-0-pro-260215`,统一经 `wc_eval/llm_client.py`(DMXAPI)调;**`ask_json` 统一传 `reasoning_effort:"high"`(thinking 拉满最高档,6 模型实测均可传)**。

> **为什么这 6 个(实测 2026-06-11,判据=响应是否吐 `reasoning_content` 思考过程)**:Claude opus-4-8 无 thinking 后缀 → 退 `claude-opus-4-6-thinking`;Gemini 换 `-thinking` 版、Kimi 换 `Kimi-K2-Thinking`(k2.5 实测 reasoning_content 为空);GLM-5、Seed-2.0 实测自带 thinking → 保留;**GPT 整个 OpenAI 家(含 o1/o3/o4 推理模型)在 DMXAPI 都不吐 reasoning_content(平台隐藏 reasoning tokens、非无 thinking)**,gpt-5.2 是稳定的 reasoning 旗舰。**旧纯 SOTA 配置见 models.json 的 `_sota_previous_备选`,可回滚。**

## 三类预测

| 类 | 喂什么 | 问什么 | 脚本 | 何时跑 |
|---|---|---|---|---|
| **A 单场 7 市场** | 比赛抬头 + 对阵 **2 队完整 summary** | 胜平负/让球/大小2.5/双方进球/单双/半全场/正确比分 | `predict_match.py` | 赛前 + **开赛后逐日** |
| **B 小组头名** | 赛事抬头 + 该组 **4 队完整 summary** | 该组头名(第1) | `predict_group.py` | **仅赛前一次** |
| **C 全局彩池** | 赛事抬头 + **48 队速览**(`extract_brief`,~118k token) | 夺冠/进决赛/四强/夺冠大洲/总进球 | `predict_global.py` | **仅赛前一次** |

> **赛前跑全量**(A+B+C 共 210 条);**开赛后只跑 A 单场**(头名/全局是赛前一锤子,赛后不重跑)。喂法:单场/头名喂完整 summary,全局喂速览(48 队完整会 30 万字超 context)。

## 🗓️ 开赛后逐日 SOP(每个比赛日照走)

```
① 增量收集 → wc-incremental-update:snapshot_round 出新快照 team_data/<日期>_R<N>
              (含截至昨日的已踢结果,绝不含待预测场 → 防泄露)
② 单场预测 → predict_match --snapshot <新快照> --run-ts <批次>,跑当天每场
              只跑单场!不碰头名/全局
③ 写档案  → merge_batch.py <批次>,再 archive_pred.py <批次> --daily(当天 matches【累加】进 archive/predictions.json,不动旧场)
④ 上线    → update_web.py --reveal <当天,如6.12>(从预测档案刷网页 + 运行时验证 + 解锁当天)→ push 前端
⑤ 收赛果  → 填 archive/results.json(matches 填比分即可,score.py 自动推各市场)
⑥ 算分    → score.py(predictions.json × results.json → scorecard.json)→ push 前端积分榜
```

## prompt 设计(三类统一,已固化在各脚本 `build_user`)

- **开放式 System**:「资料**供参考**,可结合自己掌握的信息与判断,**不必局限于给定**」—— 测真实预测力,不是阅读理解(**不再是旧版"只依据给定、不许编"**);
- **赛事抬头**:每个 prompt 开头点明赛事/阶段/时间/**尚未开赛**;单场还带 `common.match_header`(读 matches.json,自动出 日期/场地/**主客场**/真主场 or 中立);头名带时间+出线规则;全局带赛制(104场)+总进球定义;
- **先分析、再输出 JSON**;选项**能列全的列全**(半全场 9 种);**让球用固定盘口**——`common.handicap_clause` 给一条真实盘口(如 MEX-RSA 主-1、KOR-CZE 主-0.5),模型只判 **主胜盘/走盘/客胜盘**,**绝不让模型自选盘口**(旧版自选盘口=错,6 模型给不同线没法对照);
- **prompt 留存**:跑时 `save_prompt` 自动把实际 prompt(含真实抬头+summary)存到 `predictions/<批次>/_prompts/<kind>.txt`,和结果放一块、可追溯。

## 结果上线(转前端 `worldcup-data.js`)

**用 `update_web.py` 上线,绝不手动拼接 worldcup-data.js**:
```bash
python3 wc_eval/predict/update_web.py <批次>
cd worldcup_2026_web/site && git add -A && git commit -m '上线 <批次>' && git push
```
脚本三件事根除崩页:① **只替换 PRED 对象**(括号深度匹配,文件其余一字不动)② **node 实跑 ready() 验证**(崩就回滚、不写坏文件)③ **cache-bust** index.html 的 `?v=`。前端 PRED = 我们 `_unified.json` 的 `models`(结构一样);`nav-code` 按钮已链代码库。

> ⚠️ **2026-06-11 崩页教训**:曾「提取应用逻辑重组文件」,漏掉夹在 PRED 与 function hc 之间的 `var X2/OU/BT` 映射表 → `ready()` 崩 → 下半页全不渲染。**根因 =「重组文件」脆弱 + 只做语法检查没实跑**。`update_web.py` 从机制上根除(只换 PRED、必实跑验证、失败回滚)——**别再手动改 worldcup-data.js**。

## 评分(`score.py`,赛后对照真实赛果)

分值(与前端 `MARKETS`/`GLOBAL` 一致)——**单场**:让球 +4 / 半全场 +3 / 胜平负 +2 / 大小2.5 +2 / 双方进球 +2 / 正确比分 +2 / 单双 +1(看着难的多是猜、故压平);**全局**:夺冠 +25 / 进决赛 +10/队 / 四强 +4/队 / 夺冠大洲 +5 / 总进球 +4;**小组头名** +2/组。让球按固定盘口结算,逐项累加 → 积分榜。

## 存储 & 实测经验

- `predictions/<日期_时分>/`:各类预测 json + `_meta.md` + **`_prompts/`(留存)** + **`_unified.json`(merge_batch 合并)**;
- **并行** `ThreadPoolExecutor`(6-8);**`ask_json` timeout 300s**(thinking 慢,**GLM 偶 timeout 需重试**);`save_pred` **合并写**(补跑单模型不覆盖其他);
- `ask_json` 抓**最后一个** JSON(容前面分析文字),返回 `{_json, _raw}`;
- **已跑批次**:1437(旧 prompt)→ 1604(开放式)→ **2330(最新:开放SYS + 赛事抬头 + prompt留存,210条全成功)**;前端现挂 **2330**。
