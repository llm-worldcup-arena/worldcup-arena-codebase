#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""赛事结构采集（块5）：维基「2026 FIFA World Cup Group X」12 子页 → matches.json（小组赛赛程）。

每场比赛是 Lua 模块调用（不是普通模板）：
  {{#invoke:football box|main |date={{Start date|2026|6|11}} |time=… |team1={{#invoke:flag|fb-rt|MEX}}
   |score={{score link|…|Match 1}} |team2={{#invoke:flag|fb|RSA}} |stadium=[[球场]], [[城市]] …}}
赛果(goals/score)是比赛日动态、不属 background，这里只取赛程结构（date/对阵/场地）。

跑：python3 collect_fixtures.py
"""
import json, re, unicodedata
from collect_squads import (strip_wiki, MONTHS, dump_json, fetch_save, run_ts, BASE,
                            matches_path, venues_path, static_path)

GROUPS = "ABCDEFGHIJKL"          # 48 队 12 组


def vid(name):
    """球场名 → venue_id（去重音 / 小写 / 非字母数字转 _）。"""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")


def fetch_group(letter, raw_dir=None):
    return fetch_save(f"2026 FIFA World Cup Group {letter}", raw_dir, f"fixt_group_{letter}.wikitext")


def extract_box_blocks(wt):
    """括号配平提取每个 {{#invoke:football box … }} 整块（容忍内部嵌套模板）。"""
    key, blocks, i = "{{#invoke:football box", [], 0
    while True:
        s = wt.find(key, i)
        if s < 0:
            break
        depth, j = 0, s
        while j < len(wt):
            if wt[j:j+2] == "{{":
                depth += 1; j += 2
            elif wt[j:j+2] == "}}":
                depth -= 1; j += 2
                if depth == 0:
                    break
            else:
                j += 1
        blocks.append(wt[s:j]); i = j
    return blocks


def field(block, name):
    m = re.search(r"\|\s*" + name + r"\s*=\s*([^\n]*)", block)
    return m.group(1).strip() if m else ""


def parse_team(v):
    """{{#invoke:flag|fb-rt|MEX}} → MEX（取三字码）。"""
    m = re.search(r"\|([A-Z]{3})\s*\}\}", v) or re.search(r"\|([A-Z]{3})\s*\|", v)
    return m.group(1) if m else ""


def parse_match(block, group):
    dm = re.search(r"Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", field(block, "date"))
    date = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else ""
    st = field(block, "stadium")
    links = re.findall(r"\[\[([^\]|]+)", st)
    vname = links[0] if links else strip_wiki(st)
    mm = re.search(r"Match (\d+)", field(block, "score"))
    return {
        "match_id": f"M{mm.group(1)}" if mm else None,
        "edition": 2026, "round": "group", "group": group,
        "date": date, "kickoff_ts": None,
        "venue_id": vid(vname) if vname else None,
        "team_a": parse_team(field(block, "team1")),
        "team_b": parse_team(field(block, "team2")),
        "referee_id": None, "coach_a": None, "coach_b": None,
        "result": None,
        "_venue_name": vname, "_city": links[1] if len(links) > 1 else "",   # 临时·供 venues 聚合
    }


def fetch_knockout(raw_dir=None):
    return fetch_save("2026 FIFA World Cup knockout stage", raw_dir, "fixt_knockout.wikitext")


def md_to_date(s):
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})", s)
    return (f"2026-{MONTHS[m.group(1).capitalize()]:02d}-{int(m.group(2)):02d}"
            if m and m.group(1).capitalize() in MONTHS else "")


def parse_bracket(wt):
    """knockout 子页 Bracket 段（RoundN N32）→ R32 的 16 场占位对阵（实队小组赛后才定）。"""
    m = re.search(r'<section begin="?Bracket"?\s*/?>(.*?)<section end="?Bracket"?', wt, re.S)
    if not m:
        return []
    seg = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
    out = []
    for ln in seg.split("\n"):
        if "Group" in ln and ("Winner" in ln or "Runner" in ln or "3rd" in ln):
            ln = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", ln)   # [[A|B]]→B，免得链接内的 | 干扰切分
            p = ln.split("|")
            if len(p) < 5:
                continue
            dp = p[1].split("–")
            out.append({"round": "R32", "date": md_to_date(dp[0]),
                        "venue": strip_wiki(dp[1]) if len(dp) > 1 else "",
                        "slot_a": strip_wiki(p[2]), "slot_b": strip_wiki(p[4])})
    return out


def main(ts=None):
    raw_dir = f"{BASE}/data_raw/{ts or run_ts()}"             # 赛程子页原文存这（raw 全量）
    matches = []
    for g in GROUPS:
        boxes = extract_box_blocks(fetch_group(g, raw_dir))
        matches += [parse_match(b, g) for b in boxes]
        print(f"  Group {g}: {len(boxes)} 场")
    matches.sort(key=lambda m: (m["date"], int((m["match_id"] or "M0")[1:])))

    # venues（实体·从 matches 聚合 + 海拔/气候/草皮留字段 + history）
    venues = {}
    for m in matches:
        v = m.get("venue_id")
        if v and v not in venues:
            venues[v] = {"name": m.get("_venue_name", ""), "city": m.get("_city", ""),
                         "altitude_m": None, "climate": None, "surface": "grass", "history": []}

    # groups（纯关系·从 matches 每组的队聚合）
    groups = {}
    for m in matches:
        groups.setdefault(m["group"], [])
        for t in (m["team_a"], m["team_b"]):
            if t and t not in groups[m["group"]]:
                groups[m["group"]].append(t)

    # matches 落盘只留 schema 字段（去掉临时 _venue_name/_city）
    KEEP = ["match_id", "edition", "round", "group", "date", "kickoff_ts", "venue_id",
            "team_a", "team_b", "referee_id", "coach_a", "coach_b", "result"]
    dump_json(matches_path(), [{k: m.get(k) for k in KEEP} for m in matches])
    dump_json(venues_path(), venues)
    dump_json(static_path("groups"), groups)

    # bracket（淘汰赛 R32 占位结构）
    r32 = parse_bracket(fetch_knockout(raw_dir))
    dump_json(static_path("bracket"), {"R32": r32, "note": "占位，实队小组赛后定"})

    print(f"  matches {len(matches)} → bg/matches.json | venues {len(venues)} → bg/venues.json")
    print(f"  groups {len(groups)} 组 → bg/static/groups.json | bracket R32 {len(r32)} → bg/static/bracket.json")


if __name__ == "__main__":
    main()
