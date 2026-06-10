#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把指定批次的预测上线到前端 worldcup-data.js —— 安全三件套,根除"漏代码致崩":
  ① 只替换 PRED 对象(括号深度匹配精确切出,文件其余一字不动 → 绝不漏 X2/OU/BT 等映射表)
  ② node 运行时验证:实际跑 ready(),崩就【回滚】不写坏文件(语法过≠跑得起来,必须实跑)
  ③ 自动 cache-bust:bump index.html 的 ?v=(否则 CDN/浏览器吃旧缓存)

跑:python3 update_web.py 2026-06-10_2330
   通过后:cd 前端 && git add -A && git commit && git push

教训(2026-06-11):曾"提取应用逻辑重组文件",漏掉夹在 PRED 与 function hc 之间的 var X2/OU/BT
→ ready() 崩 → 整个下半页不渲染。本脚本【只换 PRED + 实跑验证 + 失败回滚】,从机制上根除此类。
"""
import json, re, sys, subprocess

WEB = "/home/ubuntu/worldcup_2026_web/site"
ROOT = "/home/ubuntu/worldcup_2026"


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python3 update_web.py <批次,如 2026-06-10_2330>")
    batch = sys.argv[1]
    uni = json.load(open(f"{ROOT}/wc_runs/predictions/{batch}/_unified.json", encoding="utf-8"))
    pred = json.dumps(uni["models"], ensure_ascii=False, indent=1)

    path = f"{WEB}/worldcup-data.js"
    orig = open(path, encoding="utf-8").read()

    # ① 只替换 var PRED = {...}（括号深度匹配，精确切 PRED 对象，其余不动）
    s = orig.index("var PRED = ")
    b0 = orig.index("{", s)
    depth, i = 0, b0
    while i < len(orig):
        depth += (orig[i] == "{") - (orig[i] == "}")
        if depth == 0:
            break
        i += 1
    new = orig[:b0] + pred + orig[i + 1:]
    new = re.sub(r"数据批次: \S+", f"数据批次: {batch}", new)
    open(path, "w", encoding="utf-8").write(new)

    # ② node 运行时验证：实际跑 ready()，崩就回滚
    test = ("global.setTimeout=function(){};"
            "global.window={addEventListener:function(){},"
            "__WC_ARENA:{MODELS:['Claude','GPT','Gemini','Kimi','GLM','Seed'].map(function(n){return {name:n};}),"
            "predict:function(){},poolPick:function(){}},"
            "__WC:{T:{Mexico:1},flag:function(x){return x;}}};"
            "require('./worldcup-data.js');")
    r = subprocess.run(["node", "-e", test], cwd=WEB, capture_output=True, text=True)
    if r.returncode != 0:
        open(path, "w", encoding="utf-8").write(orig)                       # 回滚
        sys.exit(f"✗ 运行时验证失败 → 已回滚、未上线:\n{r.stderr.strip()[:400]}")

    # ③ cache-bust：bump index.html 的 ?v=
    ver = batch.replace("-", "").replace("_", "-")                          # 20260610-2330,每批次唯一
    ip = f"{WEB}/index.html"
    html = open(ip, encoding="utf-8").read()
    html = re.sub(r"(worldcup[.-][a-z]*\.(?:js|css))\?v=[0-9a-zA-Z-]+", rf"\1?v={ver}", html)
    open(ip, "w", encoding="utf-8").write(html)

    print(f"✅ 上线就绪:worldcup-data.js → 批次 {batch}")
    print(f"   只换 PRED(其余不动)· 运行时验证通过 · cache-bust ?v={ver}")
    print(f"   下一步:cd {WEB} && git add -A && git commit -m '上线 {batch}' && git push")


if __name__ == "__main__":
    main()
