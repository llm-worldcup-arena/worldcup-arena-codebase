#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【赛后复盘官】每场结算后,用 py 调 Kimi 自动写"6 模型谁对谁错、错在哪类市场"的误差分析,
滚动存进 archive/reviews.json —— 既是监督,也是论文分析章节的素材。

数据来源:archive/predictions.json(预测)× archive/results.json(真值,score.py 同款推导各市场)。
对每个【已结算且有预测】的场次:postmatch_review(真值, 6模型预测) → per_market/model_notes/collective/paper_point。
并行跑多场;已复盘过的场默认跳过(--refresh 重做)。

跑:python3 review_round.py            # 复盘所有已结算且有预测、尚未复盘的场
   python3 review_round.py --refresh  # 全部重做
"""
import os, sys, json, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARC = f"{ROOT}/wc_runs/archive"
sys.path.insert(0, f"{ROOT}/wc_eval")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wc_llm import postmatch_review
from score import derive, match_handicap     # 真值推导 + 让球结算,与算分同源


def _actual(key, rec):
    """从赛果推 7 市场真值(score.py.derive,让球用固定盘口结算,与算分完全同源)。"""
    home, away = key.split("_vs_")
    line = match_handicap(home, away)
    d = derive(rec.get("score"), rec.get("ht"), line)
    d["score"] = rec.get("score"); d["ht"] = rec.get("ht")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    preds = json.load(open(f"{ARC}/predictions.json", encoding="utf-8"))
    results = json.load(open(f"{ARC}/results.json", encoding="utf-8"))["matches"]
    reviews = json.load(open(f"{ARC}/reviews.json", encoding="utf-8")) if os.path.exists(f"{ARC}/reviews.json") else {}

    # 收集每场 6 模型预测(predictions.json 按模型组织 → 转成按场)
    by_match = {}
    for model, mp in preds.get("models", {}).items():
        for key, mk in (mp.get("matches") or {}).items():
            by_match.setdefault(key, {})[model] = mk

    todo = [k for k in results if k in by_match and results[k].get("score") and (a.refresh or k not in reviews)]
    if not todo:
        print("✓ 没有需要复盘的新场次"); return
    print(f"▶ 赛后复盘官:{len(todo)} 场 · py-Kimi 并行")

    def one(key):
        home, away = key.split("_vs_")
        return key, postmatch_review(home, away, _actual(key, results[key]), by_match[key])

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(one, k) for k in todo]):
            try:
                key, rev = f.result()
                reviews[key] = rev
                print(f"  ✓ {key}: {rev.get('paper_point','')[:70]}")
            except Exception as e:
                print(f"  ✗ {str(e)[:80]}")
    json.dump(reviews, open(f"{ARC}/reviews.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 复盘 → archive/reviews.json（累计 {len(reviews)} 场）")


if __name__ == "__main__":
    main()
