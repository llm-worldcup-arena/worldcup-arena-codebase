#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用修好的 gen 逻辑重新生成【干净阵容表（含身价）】，替换 summary 的⑤阵容段，
**保留叙述段(①-④⑥⑦⑧)与末尾市值段**。修解析残留(birth_date=/caps=)后用此重刷阵容表。

跑：python3 replace_squad_table.py [--only ARG]
"""
import re, os, argparse
import gen_summary as G
from collect_squads import (BASE, persons_path, teams_path, snap_path,
                            matches_path, venues_path, static_path, load_json)

ASOF = "2026-06-08"
TS   = "2026-06-08_2336"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); args = ap.parse_args()
    only = {c.strip().upper() for c in args.only.split(",")} if args.only else None
    teams   = {t["team_id"]: t for t in load_json(teams_path(), [])}
    rank    = load_json(snap_path(ASOF, "team_rank"), {})
    squad   = load_json(snap_path(ASOF, "squad"), {})
    persons = {p["person_id"]: p for p in load_json(persons_path(), [])}
    matches = load_json(matches_path(), []); venues = load_json(venues_path(), {})
    groups  = load_json(static_path("groups"), {})
    wikidir = G.wiki_raw_dir()

    n = 0
    for code in sorted(teams):
        if only and code not in only:
            continue
        f = f"{BASE}/team_data/{TS}/{code}/summary.md"
        if not os.path.exists(f):
            continue
        skel = G.gen(code, teams, rank, squad, persons, matches, venues, groups, wikidir)  # 干净骨架(不写盘)
        mt = re.search(r"## 阵容全名单.*?(?=\n## |\Z)", skel, re.S)
        if not mt:
            continue
        new_seg = re.sub(r"^## 阵容全名单", "## ⑤ 阵容全名单", mt.group(0).rstrip())
        summary = open(f, encoding="utf-8").read()
        new_summary, cnt = re.subn(r"##[^\n]*阵容全名单.*?(?=\n## |\Z)",
                                   new_seg + "\n\n", summary, flags=re.S)
        mr = re.search(r"## 近期状态.*?(?=\n## |\Z)", skel, re.S)        # 近期状态也重刷(date 修好)
        if mr and "## 近期状态" in new_summary:
            new_summary = re.sub(r"## 近期状态.*?(?=\n## |\Z)", mr.group(0).rstrip() + "\n\n", new_summary, flags=re.S)
        if cnt:
            open(f, "w", encoding="utf-8").write(new_summary)
            n += 1
            print(f"  [{code}] 阵容表已替换（干净 + 身价）")
    print(f"\n替换 {n} 队阵容表（叙述段/市值段保留）")


if __name__ == "__main__":
    main()
