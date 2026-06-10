#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评分:赛后用真实赛果对照预测,按分值结算 → 积分榜。
赛果(GT)从 wc_runs/predictions/<snapshot>/results.json 读(赛后手填或采集)。赛果未出时只报"待赛果"。

分值表 SCORE:全局彩池为前端已知值;单场/头名为占位【待按前端结算规则确认】。
跑:python3 score.py --snapshot 2026-06-10_1310
"""
import os, json, argparse

ROOT = "/home/ubuntu/worldcup_2026"

# ── 分值表 ──（彩池=前端已知；单场/头名=占位,待用户按前端填）
SCORE = {
    # 全局彩池(已知)
    "夺冠": 10, "进决赛": 3, "四强": 2, "夺冠大洲": 2, "总进球": 2,
    # 小组头名(占位·待定)
    "小组头名": 2,
    # 单场 7 市场(占位·待定)
    "胜平负": 1, "让球": 1, "大小2.5": 1, "双方进球": 1, "单双": 1, "半全场": 1, "正确比分": 3,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    a = ap.parse_args()
    pdir = f"{ROOT}/wc_runs/predictions/{a.snapshot}"
    gt_path = f"{pdir}/results.json"

    if not os.path.exists(pdir):
        print(f"✗ 没有预测目录:{pdir}（先跑 predict_*）"); return
    preds = [f for f in os.listdir(pdir) if f.endswith(".json") and f != "results.json"]
    print(f"预测文件:{preds}")

    if not os.path.exists(gt_path):
        print(f"\n⏳ 赛果未出:{gt_path} 不存在。")
        print("   框架就绪 —— 赛后把真实赛果填进 results.json,本脚本即按 SCORE 对照预测、累加成积分榜。")
        print(f"   分值表(单场/头名为占位,待你按前端确认):{SCORE}")
        return

    # ── 赛后:对照打分（赛果 JSON 格式确定后补全这段）──
    print("赛果已存在 —— 对照打分逻辑待 results.json 格式定稿后补全(读预测×赛果→按SCORE累加→积分榜)。")


if __name__ == "__main__":
    main()
