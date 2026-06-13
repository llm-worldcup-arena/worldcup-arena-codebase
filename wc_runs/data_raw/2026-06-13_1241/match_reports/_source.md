# 采集来源说明 · 单场权威硬数据
- **数据源**：Apify · macheta/football-super-fast-data（= Sofascore/365scores 一手，Opta 级）
- **采法**：FIXTURES 拿 matchId → MATCH_DETAILS → `raw_game_data`(~120KB) 全量留底 + 提取
- **权威字段**：比分/事件(球员名+时间+点球)/阵容/**缺阵伤停**/控球/**xG(Type78)**/射门/传球分区
- **Type 编号为推断映射**，以 raw_game_data 全量为准可校准
- **文字补充**（叙事播报/采访/评分）：agent WebSearch，见 SKILL.md「单场赛后采集」
- **防泄露**：只采已踢完、非待预测场次
