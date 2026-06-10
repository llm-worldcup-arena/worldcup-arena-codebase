#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""算分模型:预测档案 vs 现实档案 → 积分榜。
读 archive/predictions.json(预测)+ archive/results.json(真实赛果),对照打分,输出 archive/scorecard.json。
网页积分榜由 scorecard.json 来。赛果填多少算多少(没填的项不计),随赛程可多次重算。

跑:python3 score.py
"""
import json

ROOT = "/home/ubuntu/worldcup_2026"
ARC = f"{ROOT}/wc_runs/archive"

# 分值(可调)。让球盘需盘口结算、暂不计;其余 6 个单场市场 + 头名 + 全局各项:
SC = {"胜平负": 1, "大小2.5": 1, "双方进球": 1, "单双": 1, "半全场": 2, "正确比分": 3,
      "头名": 3, "夺冠": 10, "进决赛": 3, "四强": 2, "夺冠大洲": 2, "总进球285.5": 2}


def derive(score, ht=None):
    """从真实比分推算各市场真值。score 如 '3-1';ht 半场比分 '1-0'(可选,用于半全场)。"""
    if not score or "-" not in str(score):
        return {}
    h, a = map(int, str(score).split("-")); tot = h + a
    r = {"胜平负": "主胜" if h > a else ("客胜" if a > h else "平"),
         "大小2.5": "大" if tot > 2.5 else "小",
         "双方进球": "是" if (h > 0 and a > 0) else "否",
         "单双": "单" if tot % 2 else "双",
         "正确比分": f"{h}-{a}"}
    if ht and "-" in str(ht):
        hh, ha = map(int, str(ht).split("-")); seg = lambda x, y: "主" if x > y else ("客" if y > x else "平")
        r["半全场"] = f"{seg(hh, ha)}-{seg(h, a)}"
    return r


def main():
    pred = json.load(open(f"{ARC}/predictions.json", encoding="utf-8"))["models"]
    res = json.load(open(f"{ARC}/results.json", encoding="utf-8"))
    rm, rg, rgl = res.get("matches", {}), res.get("group_winners", {}), res.get("global", {})

    card = {}
    for name, md in pred.items():
        s, d = 0, {"单场": 0, "头名": 0, "全局": 0}
        for mk, markets in (md.get("matches") or {}).items():                 # 单场
            truth = derive((rm.get(mk) or {}).get("score"), (rm.get(mk) or {}).get("ht"))
            for mkt in ["胜平负", "大小2.5", "双方进球", "单双", "半全场", "正确比分"]:
                if truth.get(mkt) and (markets or {}).get(mkt) == truth[mkt]:
                    s += SC[mkt]; d["单场"] += SC[mkt]
        for g, gw in (md.get("group_winners") or {}).items():                 # 头名
            pick = gw.get("头名") if isinstance(gw, dict) else gw
            if rg.get(g) and pick == rg[g]:
                s += SC["头名"]; d["头名"] += SC["头名"]
        gp = md.get("global_pool") or {}                                      # 全局
        if rgl.get("夺冠") and gp.get("夺冠") == rgl["夺冠"]: s += SC["夺冠"]; d["全局"] += SC["夺冠"]
        for q in (gp.get("进决赛") or []):
            if q in (rgl.get("进决赛") or []): s += SC["进决赛"]; d["全局"] += SC["进决赛"]
        for q in (gp.get("四强") or []):
            if q in (rgl.get("四强") or []): s += SC["四强"]; d["全局"] += SC["四强"]
        if rgl.get("夺冠大洲") and gp.get("夺冠大洲") == rgl["夺冠大洲"]: s += SC["夺冠大洲"]; d["全局"] += SC["夺冠大洲"]
        if rgl.get("总进球285.5") and gp.get("总进球285.5") == rgl["总进球285.5"]: s += SC["总进球285.5"]; d["全局"] += SC["总进球285.5"]
        card[name] = {"总分": s, **d}

    rank = sorted(card.items(), key=lambda x: -x[1]["总分"])
    out = {"_说明": "算分:预测档案 vs 现实档案。分值见 score.py 的 SC(让球盘暂不计)。",
           "排名": [{"模型": n, **dd} for n, dd in rank]}
    json.dump(out, open(f"{ARC}/scorecard.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("✅ 积分榜 → archive/scorecard.json")
    for i, (n, dd) in enumerate(rank, 1):
        print(f"  {i}. {n}: {dd['总分']} 分（单场{dd['单场']} / 头名{dd['头名']} / 全局{dd['全局']}）")


if __name__ == "__main__":
    main()
