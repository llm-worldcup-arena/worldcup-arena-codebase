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
import json, re, sys, subprocess, argparse, datetime, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根(可移植)
# 网页仓库在另一个目录;默认同级 worldcup_2026_web/site,可用环境变量 WC_WEB_DIR 覆盖
WEB = os.environ.get("WC_WEB_DIR") or os.path.join(os.path.dirname(ROOT), "worldcup_2026_web", "site")
if not os.path.isdir(WEB):                # 别人 clone 没有相邻网页仓 → 明确报错(而非默默失败),指明用环境变量
    raise SystemExit(f"✗ 找不到网页仓库目录:{WEB}\n  请设环境变量 WC_WEB_DIR=<你的 worldcup 网页仓 site 路径> 后重试。")
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
    new = re.sub(r"数据批次:\s*\S+", f"数据批次:{batch}(预测档案)", new)   # 注:原正则冒号后多了空格,与实际"数据批次:xxx"(无空格)不匹配→注释永不更新,已修
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
    html = re.sub(r"(worldcup[a-z-]*\.(?:js|css))\?v=[0-9a-zA-Z-]+", rf"\1?v={ver}", html)  # [a-z-]* 兼容单点 worldcup.css(旧 regex 漏了它→CSS 改动一直不刷新)
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
    # 注入全局赛果（results.global + group_winners → arena.js;FIFA码转英文队名）
    teams = {t["team_id"]: t["name_en"] for t in json.load(open(f"{ROOT}/wc_runs/bg/teams.json", encoding="utf-8"))}
    en = lambda c: teams.get(c, c)
    g = res.get("global") or {}
    CONF = {"欧洲": "UEFA", "南美": "CONMEBOL", "北美": "CONCACAF", "非洲": "CAF", "亚洲": "AFC", "大洋洲": "OFC"}
    inj = {
        "CHAMPION": (en(g["夺冠"]) if g.get("夺冠") else ""),
        "FINALISTS": [en(c) for c in (g.get("进决赛") or [])],
        "SEMIS": [en(c) for c in (g.get("四强") or [])],
        "WINNER_CONF": (CONF.get(g.get("夺冠大洲"), "") if g.get("夺冠大洲") else ""),
        "TOTAL_GOALS": res.get("total_goals"),
        "GROUP_WINNERS": {grp: en(c) for grp, c in (res.get("group_winners") or {}).items()},
    }
    for field, val in inj.items():
        aj = re.sub(field + r":\s*(\[[^\]]*\]|\"[^\"]*\"|null|\d+|\{[^}]*\})", field + ": " + json.dumps(val, ensure_ascii=False), aj, count=1)
    open(apjs, "w", encoding="utf-8").write(aj)
    if RES:
        revmsg += f" · RESULTS {len(RES)} 场"
    if g:
        revmsg += " · 全局赛果"

    nm = len(next(iter(arc["models"].values()), {}).get("matches", {}))
    print(f"✅ 上线就绪:worldcup-data.js ← 预测档案(matches {nm} 场/模型){revmsg}")
    print(f"   只换 PRED · 运行时验证通过 · cache-bust ?v={ver}")
    print(f"   下一步:cd {WEB} && git add -A && git commit && git push")


if __name__ == "__main__":
    main()
