#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单场 7 市场预测:喂比赛抬头 + 对阵 2 队完整 summary → 6 模型各预测 7 个市场。
🚨 真正跑前必须先向用户汇报(skill wc-predict / 记忆 feedback-eval-report-first)。不评分。
   跑时自动把实际 prompt 留存到 predictions/<批次>/_prompts/。

跑:python3 predict_match.py --home MEX --away RSA --snapshot 2026-06-10_1310
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from common import (load_models, read_summary, ask_json, save_pred, save_prompt, run_ts,
                    match_header, handicap_clause, coach_brief_text)

SYS = ("你是资深足球分析师。下面两队的赛前资料供你参考,你可结合自己掌握的球队/球员信息与判断"
       "来预测,不必局限于给定资料。请先一步步、认真推演分析(逐条权衡、不要急于下结论、不要凭直觉猜),"
       "再在最后输出 JSON(全文只这一个 JSON)。")


def build_user(home, away, sh):
    hc = handicap_clause(home, away)
    hc_block = f"\n【让球盘口 · 固定】{hc}（博彩让球线，仅用于判定下方「让球」一项；其余六项请基于两队赛前资料独立判断，不必与盘口一致）\n" if hc else ""
    hc_text = coach_brief_text(home)
    ac_text = coach_brief_text(away)
    h_coach = f"\n\n**主帅简介**\n{hc_text}" if hc_text else ""
    a_coach = f"\n\n**主帅简介**\n{ac_text}" if ac_text else ""
    return f"""【本场比赛】
{match_header(home, away)}
{hc_block}
【主队 {home} · 赛前资料】
{read_summary(home, sh)}{h_coach}

【客队 {away} · 赛前资料】
{read_summary(away, sh)}{a_coach}

预测本场 {home}(主) vs {away}(客) 的 7 个市场。
**先做全面、认真的逐项推演分析(务必逐条权衡、不要走过场、不要急于下结论,推理清楚再定)**——双方攻防实力 / 近期状态与士气 / 伤停与停赛 / 关键对位 / 战术风格相克 / 主客场与环境(天气·海拔·开球时间) / 历史交锋 / 大赛心理与动机 **等各方面,不限于此**,凡你认为影响赛果的因素都可纳入;**然后在最后输出 JSON**(全文只这一个 JSON,每项必须从给定选项里选)。
⚠️ **七项必须内部一致、与你给的「正确比分」完全自洽,绝不能自相矛盾**;**输出 JSON 前,自己逐项核对、检查一遍**(把七项跟比分一一对照,发现矛盾先改再输出):
 · 总进球数 = 两队进球之和 → 决定「大小2.5」(≥3 为大、≤2 为小)和「单双」(奇/偶,0 算双);
 · 「双方进球」看比分里两队是否都 ≥1 球;「胜平负」与「半全场的后段(全场)」必须与比分一致;
 · 「让球」按上方固定盘口、用净胜球判定,要与比分方向一致。
矛盾案例(以下都不允许出现):
 · 比分 2-1 却填「小」—— 2-1 总 3 球是大;正确应为:大、单、双方进球=是、主胜。
 · 比分 0-0 却填「双方进球=是」或「单」—— 0-0 应为:否、双(0 算双)、平,且半全场只能是 平-平。
 · 比分 1-1 却填「主胜」—— 1-1 是平;若主队让 0.5 球,让球应为「客胜盘」。
 · 半全场填「主-主」却给比分 0-2 —— 半全场后段(全场)与比分的胜负必须一致。
 · 比分 4-0 —— 总 4 球是大、双;客队 0 球故「双方进球=否」;主胜;半全场后段只能「主」。
⚠️ **每项的 JSON 值只填【选项本身】,引号外括号里的是说明、绝不要抄进值里**(例:`"单双": "单"`,不要写成 `"单双": "单（全场总进球数）"`)。
{{
  "胜平负": "主胜 / 平 / 客胜",
  "让球": "主胜盘 / 走盘 / 客胜盘",
  "大小2.5": "大 / 小",
  "双方进球": "是 / 否",
  "单双": "单 / 双",
  "半全场": "主-主 / 主-平 / 主-客 / 平-主 / 平-平 / 平-客 / 客-主 / 客-平 / 客-客",
  "正确比分": "X-Y（X=主队进球数、Y=客队进球数，均为整数，用短横线连接）"
}}
（各项说明:胜平负=三选一;让球=在上方固定盘口下判定,半球盘无走盘、只能选 主胜盘/客胜盘;大小2.5/双方进球=二选一;单双=全场总进球数的奇偶,0 算双;半全场=共 9 种选一;正确比分=X-Y 格式(X=主队进球数、Y=客队进球数,整数,短横线连接)。）"""


def predict_one(model_id, home, away, sh):
    return ask_json(model_id, SYS, build_user(home, away, sh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True, help="主队 FIFA 码")
    ap.add_argument("--away", required=True, help="客队 FIFA 码")
    ap.add_argument("--snapshot", required=True, help="喂哪个干净快照,如 2026-06-10_1310")
    ap.add_argument("--only", help="只跑某模型(显示名,如 Seed),测试用")
    ap.add_argument("--run-ts", dest="run_ts", help="批次目录(日期_时分),默认当前时间")
    a = ap.parse_args()
    models = [m for m in load_models() if not a.only or m["name"].lower() == a.only.lower()]
    bt = run_ts(a.run_ts)   # 经 run_ts 校验格式,非规范名直接报错
    kind = f"match_{a.home}_vs_{a.away}"
    print(f"⚠️ 单场预测 {a.home} vs {a.away}(快照 {a.snapshot}）· {len(models)} 模型 · 批次 {bt} —— 真正跑前应已向用户汇报")
    save_prompt(bt, kind, SYS, build_user(a.home, a.away, a.snapshot))        # 留存实际 prompt
    out = {}
    def _run(m):
        return m["name"], predict_one(m["id"], a.home, a.away, a.snapshot)
    with ThreadPoolExecutor(max_workers=6) as ex:
        for name, res in ex.map(_run, models):
            out[name] = res
            print(f"  ✓ {name}: {res['_json'].get('胜平负') if res and '_json' in res else '失败'}")
    meta = (f"# 预测批次 {bt}\n- 类型:单场 {a.home} vs {a.away}\n- 喂快照:{a.snapshot}\n"
            f"- 模型:{[m['name'] for m in models]}\n- 防泄露:喂赛前快照、不含本场结果\n")
    save_pred(kind, bt, out, meta)


if __name__ == "__main__":
    main()
