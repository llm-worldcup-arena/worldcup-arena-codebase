#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""块6·预选赛战绩采集：各洲「2026 FIFA World Cup qualification (洲)」页
→ 找 transclude 的积分榜 table 模板 → 解析 win_XXX/draw_XXX/loss_XXX/gf_XXX/ga_XXX
（XXX = FIFA 三字码）→ teams.qualifying（played/won/drawn/lost/gf/ga）。

⚠️ 各洲结构不一（单组/多组/多阶段），本版尽力解析 table 模板；采到的填，采不到的留 None。
独立采集器（不并进 collect_all 主流程，抓多张模板页较慢）；需要时单独跑，前提 teams.json 已建。
跑：python3 collect_qualifying.py
"""
import json, re
from collect_squads import fetch_save, run_ts, BASE, WIKI_PAGE, teams_path, load_json, dump_json

CONFED_PAGES = [
    "2026 FIFA World Cup qualification (CONMEBOL)",
    "2026 FIFA World Cup qualification (UEFA)",
    "2026 FIFA World Cup qualification (CONCACAF)",
    "2026 FIFA World Cup qualification (CAF)",
    "2026 FIFA World Cup qualification (AFC)",
]


def find_table_templates(wt):
    """页里 transclude 的「…qualification…table」积分榜模板名（含 en-dash）。"""
    return set(re.findall(r"\{\{\s*(2026 FIFA World Cup qualification[^\{\}\|\n]*?[Tt]able)\s*[\|\}]", wt))


def parse_qual_table(wt, codes):
    """table 模板源 → {code: {played,won,drawn,lost,gf,ga}}。"""
    out = {}
    for code in codes:
        w = re.search(r"\|\s*win_" + code + r"\s*=\s*(\d+)", wt)
        dr = re.search(r"\|\s*draw_" + code + r"\s*=\s*(\d+)", wt)
        ls = re.search(r"\|\s*loss_" + code + r"\s*=\s*(\d+)", wt)
        if not (w and dr and ls):
            continue
        won, drawn, lost = int(w.group(1)), int(dr.group(1)), int(ls.group(1))
        gf = re.search(r"\|\s*gf_" + code + r"\s*=\s*(\d+)", wt)
        ga = re.search(r"\|\s*ga_" + code + r"\s*=\s*(\d+)", wt)
        out[code] = {"played": won + drawn + lost, "won": won, "drawn": drawn, "lost": lost,
                     "gf": int(gf.group(1)) if gf else None, "ga": int(ga.group(1)) if ga else None}
    return out


def main(ts=None):
    raw_dir = f"{BASE}/raw/bg/{ts or run_ts()}"             # 预选赛页 + table 模板原文存这（raw 全量）
    codes = set(WIKI_PAGE)
    qual = {}
    for cpage in CONFED_PAGES:
        conf = cpage.split("(")[-1].rstrip(")")
        try:
            tmpls = find_table_templates(fetch_save(cpage, raw_dir, f"qual_{conf}.wikitext"))
        except Exception as e:
            print(f"  [{cpage}] 抓取出错: {e}"); continue
        for i, tname in enumerate(tmpls):
            try:
                twt = fetch_save("Template:" + tname, raw_dir, f"qual_{conf}_table{i}.wikitext")
                qual.update(parse_qual_table(twt, codes))
            except Exception:
                pass
        print(f"  {conf}: {len(tmpls)} 张表 → 累计本届 {len(qual)} 队")

    teams = load_json(teams_path(), [])
    tb = {t["team_id"]: t for t in teams}
    n = 0
    for code, q in qual.items():
        if code in tb:
            tb[code]["qualifying"] = q; n += 1
    dump_json(teams_path(), sorted(tb.values(), key=lambda t: t["team_id"]))
    print(f"\n完成 {n}/48 队预选赛战绩 → teams.qualifying（采不到的留 None）")


if __name__ == "__main__":
    main()
