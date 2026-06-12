# 世界杯 2026 · 可靠媒体源清单（赛事播报 / 赛后增量）

> 配 skill `wc-incremental-update`。赛后增量更新 summary 时，**文字/叙事/伤停/红黄牌**优先用下列高可信源，**≥2 个独立源交叉核实**才写入（防张冠李戴，见 ter Stegen 教训）。专业站直连反爬 403、用 WebSearch 间接拿其被引用的数据。

## 分层（按可信度，2026-06 实测）

| 层级 | 用途 | 媒体源 | 备注 |
|---|---|---|---|
| **官方** | 比分/阵容/进球/牌/赛程权威确认 | **FIFA 官方**（fifa.com match-centre）、各国足协官网（如 canadasoccer.com） | 最权威，硬数据以此为准 |
| **顶级体育媒体** | 比分/统计/叙事/伤停，覆盖全、更新快 | **ESPN**、**FOX Sports**、**CBS Sports**、**Yahoo Sports**、**NBC Sports** | 美加墨主场赛事覆盖最全；ESPN 有逐分钟 box score |
| **主流通讯/大报** | 赛事综述/重大事件（红牌/争议）核实 | **CNN**、**Washington Post**、**Al Jazeera**、**Reuters/AP**（经新闻引用） | 综述与背景叙事可靠 |
| **数据/比分站** | 比分/射手/卡牌快报 | **Flashscore**、**FotMob**（经搜索引用）、**Sofascore/FBref**（反爬，间接拿） | 硬数据交叉校验 |
| **硬数据 API**（需 key） | 比分/阵容/缺阵/统计/xG | **API-Football**（官方 API，需免费 key）、**macheta**（Apify，带 xG，需 APIFY_TOKEN） | 拿到 key 后作硬数据主力；当前未配 token，暂用 WebSearch |

## 实测记录（2026-06-11 首日两场，均多源核实）

- **墨西哥 2-0 南非**（3 红牌创揭幕战纪录）：ESPN、Washington Post、FOX Sports、CBS Sports、CNN、Al Jazeera —— 比分/射手/红牌人名一致。
- **韩国 2-1 捷克**（逆转）：ESPN、FIFA 官方、Yahoo Sports、FOX Sports、Outlook India、Flashscore —— 比分/射手/黄牌一致。

## 红线

- **防泄露**：只采**已踢完、非待预测**的场次；`integrate_match.py` 兜一道 `date≤today` 硬校验。
- **防张冠李戴**：核实人物属于**哪队/哪国**（ter Stegen 事件：误把德国门将缺阵记到西班牙）。
- 写入 summary 必标「多源核实」+ 列来源。
