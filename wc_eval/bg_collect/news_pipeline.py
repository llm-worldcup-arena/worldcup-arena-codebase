#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【新闻 → summary 的 py 化判断管道】把"清洁循环 + 三件套(新?要?对?) + 落 summary ⑦ + CHANGELOG"
**全部用 py 调 Kimi 完成**——不再由对话里的 agent 临场判断(那样换个对话就不可复现)。

这是用户【关键要求】的落地:LLM 判断走 py 代码(wc_llm.py 调 DMXAPI Kimi),谁跑都一样。

对一个快照 + 一批队:
  1. 找每队【本轮新抓(fetched==ts)且 status=ok】的新闻;无新增的队 → 跳过(不动 summary,符合"没新信息就不生成");
  2. 每条新闻:clean_loop 清洁度自检+修(≤3) → judge_news 三判(新?要?对?);
  3. 三判全过的 → 收集 summary_line,去重后追加进该队 summary ⑦;只增不改;
  4. CHANGELOG 登记(每队一条,含进⑦几条/各因何被拒)。
并行:队内多条新闻并行判、队间也并行(线程池),大幅提速。

跑:python3 news_pipeline.py --snapshot 2026-06-13_1530 --ts 2026-06-13_1530 --teams ALL
   python3 news_pipeline.py --snapshot ... --ts ... --teams QAT,SUI    # 指定队
"""
import os, sys, json, glob, argparse, re
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
sys.path.insert(0, f"{ROOT}/wc_eval")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wc_llm import clean_loop, judge_news, consolidate_seven
from consolidate_round import should_consolidate
from changelog_util import append_change


def _seg7(summary):
    """取 summary ⑦关键动态段(判新参照)。"""
    if "## ⑦" in summary:
        return summary.split("## ⑦", 1)[1].split("\n## ", 1)[0]
    return ""


def _repo_titles(team):
    out = []
    for pat in (f"{RUNS}/data_processed/team_news/{team}/*.json",
                f"{RUNS}/data_processed/prematch_news/{team}/*.json"):
        for p in glob.glob(pat):
            try:
                out.append(json.load(open(p, encoding="utf-8")).get("title") or "")
            except Exception:
                pass
    return out


def _new_news(team, ts):
    """该队本轮(fetched==ts)新抓且 ok 的新闻。"""
    items = []
    for p in glob.glob(f"{RUNS}/data_processed/team_news/{team}/*.json"):
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if r.get("fetched") == ts and r.get("status") == "ok" and len(r.get("original_text") or "") >= 300:
            items.append(r)
    return items


def process_team(team, snap, ts, workers=8):
    """处理一队:并行 清洁+三判 每条新闻 → 追加 ⑦ → CHANGELOG。返回统计。"""
    sp = f"{RUNS}/team_data/{snap}/{team}/summary.md"
    if not os.path.exists(sp):
        return {"team": team, "skip": "无summary"}
    news = _new_news(team, ts)
    if not news:
        append_change(os.path.dirname(sp), snap, block_a=[], sources=[], note=f"{ts}轮:无新增新闻,summary未动")
        return {"team": team, "new": 0, "added": 0}
    summary = open(sp, encoding="utf-8").read()
    seg7 = _seg7(summary)
    titles = _repo_titles(team)

    def one(r):
        # 超长正文截断:judge_news 本就只用前 6000 字,clean_loop 对全文(如 NZL 11250 字)×3轮重写
        # 既浪费又拖到超时(thinking 模型输出慢)。截到 7000 字,既覆盖三判所需、又不被超长文卡死。
        body = (r.get("original_text") or "")[:7000]
        cl = clean_loop(body, "新闻正文")
        jd = judge_news(cl["text"], r.get("source", "?"), team, titles, seg7, r.get("published") or r.get("news_date", ""))
        return {"r": r, "clean": cl, "judge": jd}

    results = [None] * len(news)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut = {ex.submit(one, r): i for i, r in enumerate(news)}
        for f in as_completed(fut):
            try:
                results[fut[f]] = f.result()
            except Exception as e:
                results[fut[f]] = {"err": str(e)[:100]}

    lines, rejected = [], []
    for x in results:
        if not x or x.get("err"):
            continue
        j = x["judge"]
        if j.get("is_new") and j.get("should_add") and j.get("is_correct") and j.get("summary_line"):
            ln = j["summary_line"].strip()
            if ln and ln not in summary and ln not in lines:
                lines.append(ln)
        else:
            rejected.append(f"{x['r'].get('source')}:{j.get('reason','')[:30]}")

    merged = 0
    if lines:
        # 追加进 ⑦ 段末尾(段尾=下一个 ## 之前)
        m = re.search(r"(## ⑦[^\n]*\n)", summary)
        if m:
            insert = "".join(f"- {ln}\n" for ln in lines)
            start = m.end()
            nxt = summary.find("\n## ", start)
            pos = nxt if nxt >= 0 else len(summary)
            seg_old = summary[start:pos]
            seg_new = seg_old.rstrip() + "\n" + insert
            # ── 主题驱动去重合并(同主题≥2 或 >7条就合并,不再死等>10)——治放宽收录后同主题首发/赔率堆叠 ──
            bullets_n = seg_new.count("\n- ") + (1 if seg_new.lstrip().startswith("- ") else 0)
            go, _why = should_consolidate(seg_new)
            if go:
                try:
                    con = consolidate_seven(seg_new)
                    con_n = con.count("\n- ") + (1 if con.lstrip().startswith("- ") else 0)
                    # 安全闸:合并结果必须是非空 bullet 列表、且条数不增,才采用(否则保留追加版,不冒险丢信息)
                    if con and con_n >= 1 and con_n <= bullets_n and con.lstrip().startswith("- "):
                        merged = bullets_n - con_n
                        seg_new = "\n" + con + "\n"
                except Exception:
                    pass
            summary = summary[:start] + seg_new + summary[pos:]
            open(sp, "w", encoding="utf-8").write(summary)
    srcs = list({x["r"].get("source") for x in results if x and not x.get("err")})
    append_change(os.path.dirname(sp), snap,
                  block_a=[f"[⑦] +{len(lines)}条(py-Kimi三判): {ln[:40]}" for ln in lines] or [f"本轮{len(news)}篇新闻三判全未过(拒因示例:{rejected[:2]})"],
                  sources=srcs, note=f"{ts}轮 news_pipeline:新{len(news)}/进⑦{len(lines)}/拒{len(rejected)}" + (f"/合并-{merged}行" if merged else ""))
    return {"team": team, "new": len(news), "added": len(lines), "rejected": len(rejected), "merged": merged}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--ts", required=True)
    ap.add_argument("--teams", default="ALL", help="ALL 或 逗号分隔 FIFA 码")
    ap.add_argument("--team-workers", type=int, default=10, help="并行处理多少队")
    a = ap.parse_args()
    if a.teams == "ALL":
        teams = sorted(os.path.basename(d.rstrip("/")) for d in glob.glob(f"{RUNS}/team_data/{a.snapshot}/*/")
                       if re.match(r"^[A-Z]{3}$", os.path.basename(d.rstrip("/"))))
    else:
        teams = [t.strip() for t in a.teams.split(",")]
    print(f"▶ news_pipeline:{len(teams)} 队 · 快照 {a.snapshot} · ts {a.ts} · py-Kimi 三判并行")
    stats = [None] * len(teams)
    with ThreadPoolExecutor(max_workers=a.team_workers) as ex:
        fut = {ex.submit(process_team, t, a.snapshot, a.ts): i for i, t in enumerate(teams)}
        done = 0
        for f in as_completed(fut):
            stats[fut[f]] = f.result()
            done += 1
            s = stats[fut[f]]
            print(f"  [{done}/{len(teams)}] {s.get('team')}: 新{s.get('new','-')}/进⑦{s.get('added','-')}")
    tot_new = sum(s.get("new", 0) for s in stats if s)
    tot_add = sum(s.get("added", 0) for s in stats if s)
    print(f"✅ 完成:本轮新闻 {tot_new} 篇 → 进⑦ {tot_add} 条(其余三判未过/无新增)")


if __name__ == "__main__":
    main()
