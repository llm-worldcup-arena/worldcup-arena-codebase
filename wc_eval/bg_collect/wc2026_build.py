#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【team_data 块B · 世界杯2026 专项整理段】skill: wc-team-wc2026。

块B = summary.md 最末尾的 "## 世界杯 2026 · 专项整理" 段(非文件夹)。
结构:先分比赛(### 🏟 <日期·轮次·主客·对手·比分>)→ 每场 = 我们自己的赛事播报(long 叙事 + 逐分钟时间线)
     → 对本队后续的影响;最后 "### 📋 赛前 / 通用动态"(伤停/状态/下一场)。
⚠️ 块B 里只放【内容】,不放"取自哪里/块A块B如何分工"之类说明文字——那些规则写在 skill 文档里,不进 summary。

与 match_broadcast 子项目的融合(子项目文件夹不变 = 赛事播报类信息的单一真源):
- 该场没做过(无 ours/long.md)→ 主流程先完整跑 match_broadcast 子项目;
- 做过 → 不 remake;本轮普通检索若捞到该场【新的】播报类信息 → 源文加进子项目 raws/ +
  LLM 判断是否需把增量并进 ours(long/short/timeline 都是 LLM 合成物,有实质增量才改,改了记 CHANGELOG);
- raw 写入:子项目 raws/ 同时归档一份进 data_raw/<该场收集时分>/match_broadcast/<场次>/
  (用户定:要写入,因为块A吃所有信息;archive_broadcast_raws() 自动做,幂等只增不改)。
"""
import os, re, json, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
TEAM_DATA = f"{RUNS}/team_data"
HDR = "## 世界杯 2026 · 专项整理"
# 块B 摘录时过滤的维护性行(流程注记,不是赛事内容)
_MAINT = ("macheta", "待 Apify", "ours/data.json")


def _filter_maint(text):
    return "\n".join(l for l in text.split("\n")
                     if not any(k in l for k in _MAINT) and not l.strip().startswith("<!--")).strip()


def _long_excerpt(bc_dir):
    """long 叙事正文:**优先取 long_predictable.md(可预测版:硬信息全留、情感高度概括)**,无则退回 long.md。
    ① 到「### 来源」前;去 ④阵容长名单;##/### 降级 ####/#####;滤维护行。"""
    p = f"{bc_dir}/ours/long_predictable.md"
    if not os.path.exists(p):
        p = f"{bc_dir}/ours/long.md"
    if not os.path.exists(p):
        return None
    t = open(p, encoding="utf-8").read()
    i, j = t.find("## ①"), t.find("### 来源")
    body = (t[i:j] if i >= 0 and j > i else (t[i:] if i >= 0 else t)).strip()
    body = re.sub(r"\n## ④.*?(?=\n## )", "", "\n" + body, flags=re.S).strip()
    body = re.sub(r"(?m)^### ", "##### ", body)
    body = re.sub(r"(?m)^## ", "#### ", body)
    return _filter_maint(body)


def _timeline_excerpt(bc_dir):
    """timeline.md(逐分钟,精简、形式独特,一并带入):去 #标题/引言行,保留正文与代码块。"""
    p = f"{bc_dir}/ours/timeline.md"
    if not os.path.exists(p):
        return None
    lines = open(p, encoding="utf-8").read().split("\n")
    body = "\n".join(l for l in lines if not l.startswith("# ") and not l.startswith("> ")).strip()
    return _filter_maint(body) or None


def _match_section(pm):
    L = [f"### 🏟 {pm['date']} · {pm.get('round','')} · {pm.get('ha','')} vs {pm['opp']}（{pm['result']}）", ""]
    exc = _long_excerpt(pm["bc"])
    if exc:
        L.append(exc)
    tl = _timeline_excerpt(pm["bc"])
    if tl:
        L += ["", "#### 逐分钟时间线", tl]
    if pm.get("impact"):
        L += ["", "**对本队后续的影响**："] + [f"- {x}" for x in pm["impact"]]
    return "\n".join(L)


def _build(played, pre):
    L = [HDR, ""]
    for pm in (played or []):
        L += [_match_section(pm), ""]
    pre = pre or {}
    if pre.get("injuries") or pre.get("form") or pre.get("next_hint") or not played:
        L += ["### 📋 赛前 / 通用动态"]
        L += ["**伤停与可用性**："] + ([f"- {x}" for x in pre.get("injuries", [])] or ["- （暂无）"])
        L += ["**状态与细节**："] + ([f"- {x}" for x in pre.get("form", [])] or ["- （暂无）"])
        if pre.get("next_hint"):
            L += ["**下一场指引**：", f"- {pre['next_hint']}"]
    return "\n".join(L).rstrip() + "\n"


def append_block_b(snap, team, played=None, pre=None):
    """在 <snap>/<team>/summary.md 末尾追加/替换块B段(幂等;追加用 rstrip 落真 EOF)。"""
    path = f"{TEAM_DATA}/{snap}/{team}/summary.md"
    if not os.path.exists(path):
        raise SystemExit(f"✗ 无 summary: {path}")
    t = open(path, encoding="utf-8").read()
    block = _build(played, pre)
    if HDR in t:
        t = re.sub(re.escape(HDR) + r".*\Z", block, t, flags=re.S)
    else:
        t = t.rstrip() + "\n\n---\n\n" + block
    open(path, "w", encoding="utf-8").write(t)
    return path


def archive_broadcast_raws(collect_ts, bc_dir):
    """【增量归档】把子项目该场 raws/ 里【尚未在 data_raw 任何时分归档过】的源,
    归档进 data_raw/<collect_ts>/match_broadcast/<场次>/。

    版本语义(关键,勿破坏):子项目按【场次】累积(同一场的 raws 随时间增长),data_raw 按【采集时刻】切片。
    → 每个源文件只在【它被收集的那个时分目录】出现一次:
      首次收集 → 全部源进当时的时分目录;1 小时后再来(扩充了新源)→ 只有【新源】进新时分目录,
      旧源绝不重复归档(已在旧时分目录里)。既不冗余、也不把新源混进旧时刻(撒谎)。"""
    import glob
    slug = os.path.basename(bc_dir.rstrip("/"))
    src = f"{bc_dir}/raws"
    if not os.path.isdir(src):
        return None, 0
    done = {os.path.basename(p) for p in glob.glob(f"{RUNS}/data_raw/*/match_broadcast/{slug}/*")}
    new = [d for d in os.listdir(src) if d not in done]
    if not new:
        return None, 0                                 # 没有新源 → 不建目录、不归档
    dst = f"{RUNS}/data_raw/{collect_ts}/match_broadcast/{slug}"
    os.makedirs(dst, exist_ok=True)
    for d in new:
        s, t = f"{src}/{d}", f"{dst}/{d}"
        (shutil.copytree if os.path.isdir(s) else shutil.copy2)(s, t)
    return dst, len(new)


def mb_integration_on():
    """match_broadcast 接入开关(默认 off)。off=只复用已有;on=主流程自动跑/扩充。"""
    p = f"{ROOT}/config/wc_pipeline.json"
    if os.path.exists(p):
        return bool(json.load(open(p, encoding="utf-8")).get("auto_run_match_broadcast", False))
    return False


def mb_done(bc_dir):
    """该场是否已做(有 long.md)→ 做过就不 remake;新增信息走「扩充+LLM判断」而非重做。"""
    return os.path.exists(f"{bc_dir}/ours/long.md")


if __name__ == "__main__":
    print("块B:append_block_b(snap, team, played, pre) | 归档:archive_broadcast_raws(ts, bc_dir)")
    print(f"match_broadcast 接入开关: {'ON' if mb_integration_on() else 'OFF(默认)'}")
