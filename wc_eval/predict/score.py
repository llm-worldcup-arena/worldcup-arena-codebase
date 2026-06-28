#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""算分模型:预测档案 vs 现实档案 → 积分榜。
读 archive/predictions.json(预测)+ archive/results.json(真实赛果),对照打分,输出 archive/scorecard.json。
网页积分榜由 scorecard.json 来。赛果填多少算多少(没填的项不计),随赛程可多次重算。

跑:python3 score.py
"""
import json, os, re
from common import match_handicap


def _norm(v):
    """规范化预测值:去掉模型偶尔抄进来的括号提示(如"双（全场总进球数）"→"双")与空白,再与真值精确比对。
    否则前端(会解析提取)与本脚本(精确匹配)会差几分——曾因此 GPT 前端20/后端19 不一致。"""
    if not isinstance(v, str):
        return v
    return re.sub(r"[（(].*?[)）]", "", v).strip()

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根(可移植,不再硬编码)
ARC = f"{ROOT}/wc_runs/archive"

# 单场 7 市场权重(2026-06 调:看着难的其实多是猜,权重压平)+ 头名 + 全局各项:
SC = {"让球": 4, "半全场": 3, "胜平负": 2, "大小2.5": 2, "双方进球": 2, "正确比分": 2, "单双": 1,
      "头名": 5, "夺冠": 25, "进决赛": 10, "四强": 4, "夺冠大洲": 5, "总进球285.5": 4}   # 全局对齐前端 GLOBAL


def derive(score, ht=None, line=None):
    """从真实比分推各市场真值。score '3-1';ht 半场 '1-0';line 让球盘口(主队让球,负=主让)。"""
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
    if line is not None:                                   # 让球盘:全场净胜 + 盘口
        m = (h - a) + line
        r["让球"] = "主胜盘" if m > 1e-6 else ("客胜盘" if m < -1e-6 else "走盘")
    return r


def main():
    pred = json.load(open(f"{ARC}/predictions.json", encoding="utf-8"))["models"]
    res = json.load(open(f"{ARC}/results.json", encoding="utf-8"))
    rm, rg, rgl = res.get("matches", {}), res.get("group_winners", {}), res.get("global", {})

    card = {}
    for name, md in pred.items():
        s, d = 0, {"单场": 0, "头名": 0, "全局": 0}
        for mk, markets in (md.get("matches") or {}).items():                 # 单场
            ha = mk.split("_vs_"); line = match_handicap(ha[0], ha[1]) if len(ha) == 2 else None
            truth = derive((rm.get(mk) or {}).get("score"), (rm.get(mk) or {}).get("ht"), line)
            for mkt in ["让球", "胜平负", "大小2.5", "双方进球", "单双", "半全场", "正确比分"]:
                if truth.get(mkt) and _norm((markets or {}).get(mkt)) == truth[mkt]:   # 规范化后比对(与前端一致)
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
    out = {"_说明": "算分:预测档案 vs 现实档案。分值见 score.py 的 SC(让球用固定盘口结算)。",
           "排名": [{"模型": n, **dd} for n, dd in rank]}
    json.dump(out, open(f"{ARC}/scorecard.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("✅ 积分榜 → archive/scorecard.json")
    for i, (n, dd) in enumerate(rank, 1):
        print(f"  {i}. {n}: {dd['总分']} 分（单场{dd['单场']} / 头名{dd['头名']} / 全局{dd['全局']}）")


if __name__ == "__main__":
    main()
