#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小组头名预测:每组喂该组 4 队完整 summary → 6 模型各押头名。12 组各跑 1 次(或 --group A 单组)。
🚨 真正跑前必须先向用户汇报。不评分。

跑:python3 predict_group.py --snapshot 2026-06-10_1310 [--group A]
"""
import argparse
from common import load_models, read_summary, load_groups, ask_json, save_pred, run_ts

SYS = ("你是资深足球分析师。下面同组各队的赛前资料供你参考,你可结合自己的判断与掌握的信息"
       "预测该组小组赛【头名(第 1 名)】,不必局限于给定资料。先简要分析,再在最后输出 JSON(全文只这一个 JSON)。")


def predict_group(model_id, grp, teams, sh):
    blocks = "\n\n".join(f"【{t}】\n{read_summary(t, sh)}" for t in teams)
    user = f"""{grp} 组共 {len(teams)} 队,各队赛前资料如下:

{blocks}

预测 {grp} 组小组赛【头名(第 1 名)】是哪支队。
**先简要分析**(各队实力/状态对比,3-5 句),**然后在最后输出 JSON**(全文只这一个):
{{"头名": "FIFA三字码(必须是本组 {'/'.join(teams)} 之一)", "理由": "一句话"}}"""
    return ask_json(model_id, SYS, user)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True, help="喂哪个干净快照")
    ap.add_argument("--group", help="只跑某组(如 A),默认全部 12 组")
    ap.add_argument("--only", help="只跑某模型,测试用")
    ap.add_argument("--run-ts", dest="run_ts", help="批次目录(日期_时分),默认当前")
    a = ap.parse_args()
    groups = load_groups()
    if not groups:
        raise SystemExit("✗ 没读到分组(bg/static/groups.json)")
    if a.group:
        groups = {a.group: groups[a.group]}
    models = [m for m in load_models() if not a.only or m["name"].lower() == a.only.lower()]
    bt = a.run_ts or run_ts()
    print(f"⚠️ 小组头名预测 {len(groups)} 组 · {len(models)} 模型 · 批次 {bt}(快照 {a.snapshot}）")
    from concurrent.futures import ThreadPoolExecutor
    out = {m["name"]: {} for m in models}
    tasks = [(m, grp, teams) for m in models for grp, teams in groups.items()]
    def _run(t):
        m, grp, teams = t
        return m["name"], grp, predict_group(m["id"], grp, teams, a.snapshot)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for name, grp, res in ex.map(_run, tasks):
            out[name][grp] = res
            print(f"  ✓ {name} · {grp}: {res['_json'].get('头名') if res and '_json' in res else '失败'}")
    meta = (f"# 预测批次 {bt}\n- 类型:小组头名 {len(groups)} 组\n- 喂快照:{a.snapshot}\n"
            f"- 模型:{[m['name'] for m in models]}\n")
    save_pred("group_winners", bt, out, meta)


if __name__ == "__main__":
    main()
