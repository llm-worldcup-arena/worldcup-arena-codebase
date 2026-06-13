#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Elo 采集：eloratings.net/World.tsv（静态文件，直连）→ team_rank.json 加 elo。

World.tsv 列：0/1=排名  2=2字母码  3=Elo  其余为统计。
规范见 wc_skills/wc-data-collect。跑：python3 collect_elo.py
"""
import json, os, urllib.request
from datetime import datetime
from collect_squads import snap_path

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/wc_runs"   # 可移植
ASOF = "2026-06-08"
UA = "WorldCup2026-BG-Research/1.0 (academic benchmark; mailto:zhenran.w.1103@gmail.com)"
URL = "https://www.eloratings.net/World.tsv"

# eloratings 2字母码 → FIFA 三字码（本届 48 队；多为 ISO alpha-2，英格兰/苏格兰特殊）
ELO2FIFA = {
    "ES": "ESP", "AR": "ARG", "FR": "FRA", "EN": "ENG", "BR": "BRA", "PT": "POR", "CO": "COL",
    "NL": "NED", "EC": "ECU", "DE": "GER", "NO": "NOR", "TR": "TUR", "HR": "CRO", "JP": "JPN",
    "BE": "BEL", "UY": "URU", "CH": "SUI", "MX": "MEX", "SN": "SEN", "ZA": "RSA", "KR": "KOR",
    "CZ": "CZE", "CA": "CAN", "BA": "BIH", "QA": "QAT", "MA": "MAR", "HT": "HAI", "SQ": "SCO",
    "US": "USA", "PY": "PAR", "AU": "AUS", "CW": "CUW", "CI": "CIV", "SE": "SWE", "TN": "TUN",
    "EG": "EGY", "IR": "IRN", "NZ": "NZL", "CV": "CPV", "SA": "KSA", "IQ": "IRQ", "DZ": "ALG",
    "AT": "AUT", "JO": "JOR", "CD": "COD", "UZ": "UZB", "GH": "GHA", "PA": "PAN",
}


def main(ts=None, asof=ASOF):
    ts = ts or datetime.now().strftime("%Y-%m-%d_%H%M")
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    tsv = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="replace")

    raw_dir = f"{BASE}/data_raw/{ts}"
    os.makedirs(raw_dir, exist_ok=True)
    open(f"{raw_dir}/World.tsv", "w", encoding="utf-8").write(tsv)   # 原文留底

    elo_by_fifa = {}
    for line in tsv.splitlines():
        c = line.split("\t")
        if len(c) >= 4 and c[2] in ELO2FIFA and c[3].isdigit():
            elo_by_fifa[ELO2FIFA[c[2]]] = int(c[3])

    rank_path = snap_path(asof, "team_rank")               # 新结构: bg/snapshots/asof=日/
    if os.path.exists(rank_path):
        rank = json.load(open(rank_path, encoding="utf-8"))
    else:
        rank = {f: {} for f in ELO2FIFA.values()}          # 单独跑也能建骨架
    hit = 0
    for fifa, elo in elo_by_fifa.items():
        d = rank.get(fifa) if isinstance(rank.get(fifa), dict) else {}
        d["elo"] = elo
        d["elo_asof"] = asof
        d.setdefault("squad_value_m", None)                # 阵容总身价·留字段(块7采)
        rank[fifa] = d
        hit += 1
    os.makedirs(os.path.dirname(rank_path), exist_ok=True)
    json.dump(rank, open(rank_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    missing = sorted(f for f in ELO2FIFA.values() if f not in elo_by_fifa)
    print(f"  Elo 落盘 {hit}/48 队 → team_rank.json(asof={asof}) | raw: {ts}/World.tsv")
    if missing:
        print("  没匹配到 Elo（码可能不对，需调 ELO2FIFA）:", missing)
    return hit


if __name__ == "__main__":
    main()
