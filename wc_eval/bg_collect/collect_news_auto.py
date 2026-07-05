#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【队伍新闻 · 全 py 自动采集 = ⓪a 的代码实现】不再靠 agent 手动 WebSearch 找 URL:
py 自己用 web_search_urls(Apify Google,真实结果)为每队搜新闻源 → 黑名单去垃圾 → 喂 collect_team_news 抓全文。
身份键=URL,collect_team_news 自动判重(只抓新的)+ 写本轮 _news_attempts 留痕(过 news_preflight 门禁)。
全 48 队并行。与 collect_match(赛果)/collect_match_env(环境)/broadcast_round(播报)同为"全部信息收集"的 py 化一环。

跑:python3 collect_news_auto.py --asof 2026-06-20 --ts 2026-06-20_1556 [--teams ALL|CODE,CODE] [--workers 8]
"""
import os, sys, json, re, argparse, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, f"{ROOT}/wc_eval")
from llm_client import web_search_urls

_BAD = re.compile(r"(youtube\.com|/watch|/video|liveblog|en-vivo|how-to-watch|como-ver|wikipedia\.org|"
                  r"reddit\.com|facebook\.com|twitter\.com|x\.com/|instagram|tiktok|/odds|betting|tickets|"
                  r"\.pdf($|\?)|/shop|/store|fanatics|"
                  # 中国大陆封禁/敏感媒体:被采进 summary 当来源标注会触发 Kimi(Moonshot)/GLM(智谱)内容审查→400 拒答
                  r"epochtimes|theepochtimes|大纪元|ntdtv|ntd\.com|新唐人|soundofhope|希望之声|minghui|明慧|"
                  r"secretchina|看中国|aboluowang|阿波罗|dajiyuan|bannedbook|dafahao|falun|法轮)", re.I)
_ZH = ("163.com", "sina.com", "sohu.com", "qq.com", "zhibo8", "dongqiudi", "hupu.com", "thepaper.cn",
       "cctv.com", "titan24", "pptv", "sports.cn", "7m.com.cn", "zaobao", "creaders", "chineseherald")
_ES = (".com.ar", ".com.mx", "marca", "as.com", "ole", "clarin", "lanacion", "mundodeportivo", "rpp.pe",
       "elespectador", "infobae", "tycsports", "eldesmarque", "sport.es")


def _domain(u):
    try:
        return u.split("//", 1)[-1].split("/", 1)[0].lower().removeprefix("www.")
    except Exception:
        return ""


def discover_news_urls(en, zh):
    """py 自动发现一队的新闻源 URL(多语种 query · 黑名单去垃圾 · 每域名一条)。"""
    queries = [f"{en} World Cup 2026 latest team news injury lineup",
               f"{en} World Cup 2026 squad update preview",
               f"{zh} 世界杯 最新 伤停 阵容 新闻"]
    seen, out = set(), []
    for q in queries:
        for r in web_search_urls(q, n=12):
            u = r.get("link", "")
            if not u or _BAD.search(u):
                continue
            dom = _domain(u)
            tail = u.split("//", 1)[-1].split("/", 1)
            if len(tail) < 2 or len(tail[1].strip("/")) < 6 or dom in seen:
                continue
            has_cjk = any('一' <= c <= '鿿' for c in (r.get("title") or ""))
            lang = "zh" if (has_cjk or any(z in dom for z in _ZH)) else \
                   "es" if any(e in dom for e in _ES) else "en"
            name = (re.sub(r"[^a-z0-9]+", "_", dom).strip("_")[:24]) or "src"
            seen.add(dom)
            out.append({"name": name, "source": dom, "url": u, "tier": "2", "lang": lang})
    return out


def one_team(code, en, zh, asof, ts):
    urls = discover_news_urls(en, zh)
    if not urls:
        return code, 0, "✗自动发现无果"
    p = f"/tmp/_news_{code}.json"
    json.dump(urls, open(p, "w"), ensure_ascii=False)
    r = subprocess.run(["python3", "collect_team_news.py", "--team", code, "--asof", asof, "--ts", ts, "--urls", p],
                       cwd=HERE, capture_output=True, text=True)
    line = ""
    for ln in (r.stdout or "").splitlines():
        if "仓库累计" in ln or "本轮新抓" in ln:
            line = ln.strip()
    return code, len(urls), line or (r.stdout or r.stderr or "")[-120:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", required=True)
    ap.add_argument("--ts", required=True)
    ap.add_argument("--teams", default="ALL", help="ALL=全48队 · ALIVE=仅仍存活(有比赛)的队 · 或逗号队码")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    teams = {t["team_id"]: t for t in json.load(open(f"{RUNS}/data_reference/teams.json", encoding="utf-8"))}
    if a.teams == "ALL":
        codes = list(teams)
    elif a.teams.upper() == "ALIVE":
        from roster import alive_teams
        codes = alive_teams()
    else:
        codes = [c.strip() for c in a.teams.split(",") if c.strip()]
    scope = "全48" if a.teams == "ALL" else ("存活" if a.teams.upper() == "ALIVE" else "指定")
    print(f"▶ 队伍新闻全 py 自动采集:{len(codes)} 队({scope}) · asof={a.asof} ts={a.ts} · web_search_urls(Apify)自动发现源")
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one_team, c, teams[c].get("name_en", c), teams[c].get("name_zh", c), a.asof, a.ts): c
                for c in codes}
        for f in as_completed(futs):
            c = futs[f]
            try:
                code, n, line = f.result()
                done += 1
                print(f"  [{done}/{len(codes)}] {code}: 发现{n}源 · {line}")
            except Exception as e:
                done += 1
                print(f"  [{done}/{len(codes)}] {c}: ✗ {str(e)[:80]}")
    print("═══ NEWS_AUTO_DONE ═══")


if __name__ == "__main__":
    main()
