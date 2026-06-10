#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一个预测批次的所有文件(单场/头名/全局)合成一个【统一 JSON】(按模型组织),存 _unified.json。
保留此设计:以后每批次跑完都生成统一结果,便于人看 + 评分对照。

跑:python3 merge_batch.py 2026-06-10_1437
"""
import os, sys, json, glob

ROOT = "/home/ubuntu/worldcup_2026"


def merge_batch(batch_ts):
    d = f"{ROOT}/wc_runs/predictions/{batch_ts}"
    uni = {"batch": batch_ts, "models": {}}

    def mj(p):
        return p.get("_json") if isinstance(p, dict) and "_json" in p else None

    for f in sorted(glob.glob(f"{d}/match_*.json")):          # 单场
        name = os.path.basename(f)[6:-5]
        for model, p in json.load(open(f, encoding="utf-8")).items():
            uni["models"].setdefault(model, {}).setdefault("matches", {})[name] = mj(p)
    if os.path.exists(f"{d}/group_winners.json"):             # 头名
        for model, gs in json.load(open(f"{d}/group_winners.json", encoding="utf-8")).items():
            uni["models"].setdefault(model, {})["group_winners"] = {g: mj(p) for g, p in gs.items()}
    if os.path.exists(f"{d}/global_pool.json"):               # 全局彩池
        for model, p in json.load(open(f"{d}/global_pool.json", encoding="utf-8")).items():
            uni["models"].setdefault(model, {})["global_pool"] = mj(p)

    out = f"{d}/_unified.json"
    json.dump(uni, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(len(m.get("matches", {})) * 7 + len(m.get("group_winners", {})) + (9 if m.get("global_pool") else 0)
            for m in uni["models"].values())
    print(f"✅ 统一 → predictions/{batch_ts}/_unified.json（{len(uni['models'])} 模型, {n} 条）")
    return uni


if __name__ == "__main__":
    merge_batch(sys.argv[1])
