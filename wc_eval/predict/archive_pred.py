#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把某次预测批次【固定写入】预测档案 wc_runs/archive/predictions.json(累加,不覆盖旧场)。
预测档案 = 官方固定预测的唯一真源;网页数据(update_web.py)+ 算分(score.py)都从它来。

  --full  赛前全量:写入 global_pool + group_winners,并累加 matches(揭幕场)。整届跑一次。
  --daily 逐日单场:只把该批次的 matches 累加进档案(global/group/旧 matches 原样保留)。

跑:python3 archive_pred.py 2026-06-11_0057 --full
   python3 archive_pred.py 2026-06-12_xxxx --daily
"""
import json, os, sys, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根(可移植,不再硬编码)
ARC = f"{ROOT}/wc_runs/archive"
PRED = f"{ARC}/predictions.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", help="批次,如 2026-06-11_0057")
    ap.add_argument("--full", action="store_true", help="赛前全量:写 global+group + 累加 matches")
    ap.add_argument("--daily", action="store_true", help="逐日单场:只累加 matches")
    a = ap.parse_args()
    if not (a.full or a.daily):
        sys.exit("✗ 必须指定 --full(赛前全量)或 --daily(逐日单场)")

    uni = json.load(open(f"{ROOT}/wc_runs/predictions/{a.batch}/_unified.json", encoding="utf-8"))
    new = uni["models"]

    os.makedirs(ARC, exist_ok=True)
    if os.path.exists(PRED):
        arc = json.load(open(PRED, encoding="utf-8"))
    else:
        arc = {"_说明": "官方预测档案:每个预测点固定后累加写入(只增不覆盖旧场)。网页数据 + 算分的唯一真源。",
               "_固定记录": [], "models": {}}

    for name, md in new.items():
        slot = arc["models"].setdefault(name, {"matches": {}, "group_winners": {}, "global_pool": {}})
        if a.full:                                              # 赛前:global+group 一次性固定
            slot["global_pool"] = md.get("global_pool", {})
            slot["group_winners"] = md.get("group_winners", {})
        slot.setdefault("matches", {}).update(md.get("matches", {}))   # matches 始终累加(新场 merge、旧场留)

    sample_matches = list(next(iter(new.values()), {}).get("matches", {}).keys())
    rec = {"批次": a.batch, "模式": "full" if a.full else "daily", "本次场次": sample_matches}
    records, replaced = [], False
    for old in arc.get("_固定记录", []):
        if old.get("批次") == a.batch and old.get("模式") == rec["模式"]:
            if not replaced:
                records.append(rec)
                replaced = True
            continue
        records.append(old)
    if not replaced:
        records.append(rec)
    arc["_固定记录"] = records
    json.dump(arc, open(PRED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    any_model = next(iter(arc["models"].values()), {})
    print(f"✅ 写入预测档案 archive/predictions.json({'赛前全量' if a.full else '逐日累加'})")
    print(f"   批次 {a.batch} · 本次场次 {sample_matches}")
    print(f"   档案现状:matches {len(any_model.get('matches', {}))} 场/模型 · "
          f"group/global {'已固定' if any_model.get('global_pool') else '未写'} · {len(arc['models'])} 模型")


if __name__ == "__main__":
    main()
