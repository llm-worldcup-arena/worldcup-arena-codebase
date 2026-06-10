#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【世界杯·赛后增量更新 · 第1步】采集"这一场"的权威硬数据（比分/进球/阵容/缺阵/控球/xG/射门）。
   skill: wc-incremental-update。下游：agent WebSearch(第2步补文字) → integrate_match.py(第3步增量整合)。

数据源：macheta（Apify · 365scores 数据 · 第三方抓取 · **带 xG** · py 可全自动）。
   ⚠️ 更稳的主力是 API-Football（官方 API、世界杯全覆盖、需免费 key、xG 弱）；macheta 退为 xG 补充 + 冗余校验。

流程：FIXTURES(按日期拿 matchId) → MATCH_DETAILS(matchId) → raw_game_data 全量留底 + 提取结构化。

提取(权威)：比分 / 事件(进球·牌·换人 + 球员名 + 时间 + 点球标记) / 首发阵容 / **缺阵伤停** /
            统计(控球 · xG · 射门 · 射正 · 传球分区 …)。
⚠️ Statistics/Events 的 Type 为 365scores 编号、下表为**推断映射**；raw_game_data 全量留底，可回溯校准。
🚨 防泄露：只采已踢完、非待预测的场次（与 integrate_match.py 的 date≤today 配合）。

跑：APIFY_TOKEN=xxx python3 collect_match.py --date 06/06/2026 --team Argentina --ts 2026-06-12_2000
   或直接：python3 collect_match.py --match 4710299 --ts 2026-06-12_2000
"""
import json, urllib.request, os, argparse

TOKEN = os.environ.get("APIFY_TOKEN", "")
ACT = "macheta~football-super-fast-data"
BASE = "/home/ubuntu/worldcup_2026/wc_runs"

# 365scores Statistics Type → 含义（推断；raw 全量可回溯）
STAT = {10: "控球%", 3: "射门", 4: "射正", 5: "禁区内射门", 6: "扑救", 8: "角球",
        9: "越位", 11: "传中", 19: "传球", 78: "xG预期进球", 79: "xGOT/大机会"}
# 牌取 events 里准确的（统计里的 Type23/24 含义不明、勿当黄红牌）
EV_TYPE = {0: "进球", 1: "黄牌", 2: "红牌", 3: "换人"}
EV_STYPE = {2: "点球", 1: "乌龙"}


def call(inp):
    url = f"https://api.apify.com/v2/acts/{ACT}/run-sync-get-dataset-items?token={TOKEN}"
    req = urllib.request.Request(url, data=json.dumps(inp).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=200).read())


def find_match(date, team=None):
    fx = call({"mode": "FIXTURES", "dateFrom": date, "dateTo": date})
    out = [(m.get("id"), str(m.get("homeTeam", {}).get("name", "")), str(m.get("awayTeam", {}).get("name", "")))
           for m in (fx if isinstance(fx, list) else [])]
    if team:
        out = [x for x in out if team.lower() in (x[1] + x[2]).lower()]
    return out


def collect(match_id, ts=None, iso=None, comp=None, ha_home=None):
    x = call({"mode": "MATCH_DETAILS", "matchId": str(match_id)})
    x = x[0] if isinstance(x, list) else x
    rgd = x.get("raw_game_data"); rgd = json.loads(rgd) if isinstance(rgd, str) else (rgd or {})

    # ── raw_game_data 全量留底（权威 raw，两步铁律第一步）──
    if ts:
        rawd = f"{BASE}/raw/bg/{ts}/match_reports"; os.makedirs(rawd, exist_ok=True)
        json.dump(rgd, open(f"{rawd}/{match_id}_raw.json", "w", encoding="utf-8"), ensure_ascii=False)
        if not os.path.exists(f"{rawd}/_source.md"):
            open(f"{rawd}/_source.md", "w", encoding="utf-8").write(
                "# 采集来源说明 · 单场权威硬数据\n"
                "- **数据源**：Apify · macheta/football-super-fast-data（= Sofascore/365scores 一手，Opta 级）\n"
                "- **采法**：FIXTURES 拿 matchId → MATCH_DETAILS → `raw_game_data`(~120KB) 全量留底 + 提取\n"
                "- **权威字段**：比分/事件(球员名+时间+点球)/阵容/**缺阵伤停**/控球/**xG(Type78)**/射门/传球分区\n"
                "- **Type 编号为推断映射**，以 raw_game_data 全量为准可校准\n"
                "- **文字补充**（叙事播报/采访/评分）：agent WebSearch，见 SKILL.md「单场赛后采集」\n"
                "- **防泄露**：只采已踢完、非待预测场次\n")

    sb = x.get("scoreboard", {})
    lns = rgd.get("Lineups", [])
    lineup = lambda i: [{"no": p.get("JerseyNum"), "name": p.get("PlayerName")}
                        for p in (lns[i].get("Players", []) if i < len(lns) else [])]
    events = [{"min": e.get("GT"), "side": "home" if e.get("Comp") == 1 else "away",
               "type": EV_TYPE.get(e.get("Type"), f"T{e.get('Type')}"),
               "sub": EV_STYPE.get(e.get("SType")) if e.get("SType", -1) > 0 else None,
               "player": e.get("Player")} for e in rgd.get("Events", [])]
    missing = [{"side": "home" if p.get("CompetitorNum") == 1 else "away",
                "no": p.get("JerseyNum"), "name": p.get("PlayerName"),
                "reason": p.get("Reason") or p.get("StatusText") or "缺阵"}
               for g in rgd.get("MissingPlayers", []) for p in g.get("Players", [])]
    stats = {STAT[s["Type"]]: s["Vals"] for s in rgd.get("Statistics", [])
             if s.get("Type") in STAT and s.get("Vals")}

    goals = [{"min": e["min"], "side": e["side"], "player": e["player"], "sub": e["sub"]}
             for e in events if e["type"] == "进球"]
    cards = [{"min": e["min"], "side": e["side"], "player": e["player"], "type": e["type"]}
             for e in events if "牌" in e["type"]]
    return {"match_id": match_id, "date": iso, "comp": comp or "世界杯", "ha_home": ha_home or "中",
            "home": sb.get("home", {}).get("name"), "away": sb.get("away", {}).get("name"),
            "score": f"{sb.get('home', {}).get('score')}-{sb.get('away', {}).get('score')}",
            "venue": (rgd.get("Venue") or {}).get("Name"), "attendance": rgd.get("Attendance"),
            "goals": goals, "cards": cards, "stats": stats,
            "lineups": {"home": lineup(0), "away": lineup(1)}, "missing": missing, "events": events,
            # ↓ 待 agent WebSearch 补后写回本 JSON，再交 integrate_match.py
            "injuries": [], "suspensions": [], "ratings": {}, "quotes": [], "narrative": "", "prediction_note": "",
            "_note": "macheta/Sofascore 权威硬数据；injuries/suspensions/ratings/quotes/narrative/prediction_note 待 agent WebSearch 补。"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="比赛日 DD/MM/YYYY（配合 FIXTURES 找 id）")
    ap.add_argument("--team", help="队名关键词（过滤 FIXTURES）")
    ap.add_argument("--match", help="直接给 matchId（跳过 FIXTURES）")
    ap.add_argument("--ts", help="raw 留底时间戳 YYYY-MM-DD_HHMM")
    ap.add_argument("--comp", help="赛事名（写进输出，如 世界杯·A组）")
    ap.add_argument("--ha", help="主队的 主/客/中（home 视角，世界杯小组赛多为中立）")
    ap.add_argument("--out", help="输出单场 data JSON 路径")
    a = ap.parse_args()
    iso = None
    if a.date:  # DD/MM/YYYY → YYYY-MM-DD
        dd, mm, yy = a.date.split("/"); iso = f"{yy}-{mm}-{dd}"
    mid = a.match
    if not mid and a.date:
        ms = find_match(a.date, a.team)
        for i, h, aw in ms:
            print(f"  {i}  {h} vs {aw}")
        if len(ms) == 1 or (a.team and ms):
            mid = ms[0][0]
        else:
            print("多场/0 场，请用 --match 指定 id"); return
    data = collect(mid, a.ts, iso, a.comp, a.ha)
    out = a.out or f"/tmp/match_{mid}.json"
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ {data['home']} {data['score']} {data['away']} | "
          f"事件{len(data['events'])} 阵容{len(data['lineups']['home'])}+{len(data['lineups']['away'])} "
          f"缺阵{len(data['missing'])} 统计{len(data['stats'])}项 → {out}")


if __name__ == "__main__":
    main()
