#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""块3·球员个人页采集：维基球员页 infobox → persons.player 补 全名/出生地/身高/生涯俱乐部。

球员真实页名取自球队页 raw 阵容段的 name 链接（{{nat fs g player|…|name=[[页名|显示]]|…}}）。
⚠️ ~1250 个球员页，采集耗时（十几分钟）；惯用脚维基 infobox 没有（采不到）。
独立采集器（不并进 collect_all 主流程，免得每次重采都跑十几分钟）；需要球员档案时单独跑。

跑：python3 collect_players.py            # 全部（慢）
    python3 collect_players.py --only ESP # 只补某队
    python3 collect_players.py --limit 20 # 先测 20 人
"""
import os, re, argparse
from collect_squads import (fetch_full_page, fetch_save, run_ts, clean_link, strip_wiki, slugify,
                            squad_segment, extract_player_blocks, split_top_params,
                            persons_path, load_json, dump_json, BASE, WIKI_PAGE)


def latest_raw():
    """找最近一次含球员阵容的 raw 目录。"""
    base = f"{BASE}/raw/bg"
    for d in sorted(os.listdir(base), reverse=True):
        dd = f"{base}/{d}"
        if not os.path.isdir(dd):
            continue
        fs = [f for f in os.listdir(dd) if f.endswith(".wikitext")]
        if fs and "nat fs g player" in open(f"{dd}/{fs[0]}", encoding="utf-8").read(3000):
            return dd
    return None


def player_pages(raw_dir, only=None):
    """扫 raw 阵容段 → {person_id: 维基页名}。页名取 name 参数的链接 target。"""
    out = {}
    for f in os.listdir(raw_dir):
        if not f.endswith(".wikitext"):
            continue
        if only and f[:-9] not in only:
            continue
        wt = open(f"{raw_dir}/{f}", encoding="utf-8").read()
        for b in extract_player_blocks(squad_segment(wt) or wt):
            for part in split_top_params(b[2:-2]):
                ps = part.strip()
                if ps.startswith("name") and "=" in ps:
                    v = ps.split("=", 1)[1]
                    disp = clean_link(v)
                    lm = re.search(r"\[\[([^\]|]+)", v)
                    if disp:
                        out[slugify(disp)] = lm.group(1).strip() if lm else disp
                    break
    return out


def parse_height(s):
    m = (re.search(r"convert\|\s*([\d.]+)\s*\|\s*m", s, re.I)   # {{convert|1.86|m|…}}
         or re.search(r"\|m=\s*([\d.]+)", s)                     # {{height|m=1.86}}
         or re.search(r"([\d.]+)\s*m\b", s))                     # "1.78 m"
    if m:
        try:
            return round(float(m.group(1)) * 100)
        except ValueError:
            pass
    fm = re.search(r"\|ft=\s*(\d+)", s)
    if fm:                                          # 英制 {{height|ft=6|in=1}}
        inch = re.search(r"\|in=\s*(\d+)", s)
        return round((int(fm.group(1)) * 12 + (int(inch.group(1)) if inch else 0)) * 2.54)
    m = re.search(r"(\d{3})\s*cm", s)
    return int(m.group(1)) if m else None


def parse_player_detail(wt):
    def grab(k):
        m = re.search(r"^\|\s*" + k + r"\s*=\s*([^\n]+)", wt, re.M | re.I)
        return m.group(1).strip() if m else ""
    clubs, seen = [], set()
    for i in range(1, 16):
        c = clean_link(strip_wiki(grab(f"clubs{i}")))
        if c and "loan" not in c.lower() and c not in seen:
            seen.add(c); clubs.append(c)
    return {"full_name": strip_wiki(grab("full_name")),
            "birth_place": strip_wiki(grab("birth_place")),
            "height_cm": parse_height(grab("height")),
            "club_history": clubs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只补某队，逗号分隔 FIFA 码")
    ap.add_argument("--limit", type=int, help="只跑前 N 人（测试）")
    args = ap.parse_args()
    only = {c.strip().upper() for c in args.only.split(",")} if args.only else None

    raw = latest_raw()
    if not raw:
        print("找不到含阵容的 raw 目录"); return
    pages = player_pages(raw, only)
    persons = load_json(persons_path(), [])
    by_id = {p["person_id"]: p for p in persons}
    ids = [pid for pid in pages if pid in by_id]
    if args.limit:
        ids = ids[:args.limit]
    raw_dir = f"{BASE}/raw/bg/{run_ts()}"                   # 球员页原文存这（raw 全量留底）
    print(f"页名取自 {raw}；球员页原文 → {raw_dir}  待补 {len(ids)} 球员\n")

    ok = 0
    for pid in ids:
        try:
            det = parse_player_detail(fetch_save(pages[pid], raw_dir, f"player_{pid}.wikitext"))
        except Exception as e:
            print(f"  [{pid}] 抓取出错: {e}"); continue
        rec = by_id[pid]
        pl = rec.setdefault("player", {})
        if det["full_name"]:
            rec["full_name"] = det["full_name"]
        if det["birth_place"]:
            rec["birth_place"] = det["birth_place"]
        if det["height_cm"]:
            pl["height_cm"] = det["height_cm"]
        if det["club_history"]:
            pl["club_history"] = det["club_history"]
        ok += 1
        if ok % 50 == 0:
            print(f"  {ok}/{len(ids)} …")
    dump_json(persons_path(), sorted(by_id.values(), key=lambda p: p["person_id"]))
    print(f"\n完成 {ok}/{len(ids)} 球员个人页 → persons.player（身高/生涯俱乐部/全名/出生地）")


if __name__ == "__main__":
    main()
