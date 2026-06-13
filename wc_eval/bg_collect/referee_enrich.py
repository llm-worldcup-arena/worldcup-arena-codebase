#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【裁判增强 · 结构化 + 可读材料】在 match_env 的 referee 结构化数据(人名/国籍/VAR)之上,
用 py 调 Kimi 生成"可读执法材料"(分点:执法风格/牌量倾向/大赛履历/对本场影响),写回 referee.brief。

设计同教练:先结构化(collect_match_env 落人名),再 LLM 据姓名+国籍生成可读层(覆盖结构化 + Kimi 知识)。
结构化保留;brief 是叠加层。自带质检。并行多场。

跑:python3 referee_enrich.py --slugs 2026-06-13_QAT_vs_SUI,2026-06-13_BRA_vs_MAR
   python3 referee_enrich.py --all
"""
import os, sys, json, glob, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF = f"{ROOT}/wc_runs/data_processed/match_referee"   # 独立成熟仓库(与 team_coach 同规格)
sys.path.insert(0, f"{ROOT}/wc_eval")
from wc_llm import kimi_text, clean_check, CLEAN_FIX_SYS

REF_SYS = """你是足球裁判资料编辑。给你一场世界杯比赛的主裁(姓名+国籍)与 VAR,写一份简短可读的执法材料(中文)。
分 2-4 点:① 该主裁的执法风格/尺度(严或松、牌量倾向、是否爱用 VAR)——据你对该裁判的了解;② 大赛/国际履历(如执法过的大赛);③ 对本场的潜在影响(如对抗激烈时是否易出牌)。
要求:基于你确切知道的信息,**不确定的不要编**(宁可只写 1-2 点);客观、无套话。直接输出 markdown 无序列表,无前言。"""


def enrich(slug):
    p = f"{REF}/{slug}.json"
    if not os.path.exists(p):
        return {"slug": slug, "skip": "无 match_referee(先跑 collect_match_referee)"}
    e = json.load(open(p, encoding="utf-8"))
    ref = e.get("referee") or {}
    if not ref.get("name"):
        return {"slug": slug, "skip": "无主裁名"}
    home = e.get("match", {}).get("home"); away = e.get("match", {}).get("away")
    user = (f"【比赛】{home} vs {away}\n【主裁】{ref.get('name')}　【VAR】{ref.get('var', '(未公布)')}")
    txt = kimi_text(REF_SYS, user)
    chk = clean_check(txt, "裁判材料")
    if chk.get("need_fix"):
        txt = kimi_text(CLEAN_FIX_SYS, f"【类型】裁判材料\n【问题】{chk.get('issues')}\n【原文】\n{txt}")
    e["brief"] = txt.strip()        # brief 作为顶层可读层(与 team_coach 同结构)
    json.dump(e, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"slug": slug, "ok": True, "brief_chars": len(txt)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", help="逗号分隔场次 slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    slugs = [os.path.basename(p)[:-5] for p in glob.glob(f"{REF}/*.json")] if a.all \
        else [s.strip() for s in (a.slugs or "").split(",") if s.strip()]
    if not slugs:
        raise SystemExit("✗ --slugs 或 --all")
    print(f"▶ 裁判可读材料:{len(slugs)} 场 · py-Kimi")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(enrich, s) for s in slugs]):
            print(f"  {f.result()}")


if __name__ == "__main__":
    main()
