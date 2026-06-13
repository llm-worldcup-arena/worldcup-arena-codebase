# 采集来源说明 · TM 球员档案(链接采 · 完整 JSON)
- **采集时间**:2026-06-09_2229
- **数据源**:Apify · handsome_apostrophe/transfermarkt-scraper-v2(playerUrls 模式 · slug 占位 URL)
- **内容**:235 名球员(KOR/EGY/中东等 automation-lab 音译名搜不到的)TM 完整返回 JSON,按队 tm_<队>.json
- **可靠字段** ✅:market_value / market_value_numeric / market_value_history / peak_market_value / player_id / club_id / shirt_number
- **⚠️ 坏字段(勿用)**:club / birth_date / height / citizenship / position / foot / contract_joined / contract_expires / nationality —— 该 actor 解析**错位**(把下一字段标签当值)。出生/身高/合同/国籍 一律以 WebSearch 核对值或维基为准
- **用途**:身价 raw 全量留底(世界杯 2026 预测 benchmark)
