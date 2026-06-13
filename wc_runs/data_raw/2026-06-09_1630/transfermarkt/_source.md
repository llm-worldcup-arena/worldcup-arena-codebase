# 采集来源说明 · Transfermarkt 球员档案

- **采集种类**：球员档案（身价/惯用脚/合同/双国籍/转会史…）
- **数据源**：Apify 平台 Actor `automation-lab/transfermarkt-scraper`（Transfermarkt 抓取）
- **采集时间**：2026-06-09_1630（精确到分钟）｜**方式**：每队 `searchQueries` 批量、线程池并发
- **采集范围**：4 队、约 68 名球员
- **raw**：本目录 `tm_<队>.json` = actor 返回**完整 JSON 全量留底**（一字不改）
- **提取**：market_value_eur / foot / contract_until / nationality_tm / tm_* …（从宽；其余字段仍在 raw）
- **准确性**：TM 出生年份 ⨯ 维基 birthdate 交叉校验，**年份不符=同名搜错人→剔除 TM**（`tm_mismatch` 标记）
- **凭证**：`APIFY_TOKEN`（环境变量，未入库）｜**用途**：世界杯 2026 预测 benchmark
