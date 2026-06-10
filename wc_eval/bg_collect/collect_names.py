#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文名采集：name_en → enwiki → Wikidata Q → zh-cn/zh-hans/zh（大陆简体优先）→ persons.name_zh。
两轮：① 用 name_en 直接查；② 没拿到的，用 raw wikitext 里的维基页标题（消歧全名）重查。
规范见 wc_skills/wc-data-collect。跑：python3 collect_names.py
"""
import json, re, os, urllib.request, urllib.parse
from collect_squads import persons_path, load_json, dump_json

UA = "WorldCup2026-BG-Research/1.0 (academic benchmark; mailto:zhenran.w.1103@gmail.com)"
RAW_BASE = "/home/ubuntu/worldcup_2026/wc_runs/raw/bg"


def api(host, params):
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def titles_to_qids(titles):
    """enwiki 标题 → Wikidata Q（处理 normalize/redirect）。"""
    out = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        d = api("en.wikipedia.org", {"action": "query", "titles": "|".join(batch),
                "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1, "format": "json"})
        q = d.get("query", {})
        t2q = {p["title"]: p.get("pageprops", {}).get("wikibase_item") for p in q.get("pages", {}).values()}
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        for t in batch:
            tt = redir.get(norm.get(t, t), norm.get(t, t))
            out[t] = t2q.get(tt)
    return out


def qids_to_zh(qids):
    """Q → 中文名（zh-cn > zh-hans > zh）。"""
    out = {}
    qids = [q for q in dict.fromkeys(qids) if q]
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        d = api("www.wikidata.org", {"action": "wbgetentities", "ids": "|".join(batch),
                "props": "labels", "languages": "zh-cn|zh-hans|zh", "format": "json"})
        for qid, e in d.get("entities", {}).items():
            labels = e.get("labels", {})
            for lang in ("zh-cn", "zh-hans", "zh"):
                if lang in labels:
                    out[qid] = labels[lang]["value"]; break
    return out


def display_to_title():
    """扫 raw wikitext，建 显示名 → 维基页标题（[[标题|显示]] 的标题），用于消歧补救。"""
    m = {}
    for d in os.listdir(RAW_BASE):
        dd = f"{RAW_BASE}/{d}"
        if not os.path.isdir(dd):
            continue
        for f in os.listdir(dd):
            if f.endswith(".wikitext"):
                for link in re.findall(r"\[\[([^\]\n]+)\]\]", open(f"{dd}/{f}", encoding="utf-8").read()):
                    if "|" in link:
                        title, disp = link.split("|", 1)
                        m.setdefault(disp.strip(), title.strip())
    return m


def fill(persons, name2zh):
    n = 0
    for p in persons:
        if not p.get("name_zh") and name2zh.get(p.get("name_en")):
            p["name_zh"] = name2zh[p["name_en"]]; n += 1
    return n


def main():
    persons = load_json(persons_path(), [])
    names = sorted({p["name_en"] for p in persons if p.get("name_en")})

    # 第一轮：name_en 直接查
    q1 = titles_to_qids(names)
    zh1 = qids_to_zh(list(q1.values()))
    r1 = fill(persons, {ne: zh1[q] for ne, q in q1.items() if zh1.get(q)})

    # 第二轮补救：没拿到的，用维基页标题（消歧全名）重查
    tmap = display_to_title()
    retry = {p["name_en"]: tmap[p["name_en"]] for p in persons
             if not p.get("name_zh") and tmap.get(p.get("name_en")) and tmap[p["name_en"]] != p["name_en"]}
    r2 = 0
    if retry:
        q2 = titles_to_qids(sorted(set(retry.values())))
        zh2 = qids_to_zh(list(q2.values()))
        r2 = fill(persons, {ne: zh2[q2.get(t)] for ne, t in retry.items() if zh2.get(q2.get(t))})

    dump_json(persons_path(), persons)
    total = sum(1 for p in persons if p.get("name_zh"))
    miss = [p["name_en"] for p in persons if not p.get("name_zh")]
    print(f"第一轮 {r1} + 补救 {r2} → 中文名 {total}/{len(persons)}；仍缺 {len(miss)}，例: {miss[:6]}")


if __name__ == "__main__":
    main()
