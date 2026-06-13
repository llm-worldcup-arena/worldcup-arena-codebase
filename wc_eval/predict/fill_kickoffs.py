#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【一次性·补开球时间】把 matches.json 里空着的 kickoff_ts 从网页赛程(worldcup-app.js 的 FIX)填上。
FIX 每行 = [日期, 组, 主队英文, 客队英文, 城市中, 城市英, 美东开球时间]。美东=EDT(UTC-4)。
填进 matches.json: kickoff_ts = "2026-06-11T15:00:00-04:00"(ISO,带美东时区);供 match_header 显示美东+北京。

跑:python3 fill_kickoffs.py            # 写入 matches.json(只填有时间的场次,已填的不动)
   python3 fill_kickoffs.py --dry      # 只看匹配/未匹配,不写
"""
import os, re, json, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATCHES = f"{ROOT}/wc_runs/data_reference/matches.json"
TEAMS = f"{ROOT}/wc_runs/data_reference/teams.json"
WEB_APP = os.environ.get("WC_WEB_DIR") and f"{os.environ['WC_WEB_DIR']}/worldcup-app.js" \
    or f"{os.path.dirname(ROOT)}/worldcup_2026_web/site/worldcup-app.js"

# web FIX 显示名 → FIFA 码(与 teams.json name_en 不一致的别名)
ALIAS = {
    "South Korea": "KOR", "Czechia": "CZE", "USA": "USA", "Bosnia & Herzegovina": "BIH",
    "Côte d'Ivoire": "CIV", "Türkiye": "TUR", "DR Congo": "COD", "Cape Verde": "CPV",
    "Curaçao": "CUW", "Saudi Arabia": "KSA", "New Zealand": "NZL",
}


def name_to_code():
    teams = json.load(open(TEAMS, encoding="utf-8"))
    m = {t.get("name_en", ""): t["team_id"] for t in teams if t.get("name_en")}
    m.update(ALIAS)
    return m


def parse_fix():
    """从 worldcup-app.js 抽 FIX 行 → [(date, home_en, away_en, et_time), ...]。"""
    txt = open(WEB_APP, encoding="utf-8").read()
    block = re.search(r"var FIX\s*=\s*\[(.*?)\];", txt, re.S)
    rows = re.findall(r'\["([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)"\]',
                      block.group(1) if block else "")
    out = []
    for date, grp, home, away, city_cn, city_en, t in rows:
        mm, dd = date.split(".")                      # "6.11" → 2026-06-11
        iso = f"2026-{int(mm):02d}-{int(dd):02d}"
        out.append((iso, home, away, t))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    n2c = name_to_code()
    matches = json.load(open(MATCHES, encoding="utf-8"))
    by_pair = {}                                       # (frozenset codes, date) → match dict
    for m in matches:
        by_pair[(frozenset((m["team_a"], m["team_b"])), m["date"])] = m

    filled, skipped_notime, unmatched = 0, 0, []
    for iso, home, away, t in parse_fix():
        if not t:
            skipped_notime += 1; continue
        hc, ac = n2c.get(home), n2c.get(away)
        if not hc or not ac:
            unmatched.append(f"{home}({hc}) / {away}({ac})  名字未映射"); continue
        m = by_pair.get((frozenset((hc, ac)), iso))
        if not m:
            unmatched.append(f"{hc} vs {ac} {iso}  matches.json 无此场"); continue
        m["kickoff_ts"] = f"{iso}T{t}:00-04:00"        # 美东 EDT
        filled += 1

    print(f"  匹配并填入 kickoff_ts: {filled} 场")
    print(f"  FIX 里无时间(跳过): {skipped_notime} 场")
    if unmatched:
        print("  ⚠️ 未匹配:"); [print("    -", x) for x in unmatched]
    if a.dry:
        print("  (--dry 未写)"); return
    json.dump(matches, open(MATCHES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  ✅ 已写 matches.json;现有 kickoff_ts 的场次: {sum(1 for m in matches if m.get('kickoff_ts'))}/{len(matches)}")


if __name__ == "__main__":
    main()
