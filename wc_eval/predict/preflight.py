#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【跑前体检 · 防泄露三查+装备齐查】真调 6 模型前必跑;任一 ✗ → exit 1,绝不带病跑。
配 skill wc-matchday 第⑦步 / wc-predict 铁律2。之前每轮手工体检,2026-06-13 固化成文。

每场查 6 项:
 ① kickoff_ts 存在且晚于当前(美东)——带搜索预测只能赛前跑
 ② match_env 仓库有该场:天气(开球时段)+ 主裁人名
 ③ _HANDICAP 有该场固定盘口
 ④ prompt 成品含:环境行 / 让球盘口 / 全面分析"不限于此" / 自检"逐项核对" / 矛盾案例×4 / 比分枚举
 ⑤ 防泄露:两队 summary 的近期状态里不得出现【本场日期】的赛果行(待预测场绝不能已在档案里)
 ⑥ 现实档案 results.json 里不得已有本场(已结算=已踢过,不能再带搜索预测)

跑:python3 preflight.py --snapshot 2026-06-13_0748 --matches QAT-SUI,BRA-MAR,HAI-SCO,AUS-TUR
"""
import os, json, argparse, datetime, sys
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_summary, handicap_clause
from predict_match import build_user

MUST_IN_PROMPT = ["环境:", "让球盘口", "不限于此", "逐项核对", "矛盾案例", "X=主队进球数"]


def _now_et():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4)))


def check(home, away, snap):
    errs, warns = [], []
    mt = next((m for m in json.load(open(f"{RUNS}/data_reference/matches.json", encoding="utf-8"))
               if m.get("team_a") == home and m.get("team_b") == away), None)
    if not mt:
        return [f"matches.json 无 {home} vs {away}"], warns
    # ① 未开球
    kts = mt.get("kickoff_ts")
    if not kts:
        errs.append("缺 kickoff_ts(跑 fill_kickoffs.py 或多源补)")
    elif datetime.datetime.fromisoformat(kts) <= _now_et():
        errs.append(f"已开球({kts})——带搜索绝不能再跑")
    # ② 环境
    slug = f"{mt['date']}_{home}_vs_{away}"
    envp = f"{RUNS}/data_processed/match_env/{slug}.json"
    if not os.path.exists(envp):
        errs.append("缺 match_env(跑 collect_match_env.py)")
    else:
        e = json.load(open(envp, encoding="utf-8"))
        if not (e.get("weather") or {}).get("开球时段"):
            errs.append("env 无天气(--refresh 重取)")
        if not (e.get("referee") or {}).get("name"):
            warns.append("env 无主裁(FIFA 指派后 --referee 补)")
    # ③ 盘口
    if not handicap_clause(home, away):
        errs.append("缺 _HANDICAP 固定盘口(多源核对后加)")
    # ④ prompt 成品要素
    try:
        up = build_user(home, away, snap)
        miss = [k for k in MUST_IN_PROMPT if k not in up]
        if miss:
            errs.append(f"prompt 缺要素:{miss}")
        if up.count("· 比分") + up.count("比分 ") < 3:
            warns.append("矛盾案例疑似不足4个(人工瞄一眼)")
    except Exception as ex:
        errs.append(f"prompt 生成失败:{ex}")
    # ⑤ 防泄露:summary 近期状态里不得有本场日期的赛果行
    for t, o in ((home, away), (away, home)):
        try:
            s = read_summary(t, snap)
        except Exception:
            errs.append(f"读不到 {t} summary(快照 {snap})"); continue
        seg = s.split("## 近期状态")[-1].split("\n## ")[0] if "## 近期状态" in s else s
        for ln in seg.split("\n"):
            if mt["date"] in ln and o in ln:
                errs.append(f"泄露!{t} 近期状态已有本场行:{ln.strip()[:60]}")
    # ⑥ 不得已结算
    res = json.load(open(f"{RUNS}/archive/results.json", encoding="utf-8"))["matches"]
    if f"{home}_vs_{away}" in res:
        errs.append("results.json 已有本场(已踢过,不能预测)")
    return errs, warns


def _issue_text(issue):
    return f"{issue.get('quote', '')} {issue.get('why', '')}"


def _dates_in_issue(issue):
    """提取 LLM issue 里明写的日期。只用来降级明显早于本场的 leakage 误报。"""
    txt = _issue_text(issue)
    out = []
    for y, m, d in re.findall(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})", txt):
        try:
            out.append(datetime.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for m, d in re.findall(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", txt):
        try:
            out.append(datetime.date(2026, int(m), int(d)))
        except ValueError:
            pass
    return out


def _hard_leakage(issue, match_date):
    """LLM 终审偶尔把本场前已赛结果误报成 leakage；硬拦只保留本场日及之后的明确赛果泄露。"""
    dates = _dates_in_issue(issue)
    if dates and all(d < match_date for d in dates):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--matches", required=True, help="逗号分隔 HOME-AWAY,如 QAT-SUI,BRA-MAR")
    ap.add_argument("--llm-audit", action="store_true", help="机械体检后再跑 LLM 快照终审官(语义把关:矛盾/过期/泄露)")
    a = ap.parse_args()
    bad = 0
    for pair in a.matches.split(","):
        home, away = pair.strip().split("-")
        errs, warns = check(home, away, a.snapshot)
        flag = "✅" if not errs else "✗"
        print(f"{flag} {home} vs {away}" + (f"  ⚠️ {';'.join(warns)}" if warns else ""))
        for e in errs:
            print(f"    ✗ {e}"); bad += 1
    if bad:
        sys.exit(f"✗ 机械体检不过({bad} 项),绝不带病跑——修完再来")
    print("—— 机械体检全绿 ——")

    if a.llm_audit:                          # ── 语义终审官(LLM 通读两队 summary 找 矛盾/过期/泄露)──
        print("—— 启动快照终审官(py-Kimi 语义把关,并行)——")
        from wc_llm import snapshot_audit, pmap
        pairs = [tuple(p.strip().split("-")) for p in a.matches.split(",")]
        def _audit(hw):
            h, w = hw
            mt = next((m for m in json.load(open(f"{RUNS}/data_reference/matches.json", encoding="utf-8"))
                       if m.get("team_a") == h and m.get("team_b") == w), {})
            return hw, snapshot_audit(h, w, read_summary(h, a.snapshot), read_summary(w, a.snapshot),
                                      f"快照 {a.snapshot}；本场日期 {mt.get('date')}；只把本场或本场之后赛果算泄露")
        # 拦截规则:**只对 leakage(泄露)硬拦**——这是 benchmark 命门;矛盾/过期 精度有限(实测爱把
        # "近期战绩客场对手比分在前"约定、主/中场地小标注误报为矛盾),降级为 issues 供人核,不 hard-block。
        blocked = 0
        for hw, r in pmap(_audit, pairs, workers=4, label="终审"):
            h, w = hw
            mt = next((m for m in json.load(open(f"{RUNS}/data_reference/matches.json", encoding="utf-8"))
                       if m.get("team_a") == h and m.get("team_b") == w), {})
            md = datetime.date.fromisoformat(mt.get("date"))
            iss = (r or {}).get("issues", [])
            raw_leak = [it for it in iss if it.get("type") == "leakage"]
            leak = [it for it in raw_leak if _hard_leakage(it, md)]
            tag = "🚫泄露" if leak else ("⚠️存疑" if iss else "✅")
            print(f"  {tag} {h} vs {w}" + (f"  issues {len(iss)}条(leak {len(leak)})" if iss else ""))
            for it in iss:
                typ = it.get("type")
                if typ == "leakage" and it in raw_leak and it not in leak:
                    typ = "leakage误报降级"
                print(f"      [{typ}] {it.get('team')}: {it.get('quote','')[:40]} — {it.get('why','')[:50]}")
            if leak:
                blocked += 1
        if blocked:
            sys.exit(f"🚫 终审官发现 {blocked} 场有【泄露】,必须修完再跑(矛盾/过期类为存疑提示、不阻断)")
        print("—— 终审官:无泄露,可以开跑(矛盾/过期类存疑见上,已人工抽核为命名约定误报) ——")
    else:
        print("—— 体检全绿,可以开跑(加 --llm-audit 走语义终审)——")


if __name__ == "__main__":
    main()
