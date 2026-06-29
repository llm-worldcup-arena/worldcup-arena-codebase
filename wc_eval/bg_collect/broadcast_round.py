#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【赛事播报 · 整轮自动化 = matchday ⑤ 的真正实现】
把"为已结算但还没做播报的场"的整条播报线串成一步、接进 matchday 自动流程(此前缺这一接线 → 6/15 起播报漏采的 bug):
  ① fetch_sources 直抓多源逐字原文 → match_broadcast/<slug>/raws/   (URL 由 agent WebSearch 写进
     data_raw/<ts>/_broadcast_urls/<Mid>.json;这步是唯一需 agent 的检索,与 team_news 的 URL 发现同构)
  ② broadcast_synth 多源交叉合成 ours/(long/long_predictable/short/timeline,py-Kimi)
  ③ archive_broadcast_raws 把【新源】增量归档进 data_raw/<ts>/match_broadcast/(版本语义:按采集时分切片)
  ④ wc2026_build.append_block_b 把每队【所有已踢场】的播报嵌进 summary 块B(## 世界杯 2026 · 专项整理)
开关 config/wc_pipeline.json: auto_run_match_broadcast —— off=只复用已有、不抓不合成;on=为缺的场自动跑。
做过的场(有 ours/long.md)不 remake;但若正文源过少/long 过短/只有硬数据,会自动补源重合成。

跑:python3 broadcast_round.py --snapshot <snap> --ts <ts>
   python3 broadcast_round.py --snapshot <snap> --ts <ts> --only CZE-RSA,SUI-BIH
   python3 broadcast_round.py --snapshot <snap> --ts <ts> --refresh
"""
import os, sys, json, glob, re, argparse, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
HERE = os.path.dirname(os.path.abspath(__file__))
MR = f"{ROOT}/wc_eval/match_report"
MB = f"{RUNS}/data_processed/match_broadcast"
MIN_TEXT_SOURCES = 3
MIN_LONG_CHARS = 1600
sys.path.insert(0, f"{ROOT}/wc_eval")
sys.path.insert(0, HERE)
from wc2026_build import append_block_b, mb_done, mb_integration_on, archive_broadcast_raws
try:
    from wc_llm import kimi_text
except Exception:
    kimi_text = None
try:
    from llm_client import web_search_urls          # py 自带联网搜索(智谱端点)→ 播报源自动发现 fallback
except Exception:
    web_search_urls = None

# 自动发现:黑名单过滤(Google organic 本就优选,只去垃圾)+ 启发式 tier/lang(比手维护白名单更客观)
_T1 = ("fifa.com", "apnews.com", "reuters.com")                  # 官方/通讯社
_T2 = ("skysports.com", "espn.com", "espn.co.uk", "foxsports.com", "nbcsports.com", "cbssports.com",
       "bbc.com", "bbc.co.uk", "theguardian.com", "aljazeera.com", "theanalyst.com", "goal.com",
       "sports.yahoo.com", "yahoo.com", "sportingnews.com", "si.com", "cbc.ca", "tsn.ca", "sportsnet.ca",
       "marca.com", "as.com", "mundodeportivo.com")              # 顶级体育/主流
_ZH_DOM = ("163.com", "sina.com", "sina.com.cn", "sohu.com", "qq.com", "zhibo8", "dongqiudi", "hupu.com",
           "thepaper.cn", "cctv.com", "titan24", "pptv", "baidu.com")
_ES_DOM = (".com.ar", ".com.mx", "marca", "as.com", "ole", "clarin", "lanacion", "mundodeportivo",
           "rpp.pe", "elespectador", "infobae", "tycsports", "eldesmarque", "sport.es")
_BAD_URL = re.compile(r"(youtube\.com|/watch|/video|/videos/|liveblog|/live/|live-updates|live-blog|en-vivo|"
                      r"envivo|minuto-a-minuto|how-to-watch|como-ver|wikipedia\.org|reddit\.com|facebook\.com|"
                      r"twitter\.com|x\.com/|instagram|flashscore|livescore|sofascore|/odds|betting|tickets|"
                      r"\.pdf($|\?)|365scores\.com|threads\.com|iplayer|/highlights/?$|/match/|/fixture/|"
                      r"luxiang|/luxiang|podcast|"
                      # 中国大陆封禁/敏感媒体(进 summary 当来源会触发 Kimi/GLM 审查)
                      r"epochtimes|theepochtimes|ntdtv|ntd\.com|soundofhope|minghui|secretchina|aboluowang|"
                      r"dajiyuan|bannedbook|dafahao|falun)", re.I)


def _classify(url, title):
    dom = _domain(url)
    tier = "1" if any(dom.endswith(d) for d in _T1) else "2" if any(d in dom for d in _T2) else "3"
    has_cjk = any('一' <= c <= '鿿' for c in (title or ""))
    lang = "zh" if (has_cjk or any(z in dom for z in _ZH_DOM)) else \
           "es" if any(e in dom for e in _ES_DOM) else "en"
    name = (re.sub(r"[^a-z0-9]+", "_", dom).strip("_")[:24]) or "src"
    return name, dom, tier, lang

_HOSTS = {"MEX", "USA", "CAN"}                                   # 2026 三东道主(与 common.py 同源)
_MX_CITY = {"Mexico City", "Guadalajara", "Zapopan", "Monterrey"}
_CA_CITY = {"Toronto", "Vancouver"}
_ROUND_CN = {"group": "小组赛", "r32": "32 强", "r16": "16 强", "qf": "1/4 决赛", "sf": "半决赛", "final": "决赛"}


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def _teams():
    return {t["team_id"]: t for t in _load(f"{RUNS}/data_reference/teams.json")}


def settled_matches():
    """已结算场 = results.json 的 matches 键(A_vs_B 队码)。返回带 matches.json 元数据的 list。"""
    res = _load(f"{RUNS}/archive/results.json")["matches"]
    by = {(m["team_a"], m["team_b"]): m for m in _load(f"{RUNS}/data_reference/matches.json")}
    out = []
    for key, sc in res.items():
        a, b = key.split("_vs_")
        m = by.get((a, b))
        if not m:
            print(f"  ⚠️ results 有 {key} 但 matches.json 无此对阵,跳过")
            continue
        out.append({"key": key, "mid": m["match_id"], "date": m["date"],
                    "round": m.get("round", "group"), "group": m.get("group", ""),
                    "venue_id": m.get("venue_id"), "a": a, "b": b,
                    "score": sc.get("score", ""), "ht": sc.get("ht", ""),
                    "slug": f"{m['date']}_{a}_vs_{b}", "bc": f"{MB}/{m['date']}_{a}_vs_{b}"})
    return out


def _ha(team, opp, venue_id, venues):
    """主/客/中(带城市):东道主在本国=主、对手在对方国=客、否则中立。沿用 common.py 的 venue→国家判断。"""
    v = venues.get(venue_id, {}); city = v.get("city", "")
    vcountry = "MEX" if city in _MX_CITY else "CAN" if city in _CA_CITY else "USA"
    if team in _HOSTS and vcountry == team:
        return f"主场({city})" if city else "主"
    if opp in _HOSTS and vcountry == opp:
        return f"客场({city})" if city else "客"
    return f"中({city})" if city else "中"


def _result_for(team, m):
    """从 team 视角的 '比分 胜/平/负'(team_b 视角翻转比分)。"""
    try:
        ga, gb = [int(x) for x in m["score"].split("-")]
    except Exception:
        return m["score"]
    tg, og = (ga, gb) if team == m["a"] else (gb, ga)
    return f"{tg}-{og} {'胜' if tg > og else '平' if tg == og else '负'}"


IMPACT_SYS = ("你是世界杯数据分析。给你一场已结束比赛的赛事播报,只提取对【指定球队】**下一场**有直接影响的"
              "硬信息:红牌停赛、伤退/伤情、关键球员复出或状态拐点。每条一行 markdown 无序列表(- 开头),"
              "最多 4 条;确实没有则只回两个字:无。客观、不杜撰原文没有的,不要前言、不要解释。")


def gen_impact(m, team, team_zh):
    """py-Kimi 从该场 short/long 提取对 team 下一场的影响 bullet(幂等缓存 ours/impact_<TEAM>.md;尽力而为)。"""
    bc = m["bc"]
    cache = f"{bc}/ours/impact_{team}.md"
    if os.path.exists(cache):
        txt = open(cache, encoding="utf-8").read().strip()
        return [l[1:].strip() for l in txt.split("\n") if l.strip().startswith("-")]
    if kimi_text is None:
        return []
    src = None
    for fn in ("short.md", "long_predictable.md", "long.md"):
        p = f"{bc}/ours/{fn}"
        if os.path.exists(p):
            src = open(p, encoding="utf-8").read(); break
    if not src:
        return []
    try:
        out = kimi_text(IMPACT_SYS, f"【指定球队】{team_zh}（{team}）\n【对手】{m['a'] if team==m['b'] else m['b']}\n\n【赛事播报】\n{src[:6000]}").strip()
    except Exception as e:
        print(f"    ⚠️ {team} impact 生成失败({str(e)[:40]})"); return []
    bullets = [l[1:].strip() for l in out.split("\n") if l.strip().startswith("-")]
    os.makedirs(f"{bc}/ours", exist_ok=True)
    open(cache, "w", encoding="utf-8").write(out if bullets else "无")
    return bullets


def _domain(url):
    try:
        return url.split("//", 1)[-1].split("/", 1)[0].lower().removeprefix("www.")
    except Exception:
        return ""


def discover_urls(m, exclude_names):
    """【自动发现 · 全 py 驱动】py 自己联网搜该场赛报源(web_search_urls→Apify Google),黑名单去垃圾+去重(每域名一条)
    +启发式定 tier/lang → 候选 urls。多语种 query(英/中/西)求覆盖广。返回 [{name,source,url,tier,lang}]。"""
    if web_search_urls is None:
        return []
    teams = _teams(); a, b = m["a"], m["b"]
    aen = teams.get(a, {}).get("name_en", a); ben = teams.get(b, {}).get("name_en", b)
    azh = teams.get(a, {}).get("name_zh", a); bzh = teams.get(b, {}).get("name_zh", b)
    queries = [f"{aen} {m['score']} {ben} World Cup 2026 match report",
               f"{aen} vs {ben} World Cup 2026 report highlights goals",
               f"{azh} {bzh} 世界杯 战报 集锦",
               f"{aen} {ben} crónica mundial 2026"]
    seen, out = set(), []
    for q in queries:
        for r in web_search_urls(q, n=12):
            url = r.get("link", "")
            if not url or _BAD_URL.search(url):
                continue
            name, dom, tier, lang = _classify(url, r.get("title", ""))
            tail = url.split("//", 1)[-1].split("/", 1)
            if len(tail) < 2 or len(tail[1].strip("/")) < 8:        # 跳过首页/过短路径
                continue
            if dom in seen or name in exclude_names:
                continue
            seen.add(dom)
            out.append({"name": name, "source": dom, "url": url, "tier": tier, "lang": lang})
    # Keep the retry budget bounded.  Prefer T1/T2 match-report pages, then a
    # small number of T3 text articles for language diversity.
    out.sort(key=lambda x: (int(x.get("tier") or 3), x.get("lang") != "en", x["name"]))
    return out[:5]


def collect_one(m, ts, refresh):
    """为一场收集播报(**增量**):agent urls 优先、无则自动发现;只抓【新源】(name 不在 raws);
    没做过→合成,做过但有新源→--refresh 重合成(新信息判断要不要改 ours),无新源→不动。返回状态串。"""
    bc = m["bc"]; done = mb_done(bc)
    existing = set(os.listdir(f"{bc}/raws")) if os.path.isdir(f"{bc}/raws") else set()
    q = broadcast_quality(bc)
    quality_refresh = bool(done and q["needs_refresh"])
    af = f"{RUNS}/data_raw/{ts}/_broadcast_urls/{m['mid']}.json"
    if os.path.exists(af):
        urls = json.load(open(af, encoding="utf-8")); kind = "agent源"          # agent 显式补的源(可选)优先
    elif done and not refresh and not quality_refresh:
        return "复用(已做过)"          # 增量:质量达标的已做场直接复用;质量不足的场会自动补源
    else:
        urls = discover_urls(m, existing); kind = "自动发现"
    new_urls = [u for u in urls if u["name"] not in existing]      # 只抓新源(身份键=源名)
    if not new_urls and not done:
        return f"✗缺URL({kind}无果 → agent 需 WebSearch 写 _broadcast_urls/{m['mid']}.json)"
    fetched = 0
    if new_urls:
        tmp = f"/tmp/_bcurls_{m['mid']}.json"
        json.dump(new_urls, open(tmp, "w"), ensure_ascii=False)
        subprocess.call(["python3", "fetch_sources.py", "--match", m["mid"], "--urls", tmp, "--no-apify"], cwd=MR)
        after = set(os.listdir(f"{bc}/raws")) if os.path.isdir(f"{bc}/raws") else set()
        fetched = len(after - existing)
    remake = (not done) or bool(fetched) or refresh or (quality_refresh and q["long_len"] < MIN_LONG_CHARS)
    if remake:                                                     # 没做过/有新源/强制/短 long → (重)合成
        cmd = ["python3", "broadcast_synth.py", "--slug", m["slug"]]
        if done or refresh:
            cmd.append("--refresh")
        subprocess.call(cmd, cwd=HERE)
    _, n = archive_broadcast_raws(ts, bc)
    if done and not fetched:
        if quality_refresh:
            return f"⚠质量不足({q['reason']})·重查{kind}无新源" + ("→已重合成" if remake else "")
        return f"复用(重查{kind}无新源)"
    q2 = broadcast_quality(bc)
    return (f"{kind}:抓{fetched}新源→{'(重)合成' if remake else '不动'}→归档{n}新源"
            f"{' · 质量仍偏低(' + q2['reason'] + ')' if q2['needs_refresh'] else ''}"
            + ("" if mb_done(bc) else " ⚠仍无long.md"))


def broadcast_quality(bc):
    """Return coarse quality signals for an existing match_broadcast product.

    harddata/macheta is valuable, but it is not a narrative match report. A
    finished broadcast should have several text article sources and a long.md
    that is not just the structured data restated.
    """
    raws = f"{bc}/raws"
    srcs = sorted(os.listdir(raws)) if os.path.isdir(raws) else []
    text_srcs = [s for s in srcs if s != "apify_macheta"]
    longp = f"{bc}/ours/long.md"
    long_len = len(open(longp, encoding="utf-8").read()) if os.path.exists(longp) else 0
    reasons = []
    if os.path.exists(longp) and len(text_srcs) < MIN_TEXT_SOURCES:
        reasons.append(f"正文源{text_srcs and len(text_srcs) or 0}<{MIN_TEXT_SOURCES}")
    if os.path.exists(longp) and long_len < MIN_LONG_CHARS:
        reasons.append(f"long {long_len}<{MIN_LONG_CHARS}")
    if os.path.exists(longp) and srcs == ["apify_macheta"]:
        reasons.append("仅硬数据源")
    return {
        "sources": len(srcs),
        "text_sources": len(text_srcs),
        "long_len": long_len,
        "needs_refresh": bool(reasons),
        "reason": ",".join(reasons) or "ok",
    }


def embed_team(snap, team, team_settled, venues, teams):
    """把 team 所有【已踢且已做播报】的场嵌进块B。返回嵌入场数。"""
    team_settled = sorted(team_settled, key=lambda x: (x["date"], x["mid"]))   # 定轮次顺序
    played = []
    for idx, m in enumerate(team_settled):
        if not mb_done(m["bc"]):
            continue                                                   # 没做播报的场不嵌(门禁会标红)
        opp = m["b"] if team == m["a"] else m["a"]
        team_zh = teams.get(team, {}).get("name_zh", team)
        played.append({
            "date": m["date"],
            "round": f"第{idx+1}轮·{_ROUND_CN.get(m['round'], m['round'])}",
            "ha": _ha(team, opp, m["venue_id"], venues),
            "opp": opp,
            "result": _result_for(team, m),
            "bc": m["bc"],
            "impact": gen_impact(m, team, team_zh),
        })
    if played:
        append_block_b(snap, team, played)
    return len(played)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True, help="嵌块B的快照,如 2026-06-19_1138")
    ap.add_argument("--ts", required=True, help="本轮采集时分(归档/urls 路径用)")
    ap.add_argument("--only", default="", help="只跑指定场 A-B,A-B(默认所有已结算场)")
    ap.add_argument("--refresh", action="store_true", help="强制重抓+重合成已做过的场")
    ap.add_argument("--force", action="store_true", help="无视 auto_run_match_broadcast 开关强制采集")
    ap.add_argument("--embed-only", dest="embed_only", action="store_true",
                    help="只重嵌块B(跳过采集/合成)——改了块B生成逻辑后快速重嵌全队,不动 Apify")
    ap.add_argument("--workers", type=int, default=3,
                    help="采集/合成按场并发数;嵌 summary 块B 仍串行写入")
    a = ap.parse_args()

    on = mb_integration_on() or a.force
    allm = settled_matches()
    if a.only.strip():
        want = set(tuple(x.strip().split("-")) for x in a.only.split(","))
        allm = [m for m in allm if (m["a"], m["b"]) in want]
    venues = _load(f"{RUNS}/data_reference/venues.json")
    teams = _teams()

    print(f"▶ 赛事播报整轮 · 快照{a.snapshot} · 开关 auto_run_match_broadcast={'ON' if on else 'OFF'}"
          f"{'(--force 强开)' if a.force and not mb_integration_on() else ''} · 已结算 {len(allm)} 场")

    # ── 采集+合成(增量:做过的场复用、只收没做过的;off 只复用已有;--embed-only 整段跳过) ──
    miss_url = []
    fresh = []                          # 本轮【新收集到播报】的场 → 只重嵌这些场涉及的队(增量,省时)
    if not a.embed_only:
        def one_match(m):
            if on:
                st = collect_one(m, a.ts, a.refresh)
            else:
                st = "复用(已做过)" if mb_done(m["bc"]) else "✗缺播报(开关OFF,跳过采集)"
            return m, st

        workers = max(1, min(a.workers, len(allm) or 1))
        if workers == 1:
            results = [one_match(m) for m in allm]
        else:
            print(f"▶ 播报采集/合成并行 · workers={workers}")
            results = []
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = {ex.submit(one_match, m): m for m in allm}
                for f in as_completed(futs):
                    try:
                        results.append(f.result())
                    except Exception as e:
                        m = futs[f]
                        results.append((m, f"✗异常:{str(e)[:100]}"))
        for m, st in sorted(results, key=lambda x: (x[0]["date"], x[0]["mid"])):
            if "缺URL" in st or "缺播报" in st or st.startswith("✗"):
                miss_url.append(m["key"])
            elif not st.startswith("复用"):       # 真正新收集/重合成了
                fresh.append(m)
            print(f"  · {m['key']:<14} {st}")
    else:
        print("  (--embed-only:跳过采集/合成,只重嵌块B)")

    # ── 嵌块B:增量只嵌【本轮新收集场】涉及的队(--embed-only 或 --refresh 则全嵌) ──
    if a.embed_only or a.refresh:
        bteams = sorted({m["a"] for m in allm} | {m["b"] for m in allm})
    else:
        bteams = sorted({m["a"] for m in fresh} | {m["b"] for m in fresh})
    print(f"▶ 嵌 summary 块B(专项整理)· {'全' if (a.embed_only or a.refresh) else '增量'}涉及 {len(bteams)} 队")
    embedded = 0
    for t in bteams:
        ts_m = [m for m in settled_matches() if t in (m["a"], m["b"])]      # 该队【全部】已结算场(不止本轮)
        n = embed_team(a.snapshot, t, ts_m, venues, teams)
        if n:
            embedded += 1
        print(f"  · {t}: 嵌 {n} 场播报")

    print(f"═══ 播报整轮完成:已结算 {len(allm)} 场 · 嵌块B {embedded} 队"
          + (f" · ⚠{len(miss_url)} 场缺源待补:{miss_url}" if miss_url else " · 全部就绪"))


if __name__ == "__main__":
    main()
