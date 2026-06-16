#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【比赛日一键编排 · py 入口 = "跟进比赛"按钮】把全流程的 py 步骤串起来,带参数控制。
配 skill wc-matchday。**所有 LLM 判断/生成走 py 调 Kimi(wc_llm),换个对话也能复现。**

按钮参数(用户要求"按钮有参数,如是否推web"):
  --ts            本轮时分(默认当前);raw/快照/批次共用
  --snapshot      喂哪个快照预测(默认=team_data 最新)
  --settle A-B,.. 要结算的已完赛场次(填 results 由 --score 提供;或先手动填 results.json)
  --news          1=跑 news_pipeline(py-Kimi 三判,需先有本轮抓取的 raws)  0=跳过
  --coach         1=跑 coach_enrich(48队教练可读简介)  0=跳过
  --env  A-B,..   要刷新环境(天气/裁判)的场次
  --plong         1=为已收集 raws 的播报生成可预测版 long  0=跳过
  --predict A-B,. 要预测的场次(空=不预测)
  --audit         1=预测前跑 LLM 快照终审官(语义把关)  默认1
  --review        1=对已结算且有预测的场跑赛后复盘官  默认1
  --push-web      1=把预测+积分榜推到网页(并 git push)  0=只本地(默认0,推送是外发动作需显式开)
  --reveal 6.13   配 --push-web:解锁网页到某日

只跑 py 能跑的;**新闻 URL 发现/抓取**是检索步(WebSearch+collect_team_news,见 skill),本编排假定 raws 已就位。

例(全自动推网页):
  python3 matchday.py --ts 2026-06-13_1530 --snapshot 2026-06-13_1530 \
     --settle USA-PAR --news 1 --coach 1 --env QAT-SUI,BRA-MAR --plong 1 \
     --predict QAT-SUI,BRA-MAR,HAI-SCO,AUS-TUR --push-web 1 --reveal 6.13
例(只更新数据不推):  python3 matchday.py ... --predict "" --push-web 0
"""
import os, sys, json, argparse, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
BG = f"{HERE}/bg_collect"
PR = f"{HERE}/predict"


def run(cmd, cwd):
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=cwd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ts", default=datetime.datetime.now().strftime("%Y-%m-%d_%H%M"))
    ap.add_argument("--snapshot")
    ap.add_argument("--settle", default="")
    ap.add_argument("--news", type=int, default=1)
    ap.add_argument("--coach", type=int, default=0)
    ap.add_argument("--env", default="")
    ap.add_argument("--broadcast", default="", help="要合成赛事播报 ours 的场次 A-B,..(需先有 raws);可 --refresh 重跑")
    ap.add_argument("--plong", type=int, default=0)
    ap.add_argument("--predict", default="")
    ap.add_argument("--audit", type=int, default=1)
    ap.add_argument("--review", type=int, default=1)
    ap.add_argument("--push-web", dest="push", type=int, default=0)
    ap.add_argument("--reveal", default="")
    a = ap.parse_args()
    snap = a.snapshot
    print(f"=== 比赛日编排 ts={a.ts} snapshot={snap} ===")
    print(f"参数: settle={a.settle} news={a.news} coach={a.coach} env={a.env} plong={a.plong} "
          f"predict={a.predict} audit={a.audit} review={a.review} push_web={a.push}")

    # ② 环境(天气/裁判)刷新
    for pair in [p for p in a.env.split(",") if p.strip()]:
        h, w = pair.split("-")
        run(["python3", "collect_match_env.py", "--home", h, "--away", w, "--ts", a.ts, "--refresh"], BG)

    # ③ 教练可读简介(全48队,并行)
    if a.coach:
        run(["python3", "coach_enrich.py", "--ts", a.ts, "--teams", "ALL"], BG)

    # ④ 新闻三判 py 管道(假定 raws 已抓;无新增的队自动跳过=不动 summary)
    if a.news and snap:
        run(["python3", "news_pipeline.py", "--snapshot", snap, "--ts", a.ts, "--teams", "ALL"], BG)

    # ⑤ 赛事播报:已收集 raws 的场 → broadcast_synth(raws→ours,py-Kimi) → 可预测版 long
    #    raws 收集(找源 WebSearch + fetch_sources)是检索步(agent),见 wc-match-broadcast;此处合成 ours。
    #    可重复执行:赛后信息约 3h 才全,先跑一遍、信息更全后再 --refresh 跑一遍(幂等覆盖)。
    if a.broadcast.strip():
        for pair in a.broadcast.split(","):
            h, w = pair.strip().split("-")
            # 找该场 slug(date 从 matches.json)
            import json as _j
            mt = next((m for m in _j.load(open(f"{ROOT}/wc_runs/data_reference/matches.json", encoding="utf-8"))
                       if m.get("team_a") == h and m.get("team_b") == w), None)
            if mt:
                run(["python3", "broadcast_synth.py", "--slug", f"{mt['date']}_{h}_vs_{w}", "--refresh"], BG)
    if a.plong:
        run(["python3", "predictable_long_gen.py", "--all"], BG)

    # ⑥ 赛后复盘官(已结算且有预测的场)
    if a.review:
        run(["python3", "review_round.py"], PR)

    # ⑦ 预测(先新闻收集门禁 + 开球时间核对 + 体检 + 可选终审官)
    if a.predict.strip() and snap:
        ms = ",".join(p.strip().replace("-", "-") for p in a.predict.split(","))
        # ⑦.0a 新闻收集硬门禁:全48队、每队≥3源、**本轮都搜过**(--round 传本轮ts)+ 陈旧告警
        #       (news_preflight 是范围/源/新鲜度标准的唯一权威)不达标直接拒预测——
        #       "少收几队/源太少/本轮没搜"在代码层就过不了门,不靠自觉(防 downscale 蒙混、防假绿灯)
        if run(["python3", "news_preflight.py", "--round", a.ts], BG) != 0:
            sys.exit("✗ 新闻收集门禁未过(有队 <3 源/本轮没搜/不足48队),补齐后再预测")
        # ⑦.0b 开球时间核对:FIX(网页显示)↔ matches.json(预测prompt)一致 + 非ET场醒目标记
        #       (防"西部时区场把美东时间算错"再犯;硬不一致则拦,非ET场打印提示 agent 外部核对)
        if run(["python3", "verify_kickoffs.py", "--matches", ms], PR) != 0:
            sys.exit("✗ 开球时间核对未过(FIX↔matches 不一致/当地越界),修正后再来")
        pf = ["python3", "preflight.py", "--snapshot", snap, "--matches", ms]
        if a.audit:
            pf.append("--llm-audit")
        if run(pf, PR) != 0:
            sys.exit("✗ 体检/终审未过,停止(不带病预测)")
        for pair in a.predict.split(","):
            h, w = pair.strip().split("-")
            run(["python3", "predict_match.py", "--home", h, "--away", w,
                 "--snapshot", snap, "--run-ts", a.ts], PR)
        run(["python3", "merge_batch.py", a.ts], PR)
        run(["python3", "archive_pred.py", a.ts, "--daily"], PR)

    # ⑧ 推网页(外发动作,需显式 --push-web 1)
    if a.push:
        uw = ["python3", "update_web.py"]
        if a.reveal:
            uw += ["--reveal", a.reveal]
        run(uw, PR)
        print("\n⚠️ 网页数据已刷新;git 提交/推送请按 skill 手动确认(中性作者),或下一步执行。")
    print("\n=== 编排完成 ===")


if __name__ == "__main__":
    main()
