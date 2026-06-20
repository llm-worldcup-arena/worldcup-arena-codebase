# UZB · 队伍新闻收集过程留底（asof 2026-06-20）
- **双写**：本目录=本次【新增】的收集过程留底；同内容已累积进成熟仓库 `processed/team_news/<队>/`（按队累积、文件名带新闻日期）。
- **方式**：按 gen_queries 标准关键词 WebSearch 找源(按 NEWS_TIERS 分层优先) → fetch_sources 直抓逐字全文（+Apify 兜底+质量门），不经模型改写。
- **新旧判断**：身份键=URL、以 processed 仓库为准；已有默认跳过（--refresh 重拍快照）。
- **下游**：全文走 summary 块A（LLM 三判后只增不改）；≥2 源交叉、防张冠李戴。
