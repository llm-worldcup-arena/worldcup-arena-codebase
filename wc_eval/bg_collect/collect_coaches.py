#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教练采集：维基队页 infobox 的主教练 → persons 教练条目，并对齐 teams.json 的 coach_id。

复用 collect_squads 的维基直连/解析工具。raw 存 infobox 原文（section 0 wikitext）。
规范见 wc_skills/wc-data-collect。
跑：python3 collect_coaches.py [--only ESP,ARG]
"""
import json, re, os, argparse
from datetime import datetime
from collect_squads import (wiki_api, clean_link, slugify, WIKI_PAGE, strip_wiki,
                            fetch_full_page, persons_path, teams_path, load_json, dump_json, BASE)

TEAMS_PATH = teams_path()                       # 新结构: bg/teams.json


def run_ts():
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def fetch_lead_wikitext(page):
    """section 0 = 导语 + infobox。"""
    data = json.loads(wiki_api({"action": "parse", "page": page, "section": 0,
                                "prop": "wikitext", "format": "json"}))
    return data.get("parse", {}).get("wikitext", {}).get("*", "")


def extract_manager(wt):
    """从 infobox 取 manager / head coach 字段，去掉 flag 模板，取人名。"""
    for key in (r"manager", r"head\s*coach", r"coach"):
        m = re.search(r"\|\s*" + key + r"\s*=\s*([^\n]+)", wt, re.I)
        if m:
            val = re.sub(r"\{\{(?:flagicon|flag|nowrap|ubl)[^}]*\}\}", "", m.group(1), flags=re.I).strip()
            name = clean_link(val)
            name = re.sub(r"\{\{[^}]*\}\}", "", name).strip()   # 残余模板清掉
            if name and "{{" not in name and "[[" not in name:
                return name
    return None


def extract_coach_link(wt):
    """从队页 infobox Coach 字段取 (显示名, 维基页名)。页名常带消歧后缀，用于抓教练个人页。"""
    m = re.search(r"\|\s*(?:manager|head\s*coach|coach)\s*=\s*([^\n]+)", wt, re.I)
    if not m:
        return None, None
    val = re.sub(r"\{\{(?:flagicon|flag|nowrap|ubl)[^}]*\}\}", "", m.group(1), flags=re.I).strip()
    lm = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", val)
    if lm:
        return (lm.group(2) or lm.group(1)).strip(), lm.group(1).strip()
    name = re.sub(r"\{\{[^}]*\}\}", "", clean_link(val)).strip()
    return (name or None), None


def parse_coach_detail(wt):
    """教练个人页 infobox → coach 段（出生地 / 执教生涯 teams_coached / 起始年 / 国籍近似）。"""
    def grab(k):
        mm = re.search(r"^\|\s*" + k + r"\s*=\s*([^\n]+)", wt, re.M | re.I)
        return mm.group(1).strip() if mm else ""
    teams, since, tenure = [], "", ""
    for i in range(1, 16):
        club = clean_link(strip_wiki(grab(f"managerclubs{i}")))
        ym = re.search(r"(\d{4})", strip_wiki(grab(f"manageryears{i}")))
        if not club:
            continue
        teams.append(club)
        if ym and not since:
            since = ym.group(1)
        if ym:
            tenure = ym.group(1)                       # 最后一段（现队）起始年
    bp = strip_wiki(grab("birth_place"))
    return {"birth_place": bp,
            "nationality_guess": bp.split(",")[-1].strip() if bp else "",   # 出生地末段国家 ≈ 国籍
            "coach": {"career_since": since, "teams_coached": teams,
                      "tenure_with_current_since": tenure}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑指定队，逗号分隔")
    args = ap.parse_args()
    ts = run_ts()
    raw_dir = f"{BASE}/data_raw/{ts}"
    teams = load_json(TEAMS_PATH, [])
    persons = load_json(persons_path(), [])
    by_id = {p["person_id"]: p for p in persons}
    targets = [x.strip().upper() for x in args.only.split(",")] if args.only else None

    ok = 0
    for t in teams:
        tid = t["team_id"]
        if targets and tid not in targets:
            continue
        page = WIKI_PAGE.get(tid)
        if not page:
            print(f"  [{tid}] 不在 48 队"); continue
        try:
            wt = fetch_lead_wikitext(page)
        except Exception as e:
            print(f"  [{tid}] 抓取出错: {e}"); continue
        os.makedirs(raw_dir, exist_ok=True)
        open(f"{raw_dir}/{tid}.wikitext", "w", encoding="utf-8").write(wt)

        name = extract_manager(wt)
        if not name:
            print(f"  [{tid}] infobox 没找到教练"); continue
        t.setdefault("history", [])                      # 队·事件流(换帅/退赛)·起步空
        cid = slugify(name)
        t["coach_id"] = cid                              # 对齐 teams 的 coach_id 到全名 slug
        rec = by_id.get(cid, {})
        rec.update({"person_id": cid, "name_zh": rec.get("name_zh", ""), "name_en": name,
                    "nationality": rec.get("nationality", ""),
                    "roles": sorted(set(rec.get("roles", []) + ["coach"])),
                    "coach": rec.get("coach", {})})
        rec.setdefault("history", [])                    # 人·事件流·起步空
        by_id[cid] = rec
        ok += 1
        print(f"  [{tid}] {name} → {cid}")

    dump_json(TEAMS_PATH, teams)
    dump_json(persons_path(), sorted(by_id.values(), key=lambda p: p["person_id"]))
    print(f"\n完成 {ok} 队教练 → persons.json + teams.json（coach_id 对齐）  raw: data_raw/{ts}/")


if __name__ == "__main__":
    main()
