# 采集来源说明 · 单场赛后
- **方式**：agent WebSearch 多角度(赛后播报/统计xG/球员评分/伤病停赛+采访) + WebFetch 能读的新闻站
- **可靠**：专业站(ESPN/Sofascore)反爬,数据经各新闻报道引用 WebSearch 间接全拿
- **防泄露**：只采已踢完、非待预测的场次；本脚本再兜一道 date≤today 校验
- **用途**：世界杯 2026 预测 benchmark · 滚动更新 summary
