#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【⑦ 主题合并 · 整轮清理】对一个快照的各队 summary ⑦关键动态,做主题级去重合并
(治"放宽收录后同主题首发/赔率堆 2-3 条"的冗余)。**只动 ⑦ 这层视图,事实层 raw/processed 一条不少。**

触发(主题驱动,不再死等 >10 条):⑦ 里检测到【≥2 条同主题】(预测首发/阵型、博彩赔率、伤情综述)
或总条数 > 7 → 跑一次 consolidate_seven(保留全部独立事实、同主题取最新口径、来源并列)。
安全闸:合并结果非空 bullet、条数只减不增,才采用;否则保留原样不冒险。

用途:新一轮快照从上一版复制后,**继承的旧冗余**用本脚本清一遍 → 新版 team_data 才干净。
老快照不动(版本链保留)。每队改动记 CHANGELOG。

跑:python3 consolidate_round.py --snapshot 2026-06-14_XXXX --teams ALL
"""
import os, sys, json, glob, argparse, re
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
sys.path.insert(0, f"{ROOT}/wc_eval")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wc_llm import consolidate_seven
from changelog_util import append_change

# 反复出现、易堆叠的主题(用关键词粗判同主题)
TOPICS = {
    "预测首发/阵型": ("预测首发", "预计首发", "首发", "阵型", "4-", "3-4", "predicted", "lineup", "XI"),
    "博彩赔率": ("博彩", "赔率", "大热", "冷门", "盘口"),
    "伤情综述": ("伤缺", "伤退", "伤情", "伤愈", "复出", "questionable", "缺席", "递补"),
}


def _seg7_span(t):
    m = re.search(r"(## ⑦[^\n]*\n)", t)
    if not m:
        return None
    start = m.end()
    nxt = t.find("\n## ", start)
    return start, (nxt if nxt >= 0 else len(t))


def _topic_dups(bullets):
    """返回 {主题: 命中条数};用于判断要不要合并。"""
    cnt = {}
    for k, kws in TOPICS.items():
        n = sum(1 for b in bullets if any(w in b for w in kws))
        if n:
            cnt[k] = n
    return cnt


def should_consolidate(seg_text):
    bullets = [l for l in seg_text.split("\n") if l.startswith("- ")]
    if len(bullets) > 7:
        return True, f">{7}条({len(bullets)})"
    dups = _topic_dups(bullets)
    hot = {k: v for k, v in dups.items() if v >= 2}
    if hot:
        return True, "同主题≥2:" + ",".join(f"{k}×{v}" for k, v in hot.items())
    return False, ""


def process(team, snap):
    sp = f"{RUNS}/team_data/{snap}/{team}/summary.md"
    if not os.path.exists(sp):
        return {"team": team, "skip": "无summary"}
    t = open(sp, encoding="utf-8").read()
    span = _seg7_span(t)
    if not span:
        return {"team": team, "skip": "无⑦"}
    start, end = span
    seg = t[start:end]
    go, why = should_consolidate(seg)
    if not go:
        return {"team": team, "merged": 0, "note": "无需合并"}
    n0 = len([l for l in seg.split("\n") if l.startswith("- ")])
    try:
        con = consolidate_seven(seg)
    except Exception as e:
        return {"team": team, "err": str(e)[:60]}
    n1 = con.count("\n- ") + (1 if con.lstrip().startswith("- ") else 0)
    if not (con and con.lstrip().startswith("- ") and 1 <= n1 <= n0):   # 安全闸
        return {"team": team, "merged": 0, "note": "合并结果不安全·保留原样"}
    t = t[:start] + "\n" + con.strip() + "\n" + t[end:]
    open(sp, "w", encoding="utf-8").write(t)
    append_change(os.path.dirname(sp), snap,
                  block_a=[f"[⑦合并] {n0}→{n1}条(主题级去重,触发:{why};事实全留、取最新口径)"],
                  sources=["consolidate_round(py-Kimi)"], note=f"⑦主题合并 -{n0 - n1}行")
    return {"team": team, "merged": n0 - n1, "from": n0, "to": n1, "why": why}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--teams", default="ALL")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    teams = ([t.strip() for t in a.teams.split(",")] if a.teams != "ALL" else
             sorted(os.path.basename(d.rstrip("/")) for d in glob.glob(f"{RUNS}/team_data/{a.snapshot}/*/")
                    if re.match(r"^[A-Z]{3}$", os.path.basename(d.rstrip("/")))))
    print(f"▶ ⑦主题合并:{len(teams)} 队 · 快照 {a.snapshot}")
    tot = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(process, t, a.snapshot) for t in teams]):
            r = f.result()
            if r.get("merged"):
                tot += r["merged"]; print(f"  ✓ {r['team']}: {r['from']}→{r['to']}条({r['why']})")
            elif r.get("err"):
                print(f"  ✗ {r['team']}: {r['err']}")
    print(f"✅ 完成:共合并掉 {tot} 条冗余(事实层未动、老快照未动)")


if __name__ == "__main__":
    main()
