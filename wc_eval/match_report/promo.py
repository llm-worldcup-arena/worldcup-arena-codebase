#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【赛事播报·宣传版 · AI 预测汇报】自动生成社媒（小红书/抖音）宣传文案：
   - ours/promo_predict_pre.md   AI 预测·**赛前（没看到结果版）**：6 模型预测 + 共识
   - ours/promo_predict_post.md  AI 预测·**赛后（看到结果版）**：预测 vs 实际 + 谁神准

   数据来源：web 的 `worldcup-data.js`（6 模型预测）+ `ours/data.json`（实际比分）。
   另一个宣传版 `ours/promo_report.md`（赛事播报社媒战报）由 CC 创作（创意文案，见 skill）。
   skill: wc-match-broadcast。跑：python3 promo.py --match M1
"""
import os, sys, json, argparse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_sources as FS          # noqa: E402

WEB = os.environ.get("WC_WEB_DATA") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "worldcup_2026_web", "site", "worldcup-data.js")   # 可移植:env WC_WEB_DATA 覆盖
MKTS = ["胜平负", "让球", "大小2.5", "双方进球", "单双", "半全场", "正确比分"]


def load_pred():
    js = open(WEB, encoding="utf-8").read()
    i = js.find("{", js.find("var PRED"))
    depth = 0
    for k in range(i, len(js)):
        if js[k] == "{":
            depth += 1
        elif js[k] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(js[i:k + 1])
    return {}


def outcomes(score, ht):
    """从比分推 7 个盘口的实际结果。"""
    h, a = map(int, score.split("-")); tot = h + a
    o = {"胜平负": "主胜" if h > a else ("平" if h == a else "客胜"),
         "让球": "主胜盘" if h - a >= 2 else "客胜盘",
         "大小2.5": "大" if tot > 2.5 else "小",
         "双方进球": "是" if h > 0 and a > 0 else "否",
         "单双": "单" if tot % 2 else "双",
         "正确比分": score}
    if ht and "-" in str(ht):
        hh, ha = map(int, str(ht).split("-"))
        htr = "主" if hh > ha else ("平" if hh == ha else "客")
        ftr = "主" if h > a else ("平" if h == a else "客")
        o["半全场"] = f"{htr}-{ftr}"
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True)
    a = ap.parse_args()
    md = FS.resolve_match(a.match)
    key = f"{md['home']}_vs_{md['away']}"
    base = f"{FS.RUNS}/data_processed/match_broadcast/{md['slug']}"
    os.makedirs(f"{base}/ours", exist_ok=True)
    PRED = load_pred()
    models = [m for m in PRED if PRED[m].get("matches", {}).get(key)]
    if not models:
        sys.exit(f"✗ web 预测里没有 {key}")
    preds = {m: PRED[m]["matches"][key] for m in models}
    H, Az = md["home_zh"], md["away_zh"]

    # ── 赛前版（没看到结果版）──
    wv, wn = Counter(preds[m].get("胜平负") for m in models).most_common(1)[0]
    sv, sn = Counter(preds[m].get("大小2.5") for m in models).most_common(1)[0]
    scores = Counter(preds[m].get("正确比分") for m in models)
    pre = (f"# 🤖 6 大 AI 预言：{H} vs {Az}，谁能赢？\n"
           f"> 2026 世界杯 · {md['comp']} · **赛前预测（结果未知）**\n\n"
           f"我们让 {' / '.join(models)} 六大顶尖 AI 同台开预测👇\n\n"
           f"🏆 **胜平负**：{wn}/6 个押「{wv}」\n"
           f"🎯 **正确比分**：{'、'.join(f'{k}（{v}票）' for k, v in scores.most_common(3))}\n"
           f"⚽ **大小球**：{sn}/6 押「{sv}球」\n\n"
           f"谁能笑到最后、成为最准 AI 预言家？赛后见真章🔮\n"
           f"👉 关注「LLM 世界杯竞技场」看 6 大模型硬刚\n\n"
           f"#世界杯2026 #AI预测 #大模型 #{H} #{Az}\n")
    open(f"{base}/ours/promo_predict_pre.md", "w", encoding="utf-8").write(pre)

    # ── 赛后版（看到结果版，需 data.json 比分）──
    dj = f"{base}/ours/data.json"
    if not os.path.exists(dj):
        print(f"✅ {key}: 赛前版 → promo_predict_pre.md（无 data.json，赛后版跳过，先跑 harddata.py）")
        return
    d = json.load(open(dj, encoding="utf-8"))
    act = outcomes(d["score"], d.get("ht"))
    hit = {m: sum(1 for k in MKTS if preds[m].get(k) == act.get(k)) for m in models}
    rank = sorted(models, key=lambda m: -hit[m])
    perfect = [m for m in models if hit[m] == 7]
    score_hit = [m for m in models if preds[m].get("正确比分") == act["正确比分"]]
    top = rank[0]
    if perfect:
        head = f"🥇 **满分 AI（7/7 全中）**：{'、'.join(perfect)} —— 连「正确比分 {act['正确比分']}」都精准命中！🔥"
    else:
        head = (f"🥇 **最准 AI：{top}（{hit[top]}/7）**"
                + (f"，独中正确比分 {act['正确比分']}，封神！🔥" if top in score_hit else "！"))
    wlhit = sum(1 for m in models if preds[m].get("胜平负") == act["胜平负"])
    post = (f"# 🎯 AI 预言成绩单：{H} {d['score']} {Az}，谁神准？\n"
            f"> 2026 世界杯 · {md['comp']} · **赛后复盘（实际 {d['score']}）**\n\n"
            f"赛前 6 大 AI 预测，实际 {H} {d['score']} {Az}👇\n\n"
            f"{head}\n"
            f"📊 各 AI 命中：{'、'.join(f'{m} {hit[m]}/7' for m in rank)}\n"
            f"✅ 押对「{act['胜平负']}」：{wlhit}/6 个 AI\n"
            f"🎯 押中正确比分 {act['正确比分']}：{'、'.join(score_hit) if score_hit else '无 AI 命中'}\n\n"
            f"AI 到底有多懂球？关注「LLM 世界杯竞技场」看 6 大模型硬刚⚔️\n\n"
            f"#世界杯2026 #AI预测 #大模型battle #{H}{Az}\n")
    open(f"{base}/ours/promo_predict_post.md", "w", encoding="utf-8").write(post)
    print(f"✅ {key}: 赛前+赛后 → promo_predict_pre/post.md "
          f"（满分AI: {perfect or '无'}，最准: {top} {hit[top]}/7）")


if __name__ == "__main__":
    main()
