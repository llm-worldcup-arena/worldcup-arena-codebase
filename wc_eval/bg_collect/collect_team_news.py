#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【队伍新闻 · 双写采集】raw=收集过程(按时分,只记本次新增) + processed=加工成熟仓库(按队累积)。

架构(数据定型):
  processed/team_news/<队>/<新闻日期>_<源>.json   ← 成熟仓库:世界杯开赛后该队全部新闻,逐条累积
                                                    文件名=新闻日期(更有效时间);内含 news_date/published/fetched
  data_raw/<时分>/team_news/<队>/<同名>.json         ← 收集过程留底:本次【新增】的复制(只记新的,不重复)
  新旧判断:身份键=URL,【以 processed 仓库为准】(新的才双写;--refresh 重拍快照)

下游:全文走 summary【块A】(原结构增量)——进块A前由 LLM 三判(是否新/要不要加/正确性),只增不改
     (唯一例外:发现旧条目错了才允许修正,记 CHANGELOG)。块B 的赛事播报仍由 match_broadcast 供给。

跑:python3 collect_team_news.py --team CAN --asof 2026-06-12 --ts 2026-06-13_0247 --urls /tmp/can.json
   python3 collect_team_news.py --team CAN --suggest --opp BIH    # 打印标准检索词+源名单
"""
import os, sys, json, argparse, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
CURATED = f"{RUNS}/data_processed/team_news"          # 加工成熟仓库(按队累积,新旧判断以此为准)
sys.path.insert(0, f"{ROOT}/wc_eval/match_report")
import fetch_sources as FS                       # 复用 fetch/extract/质量门/Apify 兜底
from naming_util import valid_ts, valid_asof     # 命名规范强制


# ════ 找源规范(成文检索依据,配 skill wc-incremental-update;--suggest 打印) ════
# 队伍新闻 · 源分层(与 match_broadcast 同思路:T1 官方/通讯社 → T2 主流体育媒体 → T3 专项/本地/中文)
NEWS_TIERS = {
    "T1 官方/通讯社": ["FIFA.com", "该队足协官网/官方账号", "AP 美联社", "Reuters 路透"],
    "T2 主流体育媒体": ["ESPN", "Sky Sports", "FOX Sports", "CBS", "NBC", "Yahoo Sports",
                      "Goal.com", "Olympics.com", "The Athletic"],
    "T3 专项/本地/中文": ["RotoWire(伤停专门)", "Sports Mole(赛前预览)", "SI", "Sportskeeda",
                       "队属国当地大报", "中文:网易/新浪/直播吧/懂球帝"],
}


def gen_queries(team_en, opp_en=None, date=None, team_zh=None):
    """标准关键词模板(~10 条,稳定覆盖各维度):队名 + World Cup 2026 + 主题词 + 锚点(对手/日期)。
    覆盖:伤停/名单/首发/赔率预测/主帅发布会/停赛可用性/近期状态/战术对位/历史交锋。中英都搜,不临场乱编。
    临战可再经 suggest_queries(wc_llm,LLM 判断)按当下情境补充关键词。"""
    vs = f" vs {opp_en}" if opp_en else ""
    opp = f" {opp_en}" if opp_en else ""
    q = [f"{team_en} World Cup 2026 squad injury news",
         f"{team_en} World Cup 2026 lineup team news{(' ' + opp_en + ' match') if opp_en else ''}",
         f"{team_en} injury update June 2026{vs}",
         f"{team_en}{vs} World Cup 2026 odds prediction preview",   # 赔率/预测预览(放宽收录后固定钓这一类)
         f"{team_en} predicted lineup World Cup 2026{vs}",          # 预测首发
         f"{team_en} manager press conference World Cup 2026",      # 主帅发布会口径
         f"{team_en} suspension availability World Cup 2026",       # 停赛/可用性
         f"{team_en} recent form results 2026"]                     # 近期状态/战绩
    if team_zh:
        q += [f"{team_zh} 世界杯 伤停 名单 最新",
              f"{team_zh} 世界杯 首发 预测 {date or ''}".strip(),
              f"{team_zh}{(' 对 ' + '') if False else ''} 世界杯 赔率 预测".strip()]
    return q


def _team_names(code):
    t = next((x for x in json.load(open(f"{RUNS}/data_reference/teams.json", encoding="utf-8"))
              if x.get("team_id") == code), {})
    return t.get("name_en", code), t.get("name_zh", "")


def _fetched_urls(team):
    """新旧判断依据(身份键=URL):【以 processed 成熟仓库为准】,兼扫 raw 历史兜底。
    返回 {已收录URL: 文件路径}。"""
    import glob
    done = {}
    for pat in (f"{CURATED}/{team}/*.json",                       # 主:成熟仓库(开赛后)
                f"{RUNS}/data_processed/prematch_news/{team}/*.json",  # 主:成熟仓库(赛前)
                f"{RUNS}/data_raw/*/team_news/{team}/*.json",       # 兜底:raw 过程(老件)
                f"{RUNS}/data_raw/*/prematch_news/{team}/*.json"):
        for p in glob.glob(pat):
            try:
                u = json.load(open(p, encoding="utf-8")).get("url")
                if u and u not in done:
                    done[u] = p
            except Exception:
                pass
    return done


def _news_date(published, asof):
    """更有效时间 = 新闻发布日(解析得出);解析不了用信息日 asof。"""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", (published or ""))
    return m.group(1) if m else asof


def collect(team, asof, ts, urls, min_chars=300, refresh=False, prematch=False):
    kind = "prematch_news" if prematch else "team_news"      # 赛前新闻补课 → 落 prematch 仓库
    rawd = f"{RUNS}/data_raw/{ts}/{kind}/{team}"             # 收集过程(本次新增)
    curd = f"{RUNS}/data_processed/{kind}/{team}"            # 成熟仓库(累积)
    done = _fetched_urls(team)
    token = FS.apify_token()
    ok = blocked = skipped = 0
    made = False
    for e in urls:
        name = e["name"]
        # ── 新旧判断:URL 已在 processed 仓库 → 默认跳过;--refresh / 条目 refresh:true 强制重拍快照
        #    (重拍适合"内容会更新的实时页"如 ESPN 伤停追踪;已发表的普通文章无需重拍) ──
        if e["url"] in done and not (refresh or e.get("refresh")):
            skipped += 1
            print(f"  ⏭ {name:20s} 仓库已有(同URL) → 跳过;原件: {done[e['url']].split('wc_runs/')[-1]}")
            continue
        if not made:
            os.makedirs(rawd, exist_ok=True); os.makedirs(curd, exist_ok=True); made = True
        try:
            text, method, title, pub, rawlen = FS.fetch(e["url"])
        except Exception as ex:
            text, method, title, pub = "", "fail", None, None
            print(f"  ✗ {name:20s} 直抓异常:{str(ex)[:50]}")
        # 被反爬挡(空/直播垃圾)→ 有 token 用 Apify 兜底
        if (len(text) < min_chars or FS.is_junk(text)) and token and e.get("apify", True):
            try:
                atext, atitle = FS.fetch_apify(e["url"], token)
                if len(atext) >= min_chars and not FS.is_junk(atext):
                    text, method, title = atext, "apify", (atitle or title)
            except Exception:
                pass
        status = "ok" if (len(text) >= min_chars and not FS.is_junk(text)) else "blocked"
        nd = _news_date(pub, asof)                            # 更有效时间:新闻发布日(无则信息日)
        rec = {"team": team, "source": e.get("source", name), "url": e["url"],
               "title": title, "news_date": nd, "published": pub,
               "tier": e.get("tier", ""), "lang": e.get("lang", ""),
               "asof": asof, "fetched": ts, "method": method, "status": status,
               "original_text": text,
               "_note": "全文走 summary 块A(LLM三判后只增不改);processed=成熟仓库累积,raw=本次收集过程。"}
        fn = f"{nd}_{name}.json"                              # 文件名带新闻日期(利于按时序判断)
        body = json.dumps(rec, ensure_ascii=False, indent=1)
        open(f"{curd}/{fn}", "w", encoding="utf-8").write(body)    # ① 成熟仓库(累积)
        open(f"{rawd}/{fn}", "w", encoding="utf-8").write(body)    # ② 收集过程(本次新增)
        if status == "ok":
            ok += 1; print(f"  ✅ {fn:34s} {len(text):5d}字 [{method}] {(title or '')[:36]}")
        else:
            blocked += 1; print(f"  ⚠️ {fn:34s} {len(text)}字 被挡/过短 → 标 blocked,待换源")
    # 来源说明(真写了东西才留)
    sp = f"{rawd}/_source.md"
    if made and not os.path.exists(sp):
        open(sp, "w", encoding="utf-8").write(
            f"# {team} · 队伍新闻收集过程留底（asof {asof}）\n"
            "- **双写**：本目录=本次【新增】的收集过程留底；同内容已累积进成熟仓库 "
            "`processed/team_news/<队>/`（按队累积、文件名带新闻日期）。\n"
            "- **方式**：按 gen_queries 标准关键词 WebSearch 找源(按 NEWS_TIERS 分层优先) → "
            "fetch_sources 直抓逐字全文（+Apify 兜底+质量门），不经模型改写。\n"
            "- **新旧判断**：身份键=URL、以 processed 仓库为准；已有默认跳过（--refresh 重拍快照）。\n"
            "- **下游**：全文走 summary 块A（LLM 三判后只增不改）；≥2 源交叉、防张冠李戴。\n")
    # 本轮"搜过"留痕(即使 0 新增也写)——区分"搜了没新"(合法) vs "没搜"(降级)。配 news_preflight 尝试制门禁消假绿灯。
    # urls_checked = 本轮喂了几个 URL(喂空列表假装搜过 → urls_checked=0,门禁能识破)。
    amd = f"{RUNS}/data_raw/{ts}/_news_attempts"
    os.makedirs(amd, exist_ok=True)
    json.dump({"team": team, "ts": ts, "urls_checked": len(urls), "new": ok, "blocked": blocked, "skipped": skipped},
              open(f"{amd}/{team}.json", "w", encoding="utf-8"), ensure_ascii=False)
    return ok, blocked, skipped, rawd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True, help="队 FIFA 码")
    ap.add_argument("--asof", help="信息日 YYYY-MM-DD")
    ap.add_argument("--ts", help="raw 留底时分 YYYY-MM-DD_HHMM")
    ap.add_argument("--urls", help="urls.json [{name,source,url,tier,lang[,refresh]}]")
    ap.add_argument("--suggest", action="store_true", help="打印该队标准检索词(中/英)+源分层名单(检索按此跑)")
    ap.add_argument("--opp", help="对手码(配 --suggest 作锚点)")
    ap.add_argument("--date", help="比赛日(配 --suggest 作锚点)")
    ap.add_argument("--context", help="临战情境(给LLM判断是否补检索词)")
    ap.add_argument("--prematch", action="store_true", help="赛前新闻补课模式:落 data_processed/prematch_news/(开赛前的新闻)")
    ap.add_argument("--refresh", action="store_true", help="历史已抓的 URL 也强制重抓(重拍快照,适合实时更新页)")
    a = ap.parse_args()

    if a.suggest:                                  # ── 成文检索依据:标准词 + 名单 ──
        en, zh = _team_names(a.team)
        oen = _team_names(a.opp)[0] if a.opp else None
        base = gen_queries(en, oen, a.date, zh)
        print(f"▶ {a.team}({en}) 标准检索词(中/英都搜,{len(base)}条):")
        for q in base:
            print(f"   · {q}")
        # ── 启动前 LLM 判断:按当下情境是否要补关键词(--context 给情境;无 key 时静默跳过)──
        if a.context:
            try:
                import sys as _s; _s.path.insert(0, f"{ROOT}/wc_eval")
                from wc_llm import suggest_queries
                sg = suggest_queries(a.team, base, a.context)
                if sg.get("add"):
                    print(f"▶ LLM 临战补充检索词(情境:{a.context[:40]}…):")
                    for q in sg["add"]:
                        print(f"   + {q}")
                    print(f"   (理由:{sg.get('why','')[:60]})")
            except Exception as e:
                print(f"   (LLM 关键词建议跳过:{str(e)[:40]})")
        print("▶ 选源按分层优先(每队≥3-5源,T1/T2优先,≥2源交叉;避开 live/导视页):")
        for tier, srcs in NEWS_TIERS.items():
            print(f"   {tier}: {', '.join(srcs)}")
        return

    for req in ("asof", "ts", "urls"):
        if not getattr(a, req):
            raise SystemExit(f"✗ 缺 --{req}(采集模式必填;只想看检索词用 --suggest)")
    valid_asof(a.asof); valid_ts(a.ts)            # 命名规范强制
    urls = json.load(open(a.urls, encoding="utf-8"))
    print(f"▶ {a.team} 队伍新闻双写采集（asof {a.asof}）→ {len(urls)} 源 → processed/team_news/{a.team}/ + data_raw/{a.ts}/")
    ok, blocked, skipped, rawd = collect(a.team, a.asof, a.ts, urls, refresh=a.refresh, prematch=a.prematch)
    # 强制边收边报数:仓库累计源 + 是否达标(MIN=3),偷工当场可见、藏不住(配 news_preflight 硬门禁)
    kind = "prematch_news" if a.prematch else "team_news"
    total = len([p for p in glob.glob(f"{RUNS}/data_processed/{kind}/{a.team}/*.json")
                 if (json.load(open(p, encoding="utf-8")).get("status", "ok") == "ok")])
    flag = "✓" if total >= 3 else f"✗仅{total}源(<3,门禁会拦)"
    print(f"  → {a.team}: 本轮新抓 {ok} / 被挡 {blocked} / 跳过 {skipped} · 仓库累计 {total} 源 {flag}")


if __name__ == "__main__":
    main()
