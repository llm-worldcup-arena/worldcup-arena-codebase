#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单场 7 市场预测:喂对阵 2 队完整 summary → 6 模型各预测 7 个市场。
🚨 真正跑前必须先向用户汇报(skill wc-predict / 记忆 feedback-eval-report-first)。本脚本不评分(赛果未出)。

跑:python3 predict_match.py --home MEX --away RSA --snapshot 2026-06-10_1310
"""
import argparse
from common import load_models, read_summary, ask_json, save_pred, run_ts, match_header

SYS = ("你是资深足球分析师。下面两队的赛前资料供你参考,你可结合自己掌握的球队/球员信息与判断"
       "来预测,不必局限于给定资料。先给一点简要分析,再在最后输出 JSON(全文只这一个 JSON)。")


def predict_one(model_id, home, away, sh):
    user = f"""【本场比赛】
{match_header(home, away)}

【主队 {home} · 赛前资料】
{read_summary(home, sh)}

【客队 {away} · 赛前资料】
{read_summary(away, sh)}

预测本场 {home}(主) vs {away}(客) 的 7 个市场。
**先简要分析**(双方攻防实力 / 近期状态 / 伤停 / 关键对位,3-5 句),**然后在最后输出 JSON**(全文只这一个 JSON,每项必须从给定选项里选):
{{
  "胜平负": "主胜 / 平 / 客胜",
  "让球": "主-2 / 主-1.5 / 主-1 / 主-0.5 / 平手 / 客-0.5 / 客-1 / 客-1.5 / 客-2（强队让几球,从中选一）",
  "大小2.5": "大 / 小",
  "双方进球": "是 / 否",
  "单双": "单 / 双（全场总进球数）",
  "半全场": "主-主 / 主-平 / 主-客 / 平-主 / 平-平 / 平-客 / 客-主 / 客-平 / 客-客（共9种,选一）",
  "正确比分": "给最可能的比分,如 2-1 / 1-0 / 0-0 / 2-2"
}}"""
    return ask_json(model_id, SYS, user)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True, help="主队 FIFA 码")
    ap.add_argument("--away", required=True, help="客队 FIFA 码")
    ap.add_argument("--snapshot", required=True, help="喂哪个干净快照,如 2026-06-10_1310")
    ap.add_argument("--only", help="只跑某模型(显示名,如 Seed),测试用")
    ap.add_argument("--run-ts", dest="run_ts", help="批次目录(日期_时分),默认当前时间")
    a = ap.parse_args()
    models = [m for m in load_models() if not a.only or m["name"].lower() == a.only.lower()]
    bt = a.run_ts or run_ts()
    print(f"⚠️ 单场预测 {a.home} vs {a.away}(快照 {a.snapshot}）· {len(models)} 模型 · 批次 {bt} —— 真正跑前应已向用户汇报")
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    def _run(m):
        return m["name"], predict_one(m["id"], a.home, a.away, a.snapshot)
    with ThreadPoolExecutor(max_workers=6) as ex:
        for name, res in ex.map(_run, models):
            out[name] = res
            print(f"  ✓ {name}: {res['_json'].get('胜平负') if res and '_json' in res else '失败'}")
    meta = (f"# 预测批次 {bt}\n- 类型:单场 {a.home} vs {a.away}\n- 喂快照:{a.snapshot}\n"
            f"- 模型:{[m['name'] for m in models]}\n- 防泄露:喂赛前快照、不含本场结果\n")
    save_pred(f"match_{a.home}_vs_{a.away}", bt, out, meta)


if __name__ == "__main__":
    main()
