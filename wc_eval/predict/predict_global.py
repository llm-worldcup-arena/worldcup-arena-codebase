#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全局彩池预测(夺冠 / 进决赛2 / 四强4 / 夺冠大洲 / 总进球大小 285.5)。
喂法:48 队「速览」(extract_brief 默认:速览+⑦动态+⑧定位+市值,去掉 ⑤阵容5000字细节),一次喂全 → 全局视野。
🚨 真正跑前必须先向用户汇报(skill wc-predict)。

跑:python3 predict_global.py --snapshot 2026-06-10_1310 --run-ts 2026-06-10_1437 [--only Seed]
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from common import load_models, load_groups, read_summary, extract_brief, ask_json, save_pred, run_ts

SYS = ("你是资深足球分析师。下面 48 队的赛前简况供你参考,你可结合自己掌握的信息与判断预测本届世界杯整体走向,"
       "不必局限于给定资料。先简要分析夺冠梯队,再在最后输出 JSON(全文只这一个 JSON)。")


def build_context(snapshot):
    groups = load_groups()
    teams = sorted({t for ts in groups.values() for t in ts})
    parts = [f"【{t}】\n{extract_brief(read_summary(t, snapshot))}" for t in teams]
    return "\n\n".join(parts), teams


def predict_one(model_id, ctx):
    user = f"""以下是本届世界杯全部 48 队的赛前简况(实力/近期状态/伤停/身价):

{ctx}

预测本届走向。**先简要分析**夺冠热门梯队(3-6 句),**然后在最后输出 JSON**(全文只这一个,队用 FIFA 三字码):
{{
  "夺冠": "三字码",
  "进决赛": ["三字码", "三字码"],
  "四强": ["三字码", "三字码", "三字码", "三字码"],
  "夺冠大洲": "欧洲 / 南美 / 北美 / 非洲 / 亚洲",
  "总进球285.5": "大 / 小"
}}"""
    return ask_json(model_id, SYS, user)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--only", help="只跑某模型,测试用")
    ap.add_argument("--run-ts", dest="run_ts", help="批次目录,默认当前")
    a = ap.parse_args()
    models = [m for m in load_models() if not a.only or m["name"].lower() == a.only.lower()]
    bt = a.run_ts or run_ts()
    ctx, teams = build_context(a.snapshot)
    print(f"⚠️ 全局彩池 · {len(models)} 模型 · 批次 {bt} · 喂 {len(teams)} 队速览({len(ctx)} 字)")
    out = {}
    def _run(m):
        return m["name"], predict_one(m["id"], ctx)
    with ThreadPoolExecutor(max_workers=6) as ex:
        for name, res in ex.map(_run, models):
            out[name] = res
            print(f"  ✓ {name}: 夺冠 {res['_json'].get('夺冠') if res and '_json' in res else '失败'}")
    meta = (f"# 预测批次 {bt}\n- 类型:全局彩池(夺冠/进决赛/四强/夺冠大洲/总进球)\n"
            f"- 喂快照:{a.snapshot}(48 队速览,extract_brief)\n- 模型:{[m['name'] for m in models]}\n")
    save_pred("global_pool", bt, out, meta)


if __name__ == "__main__":
    main()
