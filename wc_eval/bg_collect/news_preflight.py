#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【新闻收集 · 硬门禁(py 是范围与源标准的唯一权威)】
把"全 48 队、每队 ≥N 源、本轮都搜过、情报不陈旧"从【靠自觉】变成【代码强制】——downscale 在这一层就做不到。

> 唯一权威:**范围(48 队)/ 每队最小源数 / 本轮尝试 / 陈旧阈值,全写死在这里**。skill 只引用本文件、不另立标准
>(历史教训:skill 写"非比赛队轻扫"、py 却一视同仁 → "按 py"成歧义指令,模型每次都猜、每次都降级)。
> 不分"深抓/轻扫":**统一标准**。某队确无足量新闻 → `--allow-below <队>` 显式放行 + CHANGELOG 记明,默认不放行。

三道检查(成熟仓库 + 本轮留痕):
 ① **范围**:teams.json 全 48 队,一个不少;
 ② **数量**:每队 processed/team_news/<队>/ 逐字全文源 ≥ MIN_SOURCES(默认 3)——硬;
 ③ **本轮尝试(--round <ts> 时)**:每队本轮都有"搜过"留痕 `data_raw/<ts>/_news_attempts/<队>.json` 且 urls_checked≥MIN_URLS
    ——**这才消"假绿灯"**:设计是"全搜只记新",0 新增合法;但"搜了没新"必须留痕,"没搜"=无留痕=拦(硬)。
 ④ **陈旧告警**:某队最新一条源 > STALE_DAYS 天没更新 → 黄色告警(不硬拦——队可能真没动静,但要可见,防拿陈年伤停名单预测)。
逐队打印 `团队 NN/48 XXX: N源 [langs] · 本轮搜M源 · 最新d天前 状态`;**①②③ 任一不过 → exit 1**。

跑:python3 news_preflight.py                          # 只查累计(范围+数量)
   python3 news_preflight.py --round 2026-06-15_0918  # 加本轮尝试制(matchday 预测前这样调)
   python3 news_preflight.py --allow-below CUW,HAI    # 显式放行确无足量新闻的队
"""
import os, sys, json, glob, argparse, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
TEAMS_JSON = f"{RUNS}/data_reference/teams.json"

# ── 唯一权威:范围与标准(改这里 = 改全流程,skill 引用不另立) ──
MIN_SOURCES = 3        # 每队成熟仓库最少逐字全文源数(数量维度)
MIN_LANGS = 1          # 每队最少语种数;设 2 则强制多语种
MIN_URLS = 1           # 本轮"搜过"至少喂几个 URL(防喂空列表假装搜)
STALE_DAYS = 5         # 最新一条源超过这么多天没更新 → 陈旧告警(新鲜度维度)


def all_teams():
    return sorted(x["team_id"] for x in json.load(open(TEAMS_JSON, encoding="utf-8")))


def team_sources(team):
    """成熟仓库 processed/team_news/<队>/ → (源数, 语种集, 最新news_date 或 None)。"""
    langs, n, newest = set(), 0, None
    for p in glob.glob(f"{RUNS}/data_processed/team_news/{team}/*.json"):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if (d.get("status", "ok") == "ok") and len((d.get("text") or d.get("original_text") or "")) >= 200:
            n += 1
            if d.get("lang"):
                langs.add(d["lang"])
            nd = (d.get("news_date") or "")[:10]
            if len(nd) == 10 and (newest is None or nd > newest):
                newest = nd
    return n, langs, newest


def round_attempt(team, ts):
    """本轮是否搜过该队 → urls_checked(无留痕返回 None=没搜)。"""
    p = f"{RUNS}/data_raw/{ts}/_news_attempts/{team}.json"
    if not os.path.exists(p):
        return None
    try:
        return int(json.load(open(p, encoding="utf-8")).get("urls_checked", 0))
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=MIN_SOURCES)
    ap.add_argument("--min-langs", type=int, default=MIN_LANGS)
    ap.add_argument("--round", dest="rnd", default="", help="本轮 ts;给了就强制'本轮48队都搜过'(尝试制)")
    ap.add_argument("--min-urls", type=int, default=MIN_URLS)
    ap.add_argument("--stale-days", type=int, default=STALE_DAYS)
    ap.add_argument("--today", default=datetime.date.today().isoformat(), help="陈旧基准日(默认系统今天)")
    ap.add_argument("--allow-below", default="", help="逗号分隔:显式放行确无足量新闻的队(需 CHANGELOG 记明)")
    a = ap.parse_args()
    allow = set(x.strip() for x in a.allow_below.split(",") if x.strip())
    today = datetime.date.fromisoformat(a.today)

    teams = all_teams()
    if len(teams) != 48:
        sys.exit(f"❌ teams.json 不是 48 队(实 {len(teams)})——范围基准异常,先修 teams.json")

    mode = f" · 本轮尝试制(round={a.rnd})" if a.rnd else " · 仅查累计"
    print(f"▶ 新闻硬门禁:全48队 · 每队≥{a.min}源 · ≥{a.min_langs}语种{mode} · 陈旧>{a.stale_days}天告警(py权威,不分深/轻)")
    fail, stale = [], []
    for i, t in enumerate(teams, 1):
        n, langs, newest = team_sources(t)
        age = (today - datetime.date.fromisoformat(newest)).days if newest else 9999
        att = round_attempt(t, a.rnd) if a.rnd else None
        # 硬:数量
        bad = []
        if n < a.min or len(langs) < a.min_langs:
            if t not in allow:
                bad.append(f"源{n}/语{len(langs)}")
        # 硬:本轮尝试(给了 --round 才查)
        if a.rnd and t not in allow:
            if att is None:
                bad.append("本轮没搜")
            elif att < a.min_urls:
                bad.append(f"本轮只喂{att}URL")
        if bad:
            fail.append((t, ";".join(bad)))
        # 软:陈旧
        if newest and age > a.stale_days and t not in allow:
            stale.append((t, age))
        flag = "✗" + ";".join(bad) if bad else ("☑放行" if t in allow else ("⚠陈旧" if (newest and age > a.stale_days) else "✓"))
        att_s = f" 本轮搜{att}源" if a.rnd and att is not None else (" 本轮没搜" if a.rnd else "")
        age_s = f"最新{age}天前" if newest else "无日期"
        print(f"  团队 {i:02d}/48 {t}: {n}源[{'/'.join(sorted(langs)) or '-'}]{att_s} · {age_s} {flag}")

    print("─" * 60)
    if stale:
        print(f"⚠️  陈旧告警 {len(stale)} 队(库存够但最新源 >{a.stale_days}天,小心拿旧情报预测):"
              + ", ".join(f"{t}({d}天)" for t, d in sorted(stale, key=lambda x: -x[1])[:10]))
    if fail:
        print(f"❌ 门禁不过:{len(fail)} 队 → " + "; ".join(f"{t}[{r}]" for t, r in fail))
        print(f"   补齐(≥{a.min}源{' + 本轮搜过' if a.rnd else ''})再来;某队确无足量新闻则 --allow-below 放行 + CHANGELOG 记明。")
        sys.exit(1)
    print(f"✅ 门禁通过:48/48 · 每队≥{a.min}源{' · 本轮全搜过' if a.rnd else ''}"
          + (f"(放行 {','.join(sorted(allow))})" if allow else "")
          + (f" · ⚠{len(stale)}队陈旧待留意" if stale else ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
