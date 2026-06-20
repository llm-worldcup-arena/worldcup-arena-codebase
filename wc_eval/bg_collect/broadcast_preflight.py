#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【赛事播报 硬门禁】把"每一场已结算的比赛都必须有赛事播报、且已嵌进两队 summary 块B"
从【靠自觉】变成【代码强制】—— 防 6/15 起那种"播报这条线没人跑、却没人发现"的漏采 bug 再犯。

唯一权威:已结算场(results.json)= 必须每场都有
  ① ours/long.md(多源合成的全本播报存在);
  ② 该场在 home、away 两队 summary 块B 里都有 "### 🏟 <date> ... vs <opp>" 小节(真嵌进去了)。
任一不满足 → 列出 + exit 1(matchday 据此在预测前拦,或单独跑自检)。

跑:python3 broadcast_preflight.py --snapshot 2026-06-19_1138
"""
import os, sys, json, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
MB = f"{RUNS}/data_processed/match_broadcast"
TEAM_DATA = f"{RUNS}/team_data"


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def settled():
    res = _load(f"{RUNS}/archive/results.json")["matches"]
    by = {(m["team_a"], m["team_b"]): m for m in _load(f"{RUNS}/data_reference/matches.json")}
    out = []
    for key in res:
        a, b = key.split("_vs_")
        m = by.get((a, b))
        if m:
            out.append({"key": key, "a": a, "b": b, "date": m["date"],
                        "slug": f"{m['date']}_{a}_vs_{b}"})
    return out


def embedded_in(snap, team, date, opp):
    """该队 summary 块B 是否有这场的 ### 🏟 小节(按 date + 对手码 粗匹配)。"""
    p = f"{TEAM_DATA}/{snap}/{team}/summary.md"
    if not os.path.exists(p):
        return False
    t = open(p, encoding="utf-8").read()
    if "## 世界杯 2026 · 专项整理" not in t:
        return False
    blockb = t.split("## 世界杯 2026 · 专项整理", 1)[1]
    # 该场小节标题形如:### 🏟 <date> · 第N轮·... · <主/客/中> vs <opp>（比分）
    for line in blockb.split("\n"):
        if line.startswith("### 🏟") and date in line and f"vs {opp}" in line:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    a = ap.parse_args()
    ms = settled()
    print(f"▶ 赛事播报硬门禁:已结算 {len(ms)} 场 · 每场需 ours/long.md + 两队块B 均嵌(py权威)")
    bad = []
    for m in sorted(ms, key=lambda x: x["date"]):
        long_ok = os.path.exists(f"{MB}/{m['slug']}/ours/long.md")
        emb_a = embedded_in(a.snapshot, m["a"], m["date"], m["b"])
        emb_b = embedded_in(a.snapshot, m["b"], m["date"], m["a"])
        flags = []
        if not long_ok:
            flags.append("无long.md")
        if not emb_a:
            flags.append(f"{m['a']}块B未嵌")
        if not emb_b:
            flags.append(f"{m['b']}块B未嵌")
        ok = not flags
        if not ok:
            bad.append(m["key"])
        print(f"  团队 {m['date']} {m['key']:<14} {'✓' if ok else '✗ ' + '；'.join(flags)}")
    print("─" * 60)
    if bad:
        print(f"❌ 播报门禁未过:{len(bad)} 场缺播报/未嵌 → {bad}")
        print("   补法:为缺的场 WebSearch 写 data_raw/<ts>/_broadcast_urls/<Mid>.json,再跑 broadcast_round.py(或 matchday 含 ⑤)")
        sys.exit(1)
    print(f"✅ 播报门禁通过:{len(ms)}/{len(ms)} 场均有 ours/long.md + 两队块B 均已嵌")


if __name__ == "__main__":
    main()
