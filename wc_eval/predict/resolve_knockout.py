#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve known knockout fixtures into matches.json and the web KO schedule.

This is deliberately an add-on step for the knockout stage.  The old daily
prediction flow still starts from known HOME-AWAY pairs; this script only turns
bracket slots into known pairs when the source data is sufficient.

Examples:
  python3 resolve_knockout.py --dry-run
  python3 resolve_knockout.py --write-matches --write-web
  python3 resolve_knockout.py --write-matches --write-web --third-overrides M74=ECU,M77=SEN
"""
import argparse
import json
import os
import re
from copy import deepcopy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
DEFAULT_WEB = os.environ.get("WC_WEB_DIR") or os.path.join(os.path.dirname(ROOT), "worldcup_2026_web", "site")


# Canonical knockout rows from the current web schedule:
# [match_no, round_idx, date_key, et_time, slot_a, slot_b, venue_zh, venue_en]
KO_SLOTS = [
    (73, 0, "6.28", "15:00", "2A", "2B", "洛杉矶", "Los Angeles"),
    (74, 0, "6.29", "13:00", "1E", "3rd A/B/C/D/F", "休斯顿", "Houston"),
    (75, 0, "6.29", "16:00", "1F", "2C", "波士顿", "Boston"),
    (76, 0, "6.29", "21:00", "1C", "2F", "蒙特雷", "Monterrey"),
    (77, 0, "6.30", "13:00", "1I", "3rd C/D/F/G/H", "达拉斯", "Dallas"),
    (78, 0, "6.30", "17:00", "2E", "2I", "纽约", "New York"),
    (79, 0, "6.30", "21:00", "1A", "3rd C/E/F/H/I", "墨西哥城", "Mexico City"),
    (80, 0, "7.1", "12:00", "1L", "3rd E/H/I/J/K", "亚特兰大", "Atlanta"),
    (81, 0, "7.1", "16:00", "1D", "3rd B/E/F/I/J", "西雅图", "Seattle"),
    (82, 0, "7.1", "20:00", "1G", "3rd A/E/H/I/J", "旧金山湾区", "SF Bay Area"),
    (83, 0, "7.2", "15:00", "2K", "2L", "洛杉矶", "Los Angeles"),
    (84, 0, "7.2", "19:00", "1H", "2J", "多伦多", "Toronto"),
    (85, 0, "7.2", "21:00", "1B", "3rd E/F/G/I/J", "温哥华", "Vancouver"),
    (86, 0, "7.3", "14:00", "1J", "2H", "达拉斯", "Dallas"),
    (87, 0, "7.3", "18:00", "1K", "3rd D/E/I/J/L", "迈阿密", "Miami"),
    (88, 0, "7.3", "21:30", "2D", "2G", "堪萨斯城", "Kansas City"),
]

ROUND_BY_IDX = {0: "r32", 1: "r16", 2: "qf", 3: "sf", 4: "final"}
VENUE_BY_WEB_CITY = {
    "Los Angeles": "sofi_stadium",
    "Houston": "nrg_stadium",
    "Boston": "gillette_stadium",
    "Monterrey": "estadio_bbva",
    "Dallas": "at_t_stadium",
    "New York": "metlife_stadium",
    "Mexico City": "estadio_azteca",
    "Atlanta": "mercedes_benz_stadium",
    "Seattle": "lumen_field",
    "SF Bay Area": "levi_s_stadium",
    "Toronto": "bmo_field",
    "Vancouver": "bc_place",
    "Miami": "hard_rock_stadium",
    "Kansas City": "arrowhead_stadium",
    "Philadelphia": "lincoln_financial_field",
    "New York / NJ": "metlife_stadium",
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def parse_score(score):
    m = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$", str(score or ""))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def result_key(match):
    return f"{match['team_a']}_vs_{match['team_b']}"


def head_to_head_points(team, tied, group_matches, results):
    pts = gf = ga = 0
    for match in group_matches:
        a, b = match["team_a"], match["team_b"]
        if team not in (a, b) or a not in tied or b not in tied:
            continue
        score = parse_score((results.get(result_key(match)) or {}).get("score"))
        if not score:
            continue
        h, w = score
        if team == a:
            gf += h
            ga += w
            pts += 3 if h > w else 1 if h == w else 0
        else:
            gf += w
            ga += h
            pts += 3 if w > h else 1 if h == w else 0
    return pts, gf - ga, gf


def break_ties(order, stats, group_matches, results):
    """Sort by FIFA-style group criteria, with team code only as final fallback."""
    buckets = {}
    for team in order:
        s = stats[team]
        buckets.setdefault((s["pts"], s["gd"], s["gf"]), []).append(team)

    ranked = []
    for key in sorted(buckets, reverse=True):
        tied = buckets[key]
        if len(tied) == 1:
            ranked.extend(tied)
            continue
        ranked.extend(sorted(
            tied,
            key=lambda t: (
                -head_to_head_points(t, set(tied), group_matches, results)[0],
                -head_to_head_points(t, set(tied), group_matches, results)[1],
                -head_to_head_points(t, set(tied), group_matches, results)[2],
                t,
            ),
        ))
    return ranked


def compute_group_rankings(matches, results, groups):
    rankings = {}
    incomplete = []
    for group, teams in groups.items():
        stats = {team: {"pts": 0, "gf": 0, "ga": 0, "gd": 0, "played": 0} for team in teams}
        group_matches = [m for m in matches if m.get("round") == "group" and m.get("group") == group]
        for match in group_matches:
            score = parse_score((results.get(result_key(match)) or {}).get("score"))
            if not score:
                incomplete.append(match["match_id"])
                continue
            h, a = score
            ta, tb = match["team_a"], match["team_b"]
            stats[ta]["played"] += 1
            stats[tb]["played"] += 1
            stats[ta]["gf"] += h
            stats[ta]["ga"] += a
            stats[tb]["gf"] += a
            stats[tb]["ga"] += h
            if h > a:
                stats[ta]["pts"] += 3
            elif a > h:
                stats[tb]["pts"] += 3
            else:
                stats[ta]["pts"] += 1
                stats[tb]["pts"] += 1
        for s in stats.values():
            s["gd"] = s["gf"] - s["ga"]
        raw = sorted(teams, key=lambda t: (stats[t]["pts"], stats[t]["gd"], stats[t]["gf"], t), reverse=True)
        rankings[group] = [{"rank": i + 1, "team": t, **stats[t]} for i, t in enumerate(break_ties(raw, stats, group_matches, results))]
    return rankings, incomplete


def best_thirds(rankings):
    thirds = []
    for group, table in rankings.items():
        if len(table) >= 3:
            row = table[2]
            thirds.append({"group": group, **row})
    return sorted(thirds, key=lambda r: (-r["pts"], -r["gd"], -r["gf"], r["group"]))[:8]


def parse_overrides(raw):
    overrides = {}
    for part in (raw or "").split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise SystemExit(f"✗ --third-overrides 格式应为 M74=ECU 或 74=ECU: {part}")
        key, team = [x.strip().upper() for x in part.split("=", 1)]
        if not key.startswith("M"):
            key = f"M{key}"
        overrides[key] = team
    return overrides


def slot_label_zh(slot):
    if re.match(r"^[123][A-L]$", slot):
        return f"{slot[1]}组第{slot[0]}"
    m = re.match(r"^3rd ([A-L](?:/[A-L])*)$", slot)
    if m:
        return f"第3名 {m.group(1)}"
    return slot


def resolve_slot(slot, rankings, third_groups, overrides, match_id):
    if re.match(r"^[12][A-L]$", slot):
        rank, group = int(slot[0]), slot[1]
        table = rankings.get(group) or []
        if len(table) >= rank:
            return table[rank - 1]["team"], None
        return None, f"{slot}: 小组排名不足"

    m = re.match(r"^3rd ([A-L](?:/[A-L])*)$", slot)
    if not m:
        return None, f"{slot}: 非当前脚本可解析席位"

    allowed = m.group(1).split("/")
    qualified = [g for g in allowed if g in third_groups]
    override = overrides.get(match_id)
    if override:
        by_team = {rankings[g][2]["team"]: g for g in qualified if len(rankings.get(g, [])) >= 3}
        if override not in by_team:
            teams = ", ".join(f"{rankings[g][2]['team']}({g})" for g in qualified)
            return None, f"{slot}: override {override} 不在候选晋级第三名中; 候选={teams or '无'}"
        return override, None
    if len(qualified) == 1:
        group = qualified[0]
        return rankings[group][2]["team"], None
    if not qualified:
        return None, f"{slot}: 候选组没有晋级第三名"
    teams = ", ".join(f"{rankings[g][2]['team']}({g})" for g in qualified)
    return None, f"{slot}: 多个候选第三名已晋级,需 --third-overrides {match_id}=TEAM; 候选={teams}"


def date_iso(date_key):
    month, day = date_key.split(".")
    return f"2026-{int(month):02d}-{int(day):02d}"


def kickoff_ts(date_key, et_time):
    hour, minute = [int(x) for x in et_time.split(":")]
    date = date_iso(date_key)
    if hour == 24:
        hour = 0
    return f"{date}T{hour:02d}:{minute:02d}:00-04:00"


def display_maps():
    teams = load_json(f"{RUNS}/data_reference/teams.json")
    zh = {t["team_id"]: t.get("name_zh") or t["team_id"] for t in teams}
    en = {t["team_id"]: t.get("name_en") or t["team_id"] for t in teams}
    # Align with the keys used by worldcup-app.js / WC.T.
    en.update({
        "USA": "USA",
        "BIH": "Bosnia & Herzegovina",
        "CIV": "Côte d'Ivoire",
        "COD": "DR Congo",
        "CUW": "Curaçao",
        "CZE": "Czechia",
        "KOR": "South Korea",
        "KSA": "Saudi Arabia",
        "NZL": "New Zealand",
        "RSA": "South Africa",
        "TUR": "Türkiye",
        "URU": "Uruguay",
    })
    return zh, en


def resolve_r32(matches, results, groups, overrides):
    rankings, incomplete = compute_group_rankings(matches, results, groups)
    thirds = best_thirds(rankings)
    third_groups = {r["group"] for r in thirds}

    resolved = []
    unresolved = []
    for no, round_idx, dkey, et, a_slot, b_slot, venue_zh, venue_en in KO_SLOTS:
        match_id = f"M{no}"
        home, err_a = resolve_slot(a_slot, rankings, third_groups, overrides, match_id)
        away, err_b = resolve_slot(b_slot, rankings, third_groups, overrides, match_id)
        row = {
            "match_id": match_id,
            "match_no": no,
            "round_idx": round_idx,
            "round": ROUND_BY_IDX[round_idx],
            "date_key": dkey,
            "date": date_iso(dkey),
            "et_time": et,
            "kickoff_ts": kickoff_ts(dkey, et),
            "venue_zh": venue_zh,
            "venue_en": venue_en,
            "venue_id": VENUE_BY_WEB_CITY[venue_en],
            "slot_a": a_slot,
            "slot_b": b_slot,
            "team_a": home,
            "team_b": away,
        }
        errors = [e for e in (err_a, err_b) if e]
        if home and away and not errors:
            resolved.append(row)
        else:
            row["reason"] = "; ".join(errors)
            unresolved.append(row)
    return rankings, thirds, resolved, unresolved, incomplete


def update_matches(path, resolved, replace=False):
    matches = load_json(path)
    by_id = {m.get("match_id"): i for i, m in enumerate(matches)}
    added = []
    changed = []

    for row in resolved:
        rec = {
            "match_id": row["match_id"],
            "edition": 2026,
            "round": row["round"],
            "group": None,
            "date": row["date"],
            "kickoff_ts": row["kickoff_ts"],
            "venue_id": row["venue_id"],
            "team_a": row["team_a"],
            "team_b": row["team_b"],
            "referee_id": None,
            "coach_a": None,
            "coach_b": None,
            "result": None,
        }
        if row["match_id"] in by_id:
            idx = by_id[row["match_id"]]
            old = matches[idx]
            if old != rec:
                if not replace:
                    raise SystemExit(f"✗ {row['match_id']} 已存在但内容不同;确认后加 --replace-existing")
                matches[idx] = rec
                changed.append(row["match_id"])
            continue
        matches.append(rec)
        added.append(row["match_id"])

    matches.sort(key=lambda m: int(str(m.get("match_id", "M0")).lstrip("M") or "0"))
    dump_json(path, matches)
    return added, changed


def parse_web_rows(text):
    row_re = re.compile(
        r'(\[\s*)(\d+)(\s*,\s*)(\d+)(\s*,\s*)"([^"]+)"(\s*,\s*)"([^"]+)"'
        r'(\s*,\s*)"([^"]*)"(\s*,\s*)"([^"]*)"(\s*,\s*)"([^"]*)"(\s*,\s*)"([^"]*)"'
        r'(\s*,\s*)"([^"]*)"(\s*,\s*)"([^"]*)"(\s*\])'
    )
    rows = {}
    for m in row_re.finditer(text):
        rows[int(m.group(2))] = m
    return row_re, rows


def update_web_knockout(path, resolved, unresolved, replace=False):
    text = open(path, encoding="utf-8").read()
    row_re, rows = parse_web_rows(text)
    zh, en = display_maps()
    res_by_no = {r["match_no"]: r for r in resolved}
    unres_by_no = {r["match_no"]: r for r in unresolved}

    def repl(match):
        no = int(match.group(2))
        current_a = match.group(12)
        current_b = match.group(16)
        current_resolved = current_a in set(en.values()) and current_b in set(en.values())
        if no in res_by_no:
            row = res_by_no[no]
            already = current_a == en[row["team_a"]] and current_b == en[row["team_b"]]
            if current_resolved and not already and not replace:
                raise SystemExit(f"✗ web {path} 的 M{no} 已是实队且与解析结果不同;确认后加 --replace-existing")
            vals = [
                str(no),
                str(row["round_idx"]),
                row["date_key"],
                row["et_time"],
                zh[row["team_a"]],
                en[row["team_a"]],
                zh[row["team_b"]],
                en[row["team_b"]],
                row["venue_zh"],
                row["venue_en"],
            ]
        elif no in unres_by_no:
            if current_resolved and not replace:
                return match.group(0)
            row = unres_by_no[no]
            vals = [
                str(no),
                str(row["round_idx"]),
                row["date_key"],
                row["et_time"],
                slot_label_zh(row["slot_a"]),
                row["slot_a"],
                slot_label_zh(row["slot_b"]),
                row["slot_b"],
                row["venue_zh"],
                row["venue_en"],
            ]
        else:
            return match.group(0)
        return (f'[{vals[0]}, {vals[1]}, "{vals[2]}", "{vals[3]}", '
                f'"{vals[4]}", "{vals[5]}", "{vals[6]}", "{vals[7]}", '
                f'"{vals[8]}", "{vals[9]}"]')

    missing = sorted(set(res_by_no) - set(rows))
    if missing:
        raise SystemExit(f"✗ web knockout 缺这些 matchNo: {missing}")
    new = row_re.sub(repl, text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)


def print_report(rankings, thirds, resolved, unresolved, incomplete):
    print("小组排名:")
    for group in sorted(rankings):
        table = rankings[group]
        parts = [f"{r['rank']}.{r['team']} {r['pts']}分 GD{r['gd']} GF{r['gf']}" for r in table]
        print(f"  {group}: " + " | ".join(parts))
    if incomplete:
        print("⚠️ 小组赛结果不完整:", ", ".join(incomplete))

    print("\n最佳第三名(前8晋级):")
    print("  " + " | ".join(f"{r['team']}({r['group']}) {r['pts']}分 GD{r['gd']} GF{r['gf']}" for r in thirds))

    print("\n已可落地的 32 强对阵:")
    for r in resolved:
        print(f"  {r['match_id']} {r['date']} {r['et_time']}ET {r['team_a']} vs {r['team_b']} @ {r['venue_en']}"
              f"  ({r['slot_a']} vs {r['slot_b']})")

    print("\n仍需暂定/人工指定的场次:")
    for r in unresolved:
        print(f"  {r['match_id']} {r['slot_a']} vs {r['slot_b']} -> {r.get('reason')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印解析结果,不写文件")
    ap.add_argument("--write-matches", action="store_true", help="把已确定对阵写入 wc_runs/data_reference/matches.json")
    ap.add_argument("--write-web", action="store_true", help="把已确定对阵写入 worldcup-knockout.js,未定保留暂定占位")
    ap.add_argument("--replace-existing", action="store_true", help="允许覆盖已有 Mxx 记录/网页实队")
    ap.add_argument("--third-overrides", default="", help="第三名歧义手工指定,如 M74=ECU,M77=SEN")
    ap.add_argument("--web-dir", default=DEFAULT_WEB)
    args = ap.parse_args()

    matches_path = f"{RUNS}/data_reference/matches.json"
    results_path = f"{RUNS}/archive/results.json"
    groups_path = f"{RUNS}/data_reference/static/groups.json"
    overrides = parse_overrides(args.third_overrides)

    matches = load_json(matches_path)
    results_doc = load_json(results_path)
    groups = load_json(groups_path)
    rankings, thirds, resolved, unresolved, incomplete = resolve_r32(
        matches, results_doc.get("matches") or {}, groups, overrides
    )
    print_report(rankings, thirds, resolved, unresolved, incomplete)

    if args.dry_run or not (args.write_matches or args.write_web):
        print("\nDRY-RUN:未写文件。正式写入用 --write-matches 和/或 --write-web。")
        return

    if args.write_matches:
        before = deepcopy(load_json(matches_path))
        added, changed = update_matches(matches_path, resolved, replace=args.replace_existing)
        after = load_json(matches_path)
        print(f"\n✅ matches.json 已更新:新增 {added or '无'} · 覆盖 {changed or '无'} · {len(before)}→{len(after)} 场")

    if args.write_web:
        web_path = os.path.join(args.web_dir, "worldcup-knockout.js")
        update_web_knockout(web_path, resolved, unresolved, replace=args.replace_existing)
        print(f"✅ worldcup-knockout.js 已更新:{web_path}")


if __name__ == "__main__":
    main()
