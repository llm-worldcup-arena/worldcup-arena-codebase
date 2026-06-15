#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【赛事播报合成 · raws → ours(py-Kimi)】给定一场已收集 raws/ 的 match_broadcast 子项目目录,
用 py 调 Kimi 把多源逐字原文交叉合成 ours/:long.md(全本) + long_predictable.md(可预测版) +
short.md(精简) + timeline.md(逐分钟)。

这是"赛事播报自动化"缺的那一环:之前 ours 是对话里 agent 手搓的(换对话不可复现);
现在 raws 一旦齐了,ours 由 py 生成、可复现。URL 发现仍是检索步(agent/WebSearch),抓取由 fetch_sources。

新旧:ours/long.md 已存且 raws 未新增 → 跳过(--refresh 重做)。多源交叉、标注分歧。

跑:python3 broadcast_synth.py --slug 2026-06-12_CAN_vs_BIH
   python3 broadcast_synth.py --all --refresh
"""
import os, sys, json, glob, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
MB = f"{RUNS}/data_processed/match_broadcast"
sys.path.insert(0, f"{ROOT}/wc_eval")
from wc_llm import kimi_text, predictable_long

LONG_SYS = """你是世界杯赛事播报编辑。给你同一场比赛的【多份逐字原文】(不同媒体/多语种),交叉合成一篇权威「全本播报 long」。
要求:① 多源交叉——同一事实多源印证则直接陈述,只在真有分歧处标「存疑」;② 覆盖:比分(含半场)/进球(分钟+球员+助攻)/红黄牌+停赛影响/关键扑救与机会/阵容与阵型/换人/统计(控球/射门/xG)/教练战术调整/裁判与新规/现场与历史;③ 客观、信息密度高、不杜撰原文没有的事实。
用 markdown,## 分节(① 比分速览 / ② 进球过程 / ③ 牌与停赛 / ④ 阵容战术 / ⑤ 数据 / ⑥ 现场与历史 / 存疑)。不要前言。"""

SHORT_SYS = """把这篇赛事播报浓缩成 8-12 行要点(markdown 无序列表),只留对"理解这场+预测两队下一场"最关键的硬信息(比分/进球/红牌停赛/伤退/状态信号)。客观,不抒情。不要前言。"""

TL_SYS = """从这篇赛事播报抽出逐分钟时间线(markdown),格式每行 `分钟' 事件`(如 `9' 进球 Quiñones(墨)`),按时间排序,只列实际发生的关键事件(进球/红黄牌/换人/重大扑救/VAR)。不要前言、不要解释。"""


def _read_raws(d):
    """读 raws/ 下所有源的逐字原文,拼成喂 LLM 的材料(限总长)。"""
    chunks = []
    for p in sorted(glob.glob(f"{d}/raws/*/*.json")):
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        src = r.get("source", os.path.basename(os.path.dirname(p)))
        txt = r.get("text") or r.get("original_text") or r.get("body") or ""
        if isinstance(r, dict) and not txt:                      # macheta 结构化场比数据
            txt = json.dumps({k: v for k, v in r.items() if k not in ("url",)}, ensure_ascii=False)[:2000]
        if txt:
            chunks.append(f"【源:{src}】\n{txt[:3500]}")
    return "\n\n".join(chunks)[:60000]


def synth(slug, refresh=False):
    d = f"{MB}/{slug}"
    if not os.path.isdir(f"{d}/raws"):
        return {"slug": slug, "skip": "无raws"}
    os.makedirs(f"{d}/ours", exist_ok=True)
    longp = f"{d}/ours/long.md"
    if os.path.exists(longp) and not refresh:
        return {"slug": slug, "skip": "ours已存(--refresh重做)"}
    material = _read_raws(d)
    if len(material) < 500:
        return {"slug": slug, "skip": "raws内容过少"}
    head = f"# {slug.replace('_', ' ')} · 赛事播报【全本 / long】\n> 2026 世界杯 · py-Kimi 多源交叉合成\n\n"
    long_md = head + kimi_text(LONG_SYS, f"【场次】{slug}\n\n{material}")
    open(longp, "w", encoding="utf-8").write(long_md)
    # 可预测版 + short + timeline 并行
    plong = predictable_long(long_md)["plong"]
    open(f"{d}/ours/long_predictable.md", "w", encoding="utf-8").write(
        "<!-- 可预测版 long:py-Kimi 从 long.md 改写;块B 优先取此版。-->\n\n" + plong)
    open(f"{d}/ours/short.md", "w", encoding="utf-8").write(kimi_text(SHORT_SYS, long_md))
    open(f"{d}/ours/timeline.md", "w", encoding="utf-8").write(kimi_text(TL_SYS, long_md))
    return {"slug": slug, "ok": True, "long": len(long_md), "plong": len(plong)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    slugs = [os.path.basename(x.rstrip("/")) for x in glob.glob(f"{MB}/*/") if os.path.isdir(x)] if a.all \
        else [a.slug] if a.slug else []
    if not slugs:
        raise SystemExit("✗ 用 --slug 或 --all")
    print(f"▶ 播报合成 raws→ours:{len(slugs)} 场 · py-Kimi")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(synth, s, a.refresh) for s in slugs]):
            print(f"  {f.result()}")


if __name__ == "__main__":
    main()
