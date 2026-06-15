#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【新闻收集 · 硬门禁(py 是范围与源标准的唯一权威)】
把"全 48 队、每队 ≥N 源"从【靠自觉】变成【代码强制】——downscale 在这一层就做不到,直接消掉失败模式。

> 唯一权威:**范围(48 队)与每队最小源数(MIN_SOURCES)写死在这里**。skill 只引用本文件、不再各说各话
>(历史教训:skill 写"非比赛队轻扫"、py 却一视同仁 → "按 py"成了歧义指令,模型每次都猜、每次都降级)。
> 不分"深抓/轻扫":**统一标准**。某队确无足量新闻 → 必须 `--allow-below <队列表>` 显式放行 + CHANGELOG 记明,
> 默认不放行、直接 exit 1。这样"少收"藏不住、过不了门。

检查(针对某轮快照对应的成熟仓库):
 ① 队伍范围 = teams.json 全 48 队,一个不少;
 ② 每队 processed/team_news/<队>/ 的逐字全文源数 ≥ MIN_SOURCES(默认 3);
 ③ 语种覆盖(en/zh/es…)统计,低于 MIN_LANGS 警告。
逐队打印 `团队 NN/48: X源 [langs] ✓/✗`;**有欠账队 → exit 1(CI 式拦截),除非 --allow-below 放行**。

跑:python3 news_preflight.py
   python3 news_preflight.py --min 3 --allow-below CUW,HAI   # 显式放行确无足量新闻的队(需 CHANGELOG 记明)
"""
import os, sys, json, glob, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
TEAMS_JSON = f"{RUNS}/data_reference/teams.json"

# ── 唯一权威:范围与源标准(改这里 = 改全流程,skill 引用不另立) ──
MIN_SOURCES = 3        # 每队成熟仓库最少逐字全文源数
MIN_LANGS = 1          # 每队最少语种数(中/英/西…);设 2 则强制多语种


def all_teams():
    t = json.load(open(TEAMS_JSON, encoding="utf-8"))
    return sorted(x["team_id"] for x in t)


def team_sources(team):
    """该队成熟仓库 processed/team_news/<队>/ 的源(逐字全文)→ (源数, 语种集)。"""
    files = glob.glob(f"{RUNS}/data_processed/team_news/{team}/*.json")
    langs = set()
    n = 0
    for p in files:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if (d.get("status", "ok") == "ok") and len((d.get("text") or d.get("original_text") or "")) >= 200:
            n += 1
            if d.get("lang"):
                langs.add(d["lang"])
    return n, langs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=MIN_SOURCES)
    ap.add_argument("--min-langs", type=int, default=MIN_LANGS)
    ap.add_argument("--allow-below", default="", help="逗号分隔:显式放行确无足量新闻的队(需 CHANGELOG 记明)")
    a = ap.parse_args()
    allow = set(x.strip() for x in a.allow_below.split(",") if x.strip())

    teams = all_teams()
    if len(teams) != 48:
        sys.exit(f"❌ teams.json 不是 48 队(实 {len(teams)})——范围基准异常,先修 teams.json")

    print(f"▶ 新闻收集硬门禁:全 {len(teams)} 队 · 每队 ≥{a.min} 源 · ≥{a.min_langs} 语种(py 权威,不分深/轻)")
    short = []          # 欠账队
    for i, t in enumerate(teams, 1):
        n, langs = team_sources(t)
        ok = (n >= a.min and len(langs) >= a.min_langs)
        flag = "✓" if ok else ("☑放行" if t in allow else "✗欠账")
        if not ok and t not in allow:
            short.append((t, n, len(langs)))
        print(f"  团队 {i:02d}/48 {t}: {n}源 [{'/'.join(sorted(langs)) or '-'}] {flag}")

    print("─" * 56)
    if short:
        miss = ", ".join(f"{t}({n}源/{l}语)" for t, n, l in short)
        print(f"❌ 门禁不过:{len(short)} 队未达标 → {miss}")
        print(f"   补齐到每队 ≥{a.min} 源再来;某队确无足量新闻则 --allow-below 显式放行 + CHANGELOG 记明。")
        sys.exit(1)
    print(f"✅ 门禁通过:48/48 队、每队 ≥{a.min} 源" + (f"(放行 {len(allow)} 队:{','.join(sorted(allow))})" if allow else ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
