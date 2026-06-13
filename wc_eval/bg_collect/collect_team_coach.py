#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【主教练 · 按队采集】教练=队伍层人员数据,与 match_env(裁判)同款待遇:双写进成熟仓库+raw。

存放:
  data_processed/team_coach/<队>.json   ← 成熟仓库(一队一份:现任主帅 + 历任记录只增)
  data_raw/<时分>/team_coach/<队>.json   ← 收集过程留底(本次新增/变更)

来历与更新:
  - 种子 = data_reference(collect_coaches.py 赛前维基采集:teams.coach_id → persons.json 教练条目);
  - 世界杯期间换帅/代理等变动 → 新闻线发现后 `--team X --set "名(国籍)" --src "来源"` 更新:
    现任换入、旧任压进 history(只增不改,与 news 同铁律)。
  - 已有且无 --set → 跳过(--refresh 重新从 reference 重建,慎用)。

下游:predict/common._coach_line() 优先读本仓库 → 主帅行进预测 prompt 抬头。

跑:python3 collect_team_coach.py --all --ts 2026-06-13_0748                 # 48队种子落库
   python3 collect_team_coach.py --team BRA --ts <时分> --set "新帅(国籍)" --src "ESPN/官方"
"""
import os, json, argparse, glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
CURATED = f"{RUNS}/data_processed/team_coach"
from naming_util import valid_ts


def _ref():
    ts = json.load(open(f"{RUNS}/data_reference/teams.json", encoding="utf-8"))
    ps = {p["person_id"]: p for p in json.load(open(f"{RUNS}/data_reference/persons.json", encoding="utf-8"))}
    out = {}
    for t in ts:
        p = ps.get(t.get("coach_id") or "")
        if p:
            c = p.get("coach") or {}
            out[t["team_id"]] = {"name_zh": p.get("name_zh"), "name_en": p.get("name_en"),
                                 "nationality": p.get("nationality"),
                                 "career_since": c.get("career_since"),
                                 "person_id": p["person_id"]}
    return out


def _dual_write(team, rec, ts):
    os.makedirs(CURATED, exist_ok=True)
    rawd = f"{RUNS}/data_raw/{ts}/team_coach"
    os.makedirs(rawd, exist_ok=True)
    body = json.dumps(rec, ensure_ascii=False, indent=1)
    open(f"{CURATED}/{team}.json", "w", encoding="utf-8").write(body)   # ① 成熟仓库
    open(f"{rawd}/{team}.json", "w", encoding="utf-8").write(body)      # ② 收集过程


def seed(team, ts, refresh=False):
    cur = f"{CURATED}/{team}.json"
    if os.path.exists(cur) and not refresh:
        return "skip"
    info = _ref().get(team)
    if not info:
        print(f"  ⚠️ {team} reference 无教练条目"); return "miss"
    rec = {"team": team, "coach": info,
           "source": "data_reference(collect_coaches.py 维基采集,赛前)", "fetched": ts,
           "history": [],
           "_note": "现任主帅;换帅经 --set 更新(旧任压进 history,只增不改)。下游:match_header 主帅行。"}
    _dual_write(team, rec, ts)
    return "ok"


def set_coach(team, ts, new, src):
    cur = f"{CURATED}/{team}.json"
    old = json.load(open(cur, encoding="utf-8")) if os.path.exists(cur) else {"team": team, "history": []}
    if old.get("coach"):
        old["history"].append({"coach": old["coach"], "source": old.get("source"),
                               "replaced": ts})
    old.update({"coach": {"name": new}, "source": src or "WebSearch多源", "fetched": ts})
    _dual_write(team, old, ts)
    print(f"  ✅ {team} 换帅 → {new}({src})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="48队种子落库(reference→processed)")
    ap.add_argument("--team", help="单队")
    ap.add_argument("--ts", required=True)
    ap.add_argument("--set", dest="new", help="换帅:新主帅 名(国籍)")
    ap.add_argument("--src", help="换帅信息来源(≥2源)")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    valid_ts(a.ts)
    if a.new:
        if not a.team:
            raise SystemExit("✗ --set 需配 --team")
        set_coach(a.team, a.ts, a.new, a.src)
        return
    if a.all:
        ref = _ref()
        n = {"ok": 0, "skip": 0, "miss": 0}
        for team in sorted(ref):
            n[seed(team, a.ts, a.refresh)] += 1
        print(f"✅ team_coach 种子:新写 {n['ok']} / 已有跳过 {n['skip']} / 缺 {n['miss']}(共 {len(ref)} 队)")
    elif a.team:
        print(f"  {a.team}: {seed(a.team, a.ts, a.refresh)}")


if __name__ == "__main__":
    main()
