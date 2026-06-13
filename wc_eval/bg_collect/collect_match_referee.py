#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【主裁 · 按场采集】裁判=比赛层人员数据,**与教练同款待遇:独立成熟仓库文件夹**。
   (教练 = data_processed/team_coach/<队>.json;裁判 = data_processed/match_referee/<场次>.json)

存放(双写,与 team_coach / match_env 一致):
  data_processed/match_referee/<date>_<HOME>_vs_<AWAY>.json   ← 成熟仓库(一场一份)
  data_raw/<时分>/match_referee/<同名>.json                    ← 收集过程留底

结构(① 结构化 + ② 可读 brief 两层,镜像 team_coach):
  {"match":{slug,date,home,away}, "referee":{name,nationality,var,source,fetched},
   "brief": "<referee_enrich.py py-Kimi 生成的执法风格可读材料>", ...}

来历:主裁=FIFA 官方指派公告,经 WebSearch 多源确认后 --set 写入(人名+国籍+VAR)。
下游:predict/common.match_header() 读本仓库 → 主裁行 + 执法风格 brief 进预测 prompt。

跑:python3 collect_match_referee.py --home BRA --away MAR --ts 2026-06-13_1340 \
       --referee "Slavko Vincic(斯洛文尼亚)" --var "Sandro Schärer(瑞士)" --src "WebSearch多源"
   python3 collect_match_referee.py --migrate-from-env --ts 2026-06-13_1340   # 从 match_env 迁移现有裁判
"""
import os, sys, json, glob, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
CURATED = f"{RUNS}/data_processed/match_referee"
ENV = f"{RUNS}/data_processed/match_env"
from naming_util import valid_ts


def _slug(home, away):
    mt = next((m for m in json.load(open(f"{RUNS}/data_reference/matches.json", encoding="utf-8"))
               if m.get("team_a") == home and m.get("team_b") == away), None)
    if not mt:
        raise SystemExit(f"✗ matches.json 无 {home} vs {away}")
    return f"{mt['date']}_{home}_vs_{away}", mt


def _dual_write(slug, rec, ts):
    os.makedirs(CURATED, exist_ok=True)
    rawd = f"{RUNS}/data_raw/{ts}/match_referee"
    os.makedirs(rawd, exist_ok=True)
    body = json.dumps(rec, ensure_ascii=False, indent=1)
    open(f"{CURATED}/{slug}.json", "w", encoding="utf-8").write(body)
    open(f"{rawd}/{slug}.json", "w", encoding="utf-8").write(body)


def set_referee(home, away, ts, referee, var=None, src=None):
    slug, mt = _slug(home, away)
    cur = f"{CURATED}/{slug}.json"
    old = json.load(open(cur, encoding="utf-8")) if os.path.exists(cur) else {}
    rec = {"match": {"slug": slug, "date": mt["date"], "home": home, "away": away,
                     "round": mt.get("round"), "group": mt.get("group")},
           "referee": {"name": referee, **({"var": var} if var else {}),
                       "source": src or "WebSearch(FIFA官方指派)", "fetched": ts},
           "brief": old.get("brief", ""),   # 保留已生成的可读层(referee_enrich 填)
           "_note": "裁判=比赛层人员数据,与教练同规格(结构化+可读brief);brief 由 referee_enrich.py py-Kimi 生成。"}
    _dual_write(slug, rec, ts)
    print(f"  ✅ {slug}: 主裁 {referee}" + (f" · VAR {var}" if var else ""))
    return cur


def migrate_from_env(ts):
    """把现有 match_env 里的 referee 字段迁出来,建独立 match_referee 仓库(一次性迁移)。"""
    n = 0
    for p in glob.glob(f"{ENV}/*.json"):
        e = json.load(open(p, encoding="utf-8"))
        ref = e.get("referee") or {}
        if not ref.get("name"):
            continue
        slug = os.path.basename(p)[:-5]
        m = e.get("match", {})
        rec = {"match": {"slug": slug, "date": m.get("date"), "home": m.get("home"), "away": m.get("away"),
                         "round": m.get("round"), "group": m.get("group")},
               "referee": {"name": ref.get("name"), **({"var": ref["var"]} if ref.get("var") else {}),
                           "source": ref.get("source", "WebSearch"), "fetched": ref.get("fetched", ts)},
               "brief": ref.get("brief", ""),
               "_note": "裁判=比赛层人员数据,与教练同规格;从 match_env 迁出独立成仓库(2026-06-13)。"}
        _dual_write(slug, rec, ts)
        n += 1
        print(f"  ↗ 迁移 {slug}: {ref.get('name')}")
    print(f"✅ 迁移完成:{n} 场裁判 → data_processed/match_referee/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home"); ap.add_argument("--away"); ap.add_argument("--ts", required=True)
    ap.add_argument("--referee"); ap.add_argument("--var"); ap.add_argument("--src")
    ap.add_argument("--migrate-from-env", action="store_true")
    a = ap.parse_args()
    valid_ts(a.ts)
    if a.migrate_from_env:
        migrate_from_env(a.ts)
    elif a.home and a.away and a.referee:
        set_referee(a.home, a.away, a.ts, a.referee, a.var, a.src)
    else:
        ap.error("用 --migrate-from-env,或 --home --away --referee [--var --src]")


if __name__ == "__main__":
    main()
