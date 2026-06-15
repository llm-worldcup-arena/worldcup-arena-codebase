#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【教练增强 · 结构化 + 可读多层】在 data_processed/team_coach/<队>.json 的结构化数据之上,
用 py 调 Kimi 生成"多层可读简介"(分点、覆盖 JSON 全部要点 + 融合收集信息),写回同一份 json 的 `brief` 字段。

设计(用户要求):先结构化(collect_team_coach 已落),再【结合结构化+收集信息】做可读介绍,覆盖 JSON + 多元素。
原 JSON 结构化数据保留;brief 是叠加的可读层。生成后自带质检(clean_loop)。并行跑 48 队。

收集信息来源:该队 team_news/prematch_news 里提到教练的段落(按教练姓名粗筛)。

跑:python3 coach_enrich.py --ts 2026-06-13_1138 --teams ALL
"""
import os, sys, json, glob, argparse, re
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
COACH = f"{RUNS}/data_processed/team_coach"
sys.path.insert(0, f"{ROOT}/wc_eval")
from wc_llm import coach_brief, cross_verify


def _coach_mentions(team, coach_json):
    """从该队新闻里粗筛提到教练的段落,作为额外信息喂给 LLM。"""
    name_en = (coach_json.get("coach") or {}).get("name_en") or ""
    name_zh = (coach_json.get("coach") or {}).get("name_zh") or ""
    last = name_en.split()[-1] if name_en else ""
    out = []
    for p in glob.glob(f"{RUNS}/data_processed/team_news/{team}/*.json") + \
             glob.glob(f"{RUNS}/data_processed/prematch_news/{team}/*.json"):
        try:
            t = json.load(open(p, encoding="utf-8")).get("original_text") or ""
        except Exception:
            continue
        for para in re.split(r"\n\n+", t):
            if (last and last in para) or (name_zh and name_zh in para):
                out.append(para.strip())
    # 去重、限长
    seen, uniq = set(), []
    for s in out:
        k = s[:50]
        if k not in seen:
            seen.add(k); uniq.append(s)
    return "\n\n".join(uniq[:8])[:6000]


def _coach_claims(team, cj):
    """从多源(reference 结构化 + 各新闻里提到主帅的段落)收集"这队主帅是谁"的说法,供 cross_verify。
    单源(只有维基)→ 多源(维基 + 各家新闻),≥2 源即可交叉,目标尽量 ≥5。"""
    import re
    c = cj.get("coach") or {}
    name_en = c.get("name_en") or ""
    last = name_en.split()[-1] if name_en else ""
    claims = [{"source": "data_reference(维基种子)", "claim": f"{c.get('name_zh','')}/{name_en}"}]
    # 各新闻:出现"主帅/coach/manager/head coach/boss"且像在说教练的段落 → 一条 claim
    KW = ("coach", "manager", "head coach", "boss", "主帅", "主教练", "执教", "带队")
    for p in glob.glob(f"{RUNS}/data_processed/team_news/{team}/*.json") + \
             glob.glob(f"{RUNS}/data_processed/prematch_news/{team}/*.json"):
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        src = r.get("source", "?"); t = r.get("original_text") or ""
        for para in re.split(r"\n\n+", t):
            if any(k in para.lower() for k in KW) and (not last or last.lower() in para.lower() or "coach" in para.lower()):
                claims.append({"source": src, "claim": para.strip()[:280]})
                break
    # 去重源、限量(尽量保留多源)
    seen, uniq = set(), []
    for cl in claims:
        if cl["source"] not in seen:
            seen.add(cl["source"]); uniq.append(cl)
    return uniq[:8]


def _coach_basis(team, cj):
    """教练 brief 的"依据签名"(便宜、无LLM):结构化主帅名 + 所有提到主帅的新闻 URL 集合。
    与上次相同 → 没有换帅、也没有新的教练相关新闻 → 不必重做 brief。"""
    import re
    c = cj.get("coach") or {}
    name = f"{c.get('name_zh','')}/{c.get('name_en','')}"
    last = (c.get("name_en") or "").split()[-1] if c.get("name_en") else ""
    KW = ("coach", "manager", "head coach", "boss", "主帅", "主教练", "执教", "带队")
    urls = set()
    for p in glob.glob(f"{RUNS}/data_processed/team_news/{team}/*.json") + \
             glob.glob(f"{RUNS}/data_processed/prematch_news/{team}/*.json"):
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        t = (r.get("original_text") or "")
        if any(k in t.lower() for k in KW) and (not last or last.lower() in t.lower() or "coach" in t.lower()):
            urls.add(r.get("url") or p)
    return {"coach": name, "mention_urls": sorted(urls)}


def enrich(team, ts, refresh=False):
    p = f"{COACH}/{team}.json"
    if not os.path.exists(p):
        return {"team": team, "skip": "无结构化教练"}
    cj = json.load(open(p, encoding="utf-8"))
    # ── 增量判断(与新闻三判同策略):先看"有没有换帅 / 有没有新的教练相关新闻"——没变就不重做 ──
    basis = _coach_basis(team, cj)
    if cj.get("brief") and cj.get("brief_basis") == basis and not refresh:
        return {"team": team, "skip": "无变化(无换帅、无新教练新闻)", "unchanged": True}
    # ── 有变化(换帅/新新闻)或首次 → 多源交叉验证主帅 + (重)生成 brief ──
    claims = _coach_claims(team, cj)
    if len(claims) >= 2:
        try:
            xv = cross_verify(f"{team} 现任主教练是谁", claims)
            cj["coach_xverify"] = {**xv, "n_sources": len(claims)}
        except Exception as e:
            cj["coach_xverify"] = {"_error": str(e)[:60]}
    info = _coach_mentions(team, cj)
    res = coach_brief(cj.get("coach") or cj, info)
    cj["brief"] = res["brief"]
    cj["brief_qc"] = res["qc"]
    cj["brief_fetched"] = ts
    cj["brief_info_chars"] = len(info)
    cj["brief_basis"] = basis        # 记本次依据签名,供下轮"变没变"判断
    json.dump(cj, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # raw 留底
    rawd = f"{RUNS}/data_raw/{ts}/team_coach"
    os.makedirs(rawd, exist_ok=True)
    json.dump(cj, open(f"{rawd}/{team}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"team": team, "brief_lines": res["brief"].count("\n- ") + 1, "info_chars": len(info), "regen": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ts", required=True)
    ap.add_argument("--teams", default="ALL")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--refresh", action="store_true", help="强制重生成(忽略'无变化'判断)")
    a = ap.parse_args()
    teams = sorted(os.path.basename(p)[:-5] for p in glob.glob(f"{COACH}/*.json")) if a.teams == "ALL" \
        else [t.strip() for t in a.teams.split(",")]
    print(f"▶ coach_enrich:{len(teams)} 队 · 增量判断(换帅/新教练新闻才重做)· py-Kimi")
    stats = [None] * len(teams)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        fut = {ex.submit(enrich, t, a.ts, a.refresh): i for i, t in enumerate(teams)}
        done = 0
        for f in as_completed(fut):
            try:
                stats[fut[f]] = f.result()
            except Exception as e:
                stats[fut[f]] = {"team": teams[fut[f]], "err": str(e)[:80]}
            done += 1
            print(f"  [{done}/{len(teams)}] {stats[fut[f]]}")
    regen = sum(1 for s in stats if s and s.get("regen"))
    unchanged = sum(1 for s in stats if s and s.get("unchanged"))
    err = sum(1 for s in stats if s and s.get("err"))
    print(f"✅ 教练增量:重做 {regen} 队(换帅/新教练新闻)· 无变化跳过 {unchanged} 队 · 失败 {err}")


if __name__ == "__main__":
    main()
