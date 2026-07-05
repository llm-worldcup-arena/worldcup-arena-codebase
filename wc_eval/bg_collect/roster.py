#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【队伍存活名单 · 单一真源】"有比赛的队伍" = 仍在赛的队。
新闻收集(collect_news_auto)与新闻门禁(news_preflight)共用本函数,范围随赛程自动收窄——
淘汰赛阶段不再一视同仁跑全 48 队,只跑仍存活的队;但仍是"存活队一个不少"的硬标准(不是随意抽样)。

存活定义(纯从产物文件算,可复现):
  存活 = R32 参赛的 32 队 − 淘汰赛中已被淘汰(输球/平局点球告负)的队。
  小组赛阶段(matches.json 尚无 r32 记录)→ 回退全 48 队(此阶段人人有比赛)。
"""
import os, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
KO_ROUNDS = ("r32", "r16", "qf", "sf", "final")


def _parse_score(score):
    m = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$", str(score or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def alive_teams(runs=RUNS):
    """返回仍存活队码的排序列表。淘汰赛按已结算赛果剔除败者;赛前回退全 48。"""
    matches = json.load(open(f"{runs}/data_reference/matches.json", encoding="utf-8"))
    results = json.load(open(f"{runs}/archive/results.json", encoding="utf-8")).get("matches", {})

    # R32 参赛队 = 淘汰赛全体候选(32 队);无 r32 记录 = 还没进淘汰赛 → 全 48
    participants = set()
    for m in matches:
        if m.get("round") == "r32":
            participants.add(m["team_a"]); participants.add(m["team_b"])
    if not participants:
        teams = json.load(open(f"{runs}/data_reference/teams.json", encoding="utf-8"))
        return sorted(t["team_id"] for t in teams)

    # 淘汰赛已结算场的败者 = 已淘汰(平局看 ko_winner 点球晋级)
    eliminated = set()
    for m in matches:
        if m.get("round") not in KO_ROUNDS:
            continue
        a, b = m["team_a"], m["team_b"]
        r = results.get(f"{a}_vs_{b}")
        if not r:
            continue
        sc = _parse_score(r.get("score"))
        if not sc:
            continue
        ha, hb = sc
        if ha > hb:
            eliminated.add(b)
        elif hb > ha:
            eliminated.add(a)
        else:  # 平局 → 点球定胜负,读 ko_winner
            kw = r.get("ko_winner")
            if kw == a:
                eliminated.add(b)
            elif kw == b:
                eliminated.add(a)
            # ko_winner 缺失 → 不敢猜,两队都暂留存活(宁多勿漏)
    return sorted(participants - eliminated)


if __name__ == "__main__":
    al = alive_teams()
    print(f"存活 {len(al)} 队: {' '.join(al)}")
