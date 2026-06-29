#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把【预测档案】archive/predictions.json 上线到前端 worldcup-data.js —— 安全三件套,根除"漏代码致崩":
  ① 只替换 PRED 对象(括号深度匹配,文件其余一字不动 → 绝不漏 X2/OU/BT 等映射表)
  ② node 运行时验证 ready()(语法过≠跑得起来,崩就【回滚】不写坏文件)
  ③ cache-bust index.html 的 ?v=
  ④ 前端 UI 契约检查:已结算淘汰赛在竞猜卡列表必须显示比分,未结算仍显示阶段/暂定。
另:--reveal <日期,如 6.12> 同步把前端 worldcup-arena.js 的 REVEAL_THROUGH 改到该日(解锁当天比赛预测)。

★ 网页数据 = 预测档案(唯一真源)。逐日只需:archive_pred.py 把新场累加进档案 → 本脚本刷新网页 + 解锁。

跑:python3 update_web.py                  # 把档案现状刷到网页
   python3 update_web.py --reveal 6.12    # 顺带解锁到 6/12
通过后:cd 前端 && git add -A && git commit && git push

教训(2026-06-11):曾"提取应用逻辑重组文件",漏掉夹在 PRED 与 function hc 间的 var X2/OU/BT
→ ready() 崩 → 下半页不渲染。本脚本只换 PRED + 实跑验证 + 回滚,机制上根除。
"""
import json, re, sys, subprocess, argparse, datetime, os
from common import _HANDICAP

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根(可移植)
# 网页仓库在另一个目录;默认同级 worldcup_2026_web/site,可用环境变量 WC_WEB_DIR 覆盖
WEB = os.environ.get("WC_WEB_DIR") or os.path.join(os.path.dirname(ROOT), "worldcup_2026_web", "site")
if not os.path.isdir(WEB):                # 别人 clone 没有相邻网页仓 → 明确报错(而非默默失败),指明用环境变量
    raise SystemExit(f"✗ 找不到网页仓库目录:{WEB}\n  请设环境变量 WC_WEB_DIR=<你的 worldcup 网页仓 site 路径> 后重试。")
ARC = f"{ROOT}/wc_runs/archive"


def verify_web_ui_contracts():
    """Guard the small but easy-to-regress UI rules that update_web relies on.

    update_web.py injects knockout results into A.RESULTS with key match_id - 1.
    The match picker must then render settled knockout rows like group rows:
    score when settled, round badge when only pairing/picks are known, provisional
    when the bracket slot is not fixed.
    """
    ui_path = f"{WEB}/worldcup-ui.js"
    ui = open(ui_path, encoding="utf-8").read()
    m = re.search(r"var koRows = koData\(\)\.map\(function \(m, i\) \{(?P<body>.*?)host\.innerHTML", ui, re.S)
    if not m:
        sys.exit("✗ 前端 UI 契约检查失败:找不到 renderAmList 的 koRows 区块")
    body = m.group("body")
    checks = [
        ("淘汰赛已结算判断使用 res[match_id-1]",
         re.search(r"done\s*=\s*!!res\[m\[0\]\s*-\s*1\]", body)),
        ("已结算淘汰赛列表尾标显示比分",
         "<span class='dn'>" in body and re.search(r"res\[m\[0\]\s*-\s*1\].*?split\(\"/\"\)\[0\]", body, re.S)),
        ("未结算但已确定对阵仍显示阶段名",
         re.search(r"f\s*\?\s*\"<span class='gp'>\"\s*\+\s*koBadge\(m,\s*en\)", body)),
        ("未确定对阵仍显示暂定",
         re.search(r"koBadge\(m,\s*en\).*?Prov\.", body, re.S) and "暂定" in body),
        # 淘汰赛展示按【开球时间】排序(2026-06-29 加,防回归):别让"巴西-日本 13:00
        # 因官方编号 M76 最大而排到当天最后"再现;擂台列表(koRows)同一天按 kickoff 排。
        ("擂台淘汰赛列表按开球时间排序",
         re.search(r"\.sort\(.*?tm\(\s*[ab]\.m\[3\]", body, re.S)),
    ]
    # 今日赛程列表 / 今日竞猜卡 / 赛程页按天 —— 这 3 处淘汰赛渲染也须按开球时间(m[3])排序。
    n_ko_time_sort = len(re.findall(r"T\(a\[3\]\)\s*-\s*T\(b\[3\]\)", ui))
    if n_ko_time_sort < 3:
        checks.append((f"今日/竞猜卡/赛程页淘汰赛按开球时间排序(应≥3处,实测{n_ko_time_sort}处)", False))
    miss = [name for name, ok in checks if not ok]
    if miss:
        sys.exit("✗ 前端 UI 契约检查失败:\n  - " + "\n  - ".join(miss))


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
    # RESULTS 的索引键必须与前端读取方式一致:
    #   小组赛:worldcup-ui.js 用 FIX 数组下标读 res[i] → 仍按 FIX/时间顺序枚举;
    #   淘汰赛:worldcup-ui.js 用 matchNo-1 读 res[m[0]-1] → 必须稀疏写 match_id-1。
    _ms = json.load(open(f"{ROOT}/wc_runs/data_reference/matches.json", encoding="utf-8"))
    RES = {}
    group_ms = sorted((m for m in _ms if m.get("round") == "group"),
                      key=lambda m: (m.get("date") or "", m.get("kickoff_ts") or "zzzz", m.get("match_id") or ""))
    ko_ms = [m for m in _ms if m.get("round") != "group"]
    for pos, m in enumerate(group_ms):
        mk = f"{m['team_a']}_vs_{m['team_b']}"
        rr = (res.get("matches") or {}).get(mk, {})
        if rr.get("score"):
            v = str(rr["score"]).replace("-", ":")
            if rr.get("ht"):
                v += "/" + str(rr["ht"]).replace("-", ":")
            RES[str(pos)] = v
    for m in ko_ms:
        mk = f"{m['team_a']}_vs_{m['team_b']}"
        rr = (res.get("matches") or {}).get(mk, {})
        mm = re.match(r"^M(\d+)$", str(m.get("match_id") or ""))
        if rr.get("score") and mm:
            v = str(rr["score"]).replace("-", ":")
            if rr.get("ht"):
                v += "/" + str(rr["ht"]).replace("-", ":")
            RES[str(int(mm.group(1)) - 1)] = v
    aj = re.sub(r"RESULTS:\s*\{[^}]*\}", "RESULTS: " + json.dumps(RES, ensure_ascii=False), aj, count=1)
    # 注入全局赛果（results.global + group_winners → arena.js;FIFA码转英文队名）
    teams = {t["team_id"]: t["name_en"] for t in json.load(open(f"{ROOT}/wc_runs/data_reference/teams.json", encoding="utf-8"))}
    # 前端 WC.T 使用展示键而非部分 FIFA 官方英文全称；这些键必须对齐，否则如 D 组头名 USA 会显示成英文文本。
    teams.update({"USA": "USA", "CIV": "Côte d'Ivoire", "COD": "DR Congo", "CUW": "Curaçao", "TUR": "Türkiye"})
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

    hcp = {f"{home}_vs_{away}": line for (home, away), line in _HANDICAP.items()}
    hcp_js = re.sub(r"^", "  ", json.dumps(hcp, ensure_ascii=False, indent=2), flags=re.M).lstrip()
    aj = re.sub(r"var HCP\s*=\s*\{.*?\};", "var HCP = " + hcp_js + ";", aj, count=1, flags=re.S)
    open(apjs, "w", encoding="utf-8").write(aj)
    verify_web_ui_contracts()

    nm = len(next(iter(arc["models"].values()), {}).get("matches", {}))
    print(f"✅ 上线就绪:worldcup-data.js ← 预测档案(matches {nm} 场/模型){revmsg}")
    print(f"   只换 PRED · 运行时验证通过 · UI契约检查通过 · cache-bust ?v={ver}")
    print(f"   下一步:cd {WEB} && git add -A && git commit && git push")


if __name__ == "__main__":
    main()
