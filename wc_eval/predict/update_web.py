#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把【预测档案】archive/predictions.json 上线到前端 worldcup-data.js —— 安全三件套,根除"漏代码致崩":
  ① 只替换 PRED 对象(括号深度匹配,文件其余一字不动 → 绝不漏 X2/OU/BT 等映射表)
  ② node 运行时验证 ready()(语法过≠跑得起来,崩就【回滚】不写坏文件)
  ③ cache-bust index.html 的 ?v=
另:--reveal <日期,如 6.12> 同步把前端 worldcup-arena.js 的 REVEAL_THROUGH 改到该日(解锁当天比赛预测)。

★ 网页数据 = 预测档案(唯一真源)。逐日只需:archive_pred.py 把新场累加进档案 → 本脚本刷新网页 + 解锁。

跑:python3 update_web.py                  # 把档案现状刷到网页
   python3 update_web.py --reveal 6.12    # 顺带解锁到 6/12
通过后:cd 前端 && git add -A && git commit && git push

教训(2026-06-11):曾"提取应用逻辑重组文件",漏掉夹在 PRED 与 function hc 间的 var X2/OU/BT
→ ready() 崩 → 下半页不渲染。本脚本只换 PRED + 实跑验证 + 回滚,机制上根除。
"""
import json, re, sys, subprocess, argparse, datetime

WEB = "/home/ubuntu/worldcup_2026_web/site"
ROOT = "/home/ubuntu/worldcup_2026"
ARC = f"{ROOT}/wc_runs/archive"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reveal", help="解锁到某日,如 6.12(改前端 REVEAL_THROUGH)")
    a = ap.parse_args()

    arc = json.load(open(f"{ARC}/predictions.json", encoding="utf-8"))           # ★ 从预测档案读
    pred = json.dumps(arc["models"], ensure_ascii=False, indent=1)
    batch = (arc.get("_固定记录") or [{}])[-1].get("批次", "archive")

    path = f"{WEB}/worldcup-data.js"
    orig = open(path, encoding="utf-8").read()

    # ① 只替换 var PRED = {...}（括号深度匹配，其余不动）
    s = orig.index("var PRED = "); b0 = orig.index("{", s)
    depth, i = 0, b0
    while i < len(orig):
        depth += (orig[i] == "{") - (orig[i] == "}")
        if depth == 0:
            break
        i += 1
    new = orig[:b0] + pred + orig[i + 1:]
    new = re.sub(r"数据批次: \S+", f"数据批次:{batch}(预测档案)", new)
    open(path, "w", encoding="utf-8").write(new)

    # ② node 运行时验证 ready()，崩就回滚
    test = ("global.setTimeout=function(){};global.window={addEventListener:function(){},"
            "__WC_ARENA:{MODELS:['Claude','GPT','Gemini','Kimi','GLM','Seed'].map(function(n){return {name:n};}),"
            "predict:function(){},poolPick:function(){}},__WC:{T:{Mexico:1},flag:function(x){return x;}}};"
            "require('./worldcup-data.js');")
    r = subprocess.run(["node", "-e", test], cwd=WEB, capture_output=True, text=True)
    if r.returncode != 0:
        open(path, "w", encoding="utf-8").write(orig)
        sys.exit(f"✗ 运行时验证失败 → 已回滚、未上线:\n{r.stderr.strip()[:400]}")

    # ③ cache-bust
    ver = batch.replace("-", "").replace("_", "-") + "-" + datetime.datetime.now().strftime("%H%M%S")
    ip = f"{WEB}/index.html"; html = open(ip, encoding="utf-8").read()
    html = re.sub(r"(worldcup[.-][a-z]*\.(?:js|css))\?v=[0-9a-zA-Z-]+", rf"\1?v={ver}", html)
    open(ip, "w", encoding="utf-8").write(html)

    # 改 arena.js:解锁 REVEAL_THROUGH(可选)+ 从 results.json 注入真实赛果 RESULTS(前端自动结算积分榜)
    apjs = f"{WEB}/worldcup-arena.js"; aj = open(apjs, encoding="utf-8").read()
    revmsg = ""
    if a.reveal:
        aj = re.sub(r"(REVEAL_THROUGH\s*[:=]\s*)['\"][^'\"]*['\"]", rf'\1"{a.reveal}"', aj, count=1)
        revmsg = f" · REVEAL_THROUGH→{a.reveal}"
    res = json.load(open(f"{ARC}/results.json", encoding="utf-8"))
    order = [f"{m['team_a']}_vs_{m['team_b']}" for m in json.load(open(f"{ROOT}/wc_runs/bg/matches.json", encoding="utf-8"))]
    RES = {}
    for idx, mk in enumerate(order):
        rr = (res.get("matches") or {}).get(mk, {})
        if rr.get("score"):
            v = str(rr["score"]).replace("-", ":")
            if rr.get("ht"):
                v += "/" + str(rr["ht"]).replace("-", ":")
            RES[str(idx)] = v
    aj = re.sub(r"RESULTS:\s*\{[^}]*\}", "RESULTS: " + json.dumps(RES, ensure_ascii=False), aj, count=1)
    open(apjs, "w", encoding="utf-8").write(aj)
    if RES:
        revmsg += f" · 注入 RESULTS {len(RES)} 场"

    nm = len(next(iter(arc["models"].values()), {}).get("matches", {}))
    print(f"✅ 上线就绪:worldcup-data.js ← 预测档案(matches {nm} 场/模型){revmsg}")
    print(f"   只换 PRED · 运行时验证通过 · cache-bust ?v={ver}")
    print(f"   下一步:cd {WEB} && git add -A && git commit && git push")


if __name__ == "__main__":
    main()
