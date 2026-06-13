# 世界杯 · 多源赛事播报（match_broadcast）

世界杯**每场比赛**的多源赛事播报，独立工作流（不与背景采集/预测线混，只借用 `wc_runs/` 存）。规则见 skill [`wc-match-broadcast`](../../../wc_skills/wc-match-broadcast/SKILL.md)。

## 结构（每场一个文件夹，命名 = `日期_主队_vs_客队`）

```
<日期>_<主>_vs_<客>/
├── raws/                      ← 收集层 = 原文（每个来源一个文件夹，只增不改）
│   └── <媒体>/<媒体>.json      JSON 里 original_text = 该网页【逐字原文】（直抓 HTML 机械抽取，不经任何模型）
└── ours/                      ← 产物层 = 我们自己做的（给人看，**不是原文**）
    ├── long.md                全本：信息最全最广，多源交叉、带来源标注与「存疑」
    ├── short.md               短版：约 600 字球迷向速览
    ├── timeline.md            逐分钟战况时间线：关键事件按分钟排（直播复盘体，最贴「播报」）
    ├── data.json              结构化数据卡：比分/射手/牌/首发/控球/xG，机器可读（harddata.py 由 Apify macheta 自动生成）
    ├── promo_report.md        社媒宣传版·赛事播报（小红书/抖音，CC 创意战报）
    ├── promo_predict_pre.md   社媒宣传版·AI 预测【没看到结果版】（赛前 6 模型预测+共识）
    └── promo_predict_post.md  社媒宣传版·AI 预测【看到结果版】（赛后 预测 vs 实际+谁神准）
                               ↑ promo_predict_* 由 promo.py 读 web 预测(worldcup-data.js)+data.json 自动生成
```

> **一句话**：要看**原文**，打开 `raws/<媒体>/<媒体>.json` 的 `original_text` 字段（可拿同文件 `url` 开原网页逐字核对）；`ours/` 里的 long/short 是基于这些原文合成的产物。

## 怎么新增一场
1. CC 用 `WebSearch`（中/英/西多语种）找该场可靠媒体报道 → 写进 urls 清单；
2. 跑 `wc_eval/match_report/fetch_sources.py --match <id> --urls urls.json` → 直抓逐字原文落 `raws/`；
3. CC 读 `raws/` 全部原文 → 交叉合成 `ours/long.md` + `ours/short.md`。
- 只用 **CC 联网 + Apify**（顶级源反爬/硬数据），**不用 DMXAPI**。

## 现状（2026-06-12）
- ✅ `2026-06-11_MEX_vs_RSA`：**13 源**（FIFA官方/AP/Sky/beIN/FOX/NBC + WST/Crónica/Diario + **中文 ×4** 网易×2/新浪/中华网）+ macheta 硬数据 → long+short+timeline+**data.json**。
- ✅ `2026-06-11_KOR_vs_CZE`：**10 源**（FIFA官方/Sky/半岛 + La Nación/El Espectador/RPP + **中文 ×4** 网易×2/新浪/大纪元）+ macheta 硬数据 → long+short+timeline+**data.json**。
- ⏳ **CAN-BIH、USA-PAR（6/12 晚场）当天还没踢完**——macheta 比分 -1--1，流水线已就位，等结果出来即可一键跑。
- ✅ **APIFY_TOKEN 已配**：FIFA 官方（JS App，urllib 只回空壳）已用 Apify `website-content-crawler` 抓到；ESPN（整日分析专栏，非专稿）/Yahoo（串稿）经核验弃用。macheta 硬数据（控球/xG/完整阵容）可随时补。
- 🔜 其余已踢场次（CAN-BIH、USA-PAR）照流水线（skill `wc-match-broadcast`）跑。

> 流程化：找源→抓原文→(Apify补)→合成，规则全在 skill [`wc-match-broadcast`](../../../wc_skills/wc-match-broadcast/SKILL.md)，抓取 py 是 [`fetch_sources.py`](../../../wc_eval/match_report/fetch_sources.py)（内置质量门：弃直播/电视推广页、清头尾杂讯）。

> 注：`match_broadcast/` 下**每一场比赛是一个文件夹**，所以会有多个并排（如 MEX_vs_RSA、KOR_vs_CZE）——这是正常的，与"同一场重名"不同。
