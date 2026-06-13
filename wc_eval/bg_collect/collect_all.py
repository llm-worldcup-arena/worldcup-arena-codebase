#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""世界杯 2026 · bg 一键总入口 —— 一次收集 = 一个完整快照。

跑这一个，按【同一个时间戳】把该采的全采齐，raw 落【一个】目录：
  [1] 48 队维基【整页全文】 → 同一份原文里解析【球员阵容】+【主教练】
  [2] FIFA 当前排名（维基模板 {{FIFA World Rankings}} expandtemplates 展开）→ team_rank
  [3] Elo（eloratings.net/World.tsv）→ team_rank
  [4] 中文名（enwiki → Wikidata zh-cn 大陆简体）→ persons

raw : wc_runs/data_raw/<采集时分>/        ← 一个目录 = 一次收集（类型靠文件名区分，不另套子文件夹）
        <TEAM>.wikitext                  48 队整页全文（球员+教练+世界杯史都在里面）
        fifa_rankings.txt                FIFA 排名模板展开留底
        World.tsv                        Elo 原文
data: data/static/persons.json           人物（增量）
      data/bg/asof=<日>/squad.json       阵容快照
      data/bg/asof=<日>/team_rank.json   FIFA + Elo

跑：python3 collect_all.py                          # 全 48 队一次采齐
    python3 collect_all.py --only ESP,ARG           # 先测几队
    python3 collect_all.py --only ESP --skip-names  # 测试时跳过（较慢的）中文名
"""
import os, re, json, argparse
from collect_squads import (
    run_ts, fetch_full_page, fetch_save, parse_squad, parse_team_infobox, wiki_api, MONTHS,
    upsert_persons, update_squad, slugify, WIKI_PAGE, BASE,
    persons_path, teams_path, snap_path, load_json, dump_json)
from collect_coaches import extract_coach_link, parse_coach_detail, TEAMS_PATH
import collect_elo, collect_names, collect_fixtures

ASOF = "2026-06-08"                        # 本次快照日期（data 按日）


def upsert_coach(cid, name, detail=None):
    """教练写进 persons（增量）：填出生地/国籍/执教生涯，保留已有中文名。"""
    detail = detail or {}
    persons = load_json(persons_path(), [])
    by_id = {p["person_id"]: p for p in persons}
    rec = by_id.get(cid, {})
    rec.update({"person_id": cid, "name_zh": rec.get("name_zh", ""), "name_en": name,
                "birth_place": detail.get("birth_place", rec.get("birth_place", "")),
                "nationality": detail.get("nationality_guess") or rec.get("nationality", ""),
                "roles": sorted(set(rec.get("roles", []) + ["coach"])),
                "coach": detail.get("coach", rec.get("coach", {}))})
    rec.setdefault("history", [])                            # 人·事件流·起步空
    by_id[cid] = rec
    dump_json(persons_path(), sorted(by_id.values(), key=lambda p: p["person_id"]))


def parse_fifa_rank(s):
    """'<nowiki/> 2 [[Decrease]] 1 (1 April 2026)…' → (当前排名, 发布日)。第一个数字=当前排名。"""
    m = re.search(r"\d+", s)
    rank = int(m.group()) if m else None
    dm = re.search(r"\((\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\)", s)
    asof = ""
    if dm and dm.group(2).capitalize() in MONTHS:
        asof = f"{dm.group(3)}-{MONTHS[dm.group(2).capitalize()]:02d}-{int(dm.group(1)):02d}"
    return rank, asof


def fetch_fifa_ranks(codes, raw_dir):
    """一次性 expandtemplates 展开所有 {{FIFA World Rankings|CODE}} → {code:(rank,asof)}；展开文留底。"""
    SEP = "@@@FIFA@@@"
    text = f"\n{SEP}\n".join("{{FIFA World Rankings|%s}}" % c for c in codes)
    d = json.loads(wiki_api({"action": "expandtemplates", "text": text,
                             "prop": "wikitext", "format": "json"}))
    exp = d.get("expandtemplates", {}).get("wikitext", "")
    open(f"{raw_dir}/fifa_rankings.txt", "w", encoding="utf-8").write(exp)
    parts = exp.split(SEP)
    return {c: parse_fifa_rank(p) for c, p in zip(codes, parts)}


def write_fifa_ranks(asof, franks):
    rank_path = snap_path(asof, "team_rank")               # 新结构: bg/snapshots/asof=日/
    rank = load_json(rank_path, {})
    hit = 0
    for code, (r, fa) in franks.items():
        if r is None:
            continue
        d = rank.get(code) if isinstance(rank.get(code), dict) else {}
        d["fifa_rank"] = r
        d["fifa_asof"] = fa
        rank[code] = d
        hit += 1
    dump_json(rank_path, rank)
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑指定队，逗号分隔，如 ESP,ARG（测试用）")
    ap.add_argument("--asof", default=ASOF, help="本次快照日期")
    ap.add_argument("--skip-names", action="store_true", help="跳过中文名（测试用，省时间）")
    args = ap.parse_args()
    from naming_util import valid_asof
    valid_asof(args.asof)        # 命名规范强制:asof 必须 YYYY-MM-DD
    codes = [c.strip().upper() for c in args.only.split(",")] if args.only else list(WIKI_PAGE)
    codes = [c for c in codes if c in WIKI_PAGE]

    ts = run_ts()
    raw_dir = f"{BASE}/data_raw/{ts}"
    os.makedirs(raw_dir, exist_ok=True)
    print(f"=== 一次收集  ts={ts}  asof={args.asof}  {len(codes)} 队 ===")
    print(f"raw 一个目录: data_raw/{ts}/\n")

    teams = load_json(TEAMS_PATH, [])
    teams_by_id = {t.get("team_id"): t for t in teams}
    for code in WIKI_PAGE:                                  # 没有就建 team 骨架(带 history + 待采字段留好)
        t = teams_by_id.setdefault(code, {})
        t["team_id"] = code
        t.setdefault("history", [])                         # 队·事件流(换帅/退赛)
        for f in ("name_zh", "wc_titles", "wc_best", "wc_appearances", "qualifying"):
            t.setdefault(f, None)                           # 待采:中文名/世界杯史/预选赛(块6)
    teams = list(teams_by_id.values())

    # [1] 整页全文 → 球员 + 教练（同一份原文）
    print(f"[1/5] 48 队整页全文 → 球员 + 教练")
    ok_sq = ok_co = 0
    for code in codes:
        try:
            wt = fetch_full_page(WIKI_PAGE[code])
        except Exception as e:
            print(f"  [{code}] 整页抓取失败: {e}"); continue
        open(f"{raw_dir}/{code}.wikitext", "w", encoding="utf-8").write(wt)   # 整页全文留底
        players, meta = parse_squad(wt)
        if players:
            upsert_persons(code, players, meta["caps_asof"])
            update_squad(args.asof, code, players, meta)
            ok_sq += 1
        if code in teams_by_id:                         # 球队补充字段（整页 infobox，raw 现成）
            for k, v in parse_team_infobox(wt).items():
                if v: teams_by_id[code][k] = v
        cname, cpage = extract_coach_link(wt)
        tag = ""
        if cname:
            cid = slugify(cname)
            if code in teams_by_id:
                teams_by_id[code]["coach_id"] = cid
            detail = {}
            if cpage:
                try:
                    cwt = fetch_save(cpage, raw_dir, f"coach_{cid}.wikitext")   # 抓教练页 + 存 raw 原文
                    detail = parse_coach_detail(cwt)
                except Exception:
                    pass
            upsert_coach(cid, cname, detail)
            ok_co += 1
            nteams = len(detail.get("coach", {}).get("teams_coached", []))
            tag = f"| 教练 {cname} ({nteams}队)"
        print(f"  [{code}] {len(players)} 人 {tag}")
    dump_json(TEAMS_PATH, teams)
    print(f"  → 球员 {ok_sq}/{len(codes)} 队、教练 {ok_co}/{len(codes)} 队\n")

    # [2] FIFA 当前排名（模板展开）
    print(f"[2/5] FIFA 当前排名（expandtemplates 展开）")
    franks = fetch_fifa_ranks(codes, raw_dir)
    nf = write_fifa_ranks(args.asof, franks)
    print(f"  → FIFA 排名 {nf}/{len(codes)} 队 → team_rank.json\n")

    # [3] Elo
    print(f"[3/5] Elo（eloratings.net）")
    collect_elo.main(ts=ts, asof=args.asof)
    print()

    # [4] 中文名
    if args.skip_names:
        print(f"[4/5] 中文名 —— 跳过（--skip-names）")
    else:
        print(f"[4/5] 中文名（Wikidata zh-cn）")
        collect_names.main()

    # [5] 赛事结构（matches/bracket/venues/groups，子页原文存进同一 raw 目录）
    print(f"[5/5] 赛程（2026 世界杯子页 → matches/venues/groups/bracket）")
    collect_fixtures.main(ts=ts)

    print(f"\n=== 完成 ===  一份原文在 data_raw/{ts}/ ，data 快照 asof={args.asof}")


if __name__ == "__main__":
    main()
