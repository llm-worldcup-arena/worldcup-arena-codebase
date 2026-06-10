#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Transfermarkt 身价【补进】已生成的 team_data summary 阵容表 + 末尾加「球队市值段」。
阵容表**有身价列就替换、没有就在「国脚」列后插入**；搜错人(tm_verified=False)记 —⚠️。
**绝不动叙述段**，幂等可重跑。

跑：python3 update_summary_value.py [--only ARG]
"""
import re, os, argparse, statistics
from collect_squads import BASE, persons_path, snap_path, load_json

ASOF = "2026-06-08"
TS   = "2026-06-08_2336"
SEG_TITLE = "## 球队市值与年龄结构"


def fmt(eur):
    if not eur: return "—"
    if eur >= 1e8: return f"{eur/1e8:.2f}亿€"
    if eur >= 1e6: return f"{eur/1e6:.0f}M€"
    return f"{eur/1e3:.0f}K€"


def update_team(code, by_id, squad):
    f = f"{BASE}/team_data/{TS}/{code}/summary.md"
    if not os.path.exists(f):
        return None
    txt = re.split(r"\n" + re.escape(SEG_TITLE), open(f, encoding="utf-8").read())[0].rstrip()
    no2pid = {pl.get("no"): pl["person_id"] for pl in squad.get(code, {}).get("players", [])}

    out, members, total, all_ages = [], [], 0, []
    mode, col, pend_sep = None, None, False
    for ln in txt.split("\n"):
        cells = ln.split("|")
        # 说明行补「身价·」
        if ln.startswith(">") and "国脚" in ln and "俱乐部生涯" in ln and "身价" not in ln:
            out.append(ln.replace("国脚(场/球)·", "国脚(场/球)·身价·")); continue
        # 阵容表表头：有身价列→替换；没有→在「国脚」后插
        if len(cells) >= 10 and cells[1].strip() == "号" and "俱乐部生涯" in ln:
            if "身价" in ln:
                mode = "replace"; col = next(i for i, c in enumerate(cells) if c.strip() == "身价")
            else:
                mode = "insert"; col = next(i for i, c in enumerate(cells) if c.strip() == "国脚") + 1
                cells.insert(col, " 身价 "); ln = "|".join(cells); pend_sep = True
            out.append(ln); continue
        # 表头紧跟的分隔行（插入模式才补一格）
        if pend_sep and re.match(r"^\|[\s:|\-]+\|?\s*$", ln):
            cells.insert(col, "---"); out.append("|".join(cells)); pend_sep = False; continue
        pend_sep = False
        # 球员行
        m = re.match(r"^\|\s*(\d+)\s*\|", ln)
        if mode and col and m and len(cells) > col:
            pid = no2pid.get(int(m.group(1)))
            plr = by_id.get(pid, {}).get("player", {}) if pid else {}
            mv = plr.get("market_value_eur")
            cell = " —⚠️ " if plr.get("tm_verified") is False else (f" {fmt(mv)} " if mv else " — ")
            if mode == "insert":
                cells.insert(col, cell)
            else:
                cells[col] = cell
            ln = "|".join(cells)
            p = by_id.get(pid, {}); bd = p.get("birthdate") or ""
            if re.match(r"\d{4}-\d{2}-\d{2}$", bd):
                yy, mm, dd = map(int, bd.split("-")); all_ages.append(2026 - yy - ((mm, dd) > (6, 9)))
            if mv:
                total += mv
                members.append((p.get("name_zh") or p.get("name_en"), mv))
        out.append(ln)

    if not members:
        return None
    ages = all_ages
    top = sorted(members, key=lambda x: -x[1])[:3]
    seg = [
        "", SEG_TITLE + "（汇总自球员身价，Transfermarkt，asof 2026-06）",
        f"- 阵容总身价：**{fmt(total)}**（{len(members)} 名有估值球员合计）",
        (f"- 平均年龄：**{statistics.mean(ages):.1f} 岁**（最年长 {max(ages)}、最年轻 {min(ages)}）" if ages else "- 平均年龄：—"),
        "- 身价 Top3：" + "、".join(f"{n}（{fmt(v)}）" for n, v in top),
    ]
    open(f, "w", encoding="utf-8").write("\n".join(out).rstrip() + "\n" + "\n".join(seg) + "\n")
    return total, len(members)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    only = {c.strip().upper() for c in args.only.split(",")} if args.only else None
    by_id = {p["person_id"]: p for p in load_json(persons_path(), [])}
    squad = load_json(snap_path(ASOF, "squad"), {})
    n = 0
    for code in sorted(squad):
        if only and code not in only:
            continue
        r = update_team(code, by_id, squad)
        if r:
            print(f"  [{code}] 总身价 {fmt(r[0])}（{r[1]} 人）")
            n += 1
    print(f"\n补身价 + 市值段完成 {n} 队（叙述段未动）")


if __name__ == "__main__":
    main()
