#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【世界杯·赛事播报 · 硬数据 step】Apify **macheta**（365scores/Opta 级）抓一场的结构化硬数据
   （比分/首发/缺阵/控球/射门/射正/角球/xG/红黄牌），落两处：
     - `raws/apify_macheta/harddata.json`  全量留底（含 events）
     - `ours/data.json`                    第 4 种产物 = 结构化数据卡（机器可读，给网站/评测）

   复用 wc_eval/bg_collect/collect_match.py 的 macheta 取数逻辑。需 APIFY_TOKEN（读 env 或 config/secrets.local.json）。
   skill: wc-match-broadcast。跑：python3 harddata.py --match M1
"""
import os, sys, json, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                                  # fetch_sources
sys.path.insert(0, os.path.dirname(HERE) + "/bg_collect")  # collect_match
import fetch_sources as FS          # noqa: E402
import collect_match as CM          # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True, help="matches.json 的 match_id，如 M1")
    a = ap.parse_args()
    md = FS.resolve_match(a.match)
    tok = FS.apify_token()
    if not tok:
        sys.exit("✗ 无 APIFY_TOKEN（填 config/secrets.local.json）")
    os.environ["APIFY_TOKEN"] = tok
    CM.TOKEN = tok                                        # collect_match 模块级 token

    # 试「比赛日」与「后一天」（365scores 按 UTC 记日期，晚场会算到次日）× 全名/首词
    d0 = datetime.date.fromisoformat(md["date"])
    dates = [d0.strftime("%d/%m/%Y"), (d0 + datetime.timedelta(days=1)).strftime("%d/%m/%Y")]
    keys = []
    for k in (md["home_en"], md["away_en"]):
        keys += [k, k.split()[0]]
    print(f"▶ macheta 找 {md['home_en']} vs {md['away_en']}（试 {dates}）…")
    mid = None
    for dd in dates:
        for key in keys:
            ms = CM.find_match(dd, key)
            if ms:
                mid = ms[0][0]; break
        if mid:
            break
    if not mid:
        sys.exit("✗ macheta 未找到该场（不覆盖 / 未开赛）")
    hard = CM.collect(mid, iso=md["date"], comp=md["comp"], ha_home="中")
    # 未踢守卫：比分 -1--1 或无首发 = 没踢完，不生成产物
    if str(hard.get("score", "")).replace(" ", "") in ("-1--1", "None-None", "") or \
       not (hard["lineups"]["home"] or hard["lineups"]["away"]):
        sys.exit(f"🚫 该场尚未踢完（macheta 比分 {hard.get('score')}、无阵容）—— 不生成硬数据/产物。")

    base = f"{FS.RUNS}/data_processed/match_broadcast/{md['slug']}"
    rawd = f"{base}/raws/apify_macheta"
    os.makedirs(rawd, exist_ok=True)
    json.dump(hard, open(f"{rawd}/harddata.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(f"{rawd}/_source.md", "w", encoding="utf-8").write(
        "# 来源：Apify macheta（365scores/Opta 级硬数据）\n"
        "- 抓法：FIXTURES 按日期找 matchId → MATCH_DETAILS → 提取比分/首发/缺阵/控球/射门/xG/牌\n"
        "- 用途：填 ours/data.json 结构化数据卡（原文里没有的控球/xG/完整阵容等硬数字）\n")

    # ── 第 4 种产物：结构化数据卡 ──
    card = {
        "match": {"date": md["date"], "home": md["home"], "away": md["away"],
                  "home_en": md["home_en"], "away_en": md["away_en"], "comp": md["comp"],
                  "venue": hard.get("venue"), "attendance": hard.get("attendance")},
        "score": hard.get("score"), "ht": hard.get("ht"),
        "goals": hard.get("goals"), "cards": hard.get("cards"),
        "stats": hard.get("stats"),
        "lineups": hard.get("lineups"), "missing": hard.get("missing"),
        "source": "Apify macheta（365scores/Opta 级硬数据）",
        "_note": "结构化硬数据（机器可读）；叙事见 ours/long.md，逐分钟见 ours/timeline.md，简版见 short.md。",
    }
    os.makedirs(f"{base}/ours", exist_ok=True)
    json.dump(card, open(f"{base}/ours/data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    st = hard.get("stats", {})
    print(f"✅ {md['home']} {hard.get('score')} {md['away']} | 首发 "
          f"{len(hard['lineups']['home'])}+{len(hard['lineups']['away'])} | 统计 {len(st)} 项"
          f"（控球 {st.get('控球%')}, xG {st.get('xG预期进球')}）")
    print(f"   → {rawd}/harddata.json + {base}/ours/data.json")


if __name__ == "__main__":
    main()
