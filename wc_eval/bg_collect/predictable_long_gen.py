#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【可预测版 long 生成】把 match_broadcast 子项目的 ours/long.md 用 py 调 Kimi 改写成
ours/long_predictable.md —— 信息全留(硬信息清楚陈述),情感/抒情高度概括精简。

设计(用户原话):long 再进一步变成"可预测版 long",起之前 long 的作用(几乎直接放 summary 后面/块B)。
原 long.md 保留(原始播报);long_predictable.md 是叠加的可预测层。生成自带质检(clean_loop)。
块B(wc2026_build._long_excerpt)优先读 long_predictable.md,没有再退回 long.md。

并行跑多场。已生成且 long.md 未更新过的默认跳过(--refresh 重做)。

跑:python3 predictable_long_gen.py --all
   python3 predictable_long_gen.py --slug 2026-06-11_MEX_vs_RSA
"""
import os, sys, json, glob, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
MB = f"{RUNS}/data_processed/match_broadcast"
sys.path.insert(0, f"{ROOT}/wc_eval")
from wc_llm import predictable_long


def gen(slug, refresh=False):
    d = f"{MB}/{slug}"
    lp = f"{d}/ours/long.md"
    out = f"{d}/ours/long_predictable.md"
    if not os.path.exists(lp):
        return {"slug": slug, "skip": "无long.md"}
    if os.path.exists(out) and not refresh and os.path.getmtime(out) >= os.path.getmtime(lp):
        return {"slug": slug, "skip": "已最新"}
    res = predictable_long(open(lp, encoding="utf-8").read())
    body = ("<!-- 可预测版 long:py-Kimi 从 long.md 改写(硬信息全留、情感高度概括);块B 优先取此版。原 long.md 保留为原始播报。-->\n\n"
            + res["plong"])
    open(out, "w", encoding="utf-8").write(body)
    return {"slug": slug, "ok": True, "chars": len(res["plong"]), "qc_pass": not res["qc"].get("need_fix")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--slug")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    slugs = [os.path.basename(d.rstrip("/")) for d in glob.glob(f"{MB}/*/") if os.path.isdir(d)] if a.all \
        else [a.slug] if a.slug else []
    if not slugs:
        raise SystemExit("✗ 用 --all 或 --slug <场次>")
    print(f"▶ 可预测版 long:{len(slugs)} 场 · py-Kimi 并行")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(gen, s, a.refresh) for s in slugs]):
            print(f"  {f.result()}")
    print("✅ done")


if __name__ == "__main__":
    main()
