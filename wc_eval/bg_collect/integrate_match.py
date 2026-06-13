#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【世界杯·赛后增量更新 · 第3步】把"这一场"【增量】加进两队 summary + raw 留底 + 防泄露。

   skill: wc-incremental-update。上游：collect_match.py(第1步采硬数据) + agent WebSearch(第2步补文字)。
   本脚本只做：① raw 全量留底 ② 增量整合进两队 summary（近期赛果加 1 行 + ⑦伤停动态）③ 防泄露 date≤today 校验。

【单场 raw JSON 结构】(agent 产出，存 /tmp 或 raw 目录)：
{
 "date":"2026-06-14","comp":"世界杯·A组","home":"MEX","away":"COD","score":"2-1","ha_home":"主",
 "goals":[{"min":23,"team":"MEX","player":"X","type":"运动战"}],
 "stats":{"possession":"55-45","shots":"14-9","sot":"5-3","corners":"6-4"},
 "xg":{"MEX":1.8,"COD":1.1}, "ratings":{"X":7.8},
 "cards":[{"min":67,"team":"COD","player":"Y","type":"黄"}],
 "injuries":["X 第30分钟伤退，疑似腿筋"], "suspensions":["Y 累计2黄，下轮停赛"],
 "quotes":["主帅：..."], "narrative":"多篇播报综合的叙事…",
 "prediction_note":"对预测的含义：MEX 锋线状态佳、COD 后防 X 伤退是隐患…"
}

跑：APIFY 无关。python3 integrate_match.py <单场raw.json> --ts <YYYY-MM-DD_HHMM> --today <YYYY-MM-DD> [--td 2026-06-10_0228]
"""
import json, re, os, argparse

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/wc_runs"   # 可移植


def _to_code(name):
    """队名→FIFA码:collect_match(macheta)给英文全名,这里统一解析,别再手工换。"""
    if re.match(r"^[A-Z]{3}$", name or ""):
        return name
    norm = lambda s: re.sub(r"[^a-z]", "", (s or "").lower().replace("&", "and"))
    for t in json.load(open(f"{BASE}/data_reference/teams.json", encoding="utf-8")):
        if norm(t.get("name_en")) == norm(name):
            return t["team_id"]
    raise SystemExit(f"✗ 队名「{name}」解析不出 FIFA 码(teams.json 无匹配),手查后改 m.json")


def integrate(match, td_dir, raw_ts, today):
    match["home"], match["away"] = _to_code(match["home"]), _to_code(match["away"])
    # ── 防泄露：只整合「已踢完、不晚于今天」的比赛 ──
    if match.get("date", "9999") > today:
        print(f"🚫 防泄露：{match.get('date')} 晚于 {today}（未踢/待预测），拒绝整合")
        return False

    # ── ① raw 全量留底（按种类分子文件夹 + _source.md）──
    rawd = f"{BASE}/data_raw/{raw_ts}/match_reports"
    os.makedirs(rawd, exist_ok=True)
    rid = f"{match['home']}_vs_{match['away']}_{match['date']}"
    json.dump(match, open(f"{rawd}/{rid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not os.path.exists(f"{rawd}/_source.md"):
        open(f"{rawd}/_source.md", "w", encoding="utf-8").write(
            "# 采集来源说明 · 单场赛后\n"
            "- **方式**：agent WebSearch 多角度(赛后播报/统计xG/球员评分/伤病停赛+采访) + WebFetch 能读的新闻站\n"
            "- **可靠**：专业站(ESPN/Sofascore)反爬,数据经各新闻报道引用 WebSearch 间接全拿\n"
            "- **防泄露**：只采已踢完、非待预测的场次；本脚本再兜一道 date≤today 校验\n"
            "- **用途**：世界杯 2026 预测 benchmark · 滚动更新 summary\n")

    # ── ② 整合进两队 summary ──
    sc = match.get("score", "")
    sh, sa = (sc.split("-") + ["", ""])[:2] if "-" in sc else ("", "")
    ha_home = match.get("ha_home", "中")
    ha_away = {"主": "客", "客": "主", "中": "中"}.get(ha_home, "中")
    comp = match.get("comp", "世界杯")
    for team, opp, ha, my, ot in [(match["home"], match["away"], ha_home, sh, sa),
                                   (match["away"], match["home"], ha_away, sa, sh)]:
        f = f"{BASE}/team_data/{td_dir}/{team}/summary.md"
        if not os.path.exists(f):
            print(f"  ⚠️ {team} summary 不存在，跳过"); continue
        t = open(f, encoding="utf-8").read()
        row = f"| {match['date']} | {ha} | {opp} | {my}-{ot} | {comp} |"

        # 近期赛果：①表格格式 append 一行 ②列表格式(- 近N场)append 一条 bullet ③都没识别→明确告警(不再静默"已存")
        rec_seg = t.split("## 近期状态")[-1].split("\n## ")[0] if "## 近期状态" in t else ""
        added_row = "已存"
        if match["date"] in rec_seg:                                   # 真的已存
            pass
        elif re.search(r"## 近期状态.*?\n(?:\|[^\n]*\n)+", t, re.S):     # 表格格式
            mt = re.search(r"(## 近期状态.*?\n(?:\|[^\n]*\n)+)", t, re.S)
            t = t.replace(mt.group(1), mt.group(1).rstrip() + "\n" + row + "\n", 1); added_row = "+1表"
        else:
            mb = re.search(r"(## 近期状态\n(?:[^\n]*\n)*?(?:  - [^\n]+\n)+)", t)   # 列表格式
            if mb:
                wld = "W" if (my and ot and int(my) > int(ot)) else ("L" if (my and ot and int(my) < int(ot)) else "D")
                bullet = f"  - {match['date']} {ha} vs {opp} {my}–{ot}({wld})  ← {comp}"
                t = t.replace(mb.group(1), mb.group(1).rstrip() + "\n" + bullet + "\n", 1); added_row = "+1列"
            else:
                added_row = "⚠️未识别格式·未追加,请人工补"
                print(f"  ⚠️ {team}: 近期状态段格式无法识别,赛果【未自动追加】——人工补：{row}")

        # ⑦关键动态：追加本场伤停（对预测最直接）。
        # dict 条目({side,player,note,sources})只进所属边的队(防张冠李戴)并格式化成行文;字符串条目无归属信息,沿旧例进双方(自带上下文)。
        side_key = "home" if team == match["home"] else "away"
        def _fmt(x):
            if isinstance(x, dict):
                src = "·多源核实:" + "/".join(x["sources"]) if x.get("sources") else ""
                return f"{x.get('player')}:{x.get('note', '')}".rstrip(":") + src
            return str(x)
        def _mine(xs):
            return [x for x in xs if not isinstance(x, dict) or x.get("side") in (None, side_key)]
        notes = [f"- 🏥 {_fmt(x)}（{match['date']} vs {opp}）" for x in _mine(match.get("injuries", []))]
        notes += [f"- 🟨 {_fmt(x)}（{match['date']} vs {opp}）" for x in _mine(match.get("suspensions", []))]
        # ── LLM 清洁+核实(与 news 三判对称:防张冠李戴/泄露/脏;失败则原样不阻断)──
        removed = []
        if notes:
            try:
                import sys as _s; _s.path.insert(0, os.path.dirname(BASE) + "/wc_eval")
                from wc_llm import verify_increment
                vr = verify_increment(team, f"{match['date']} vs {opp} {sc}", notes)
                if vr.get("notes"):
                    notes = [n if n.strip().startswith("-") else f"- {n}" for n in vr["notes"]]
                removed = vr.get("removed", [])
            except Exception as e:
                print(f"  ⚠️ {team} 增量LLM审核跳过:{str(e)[:40]}")
        added_notes = 0
        if notes:
            m7 = re.search(r"(## ⑦[^\n]*\n)", t)
            if m7:
                t = t.replace(m7.group(1), m7.group(1) + "\n".join(notes) + "\n", 1); added_notes = len(notes)
        if removed:
            print(f"  🧹 {team} 增量审核剔除:{removed}")

        open(f, "w", encoding="utf-8").write(t)
        print(f"  ✅ {team}: 近期赛果[{added_row}]、伤停动态+{added_notes}")
        # 监督闭环:块A 改动统一登记 CHANGELOG(skill wc-incremental-update 要求,2026-06-13 起自动)
        try:
            from changelog_util import append_change
            append_change(os.path.dirname(f), td_dir,
                          block_a=[f"[近期状态] {added_row}: {row}"] +
                                  ([f"[⑦] +{added_notes}条本场伤停"] if added_notes else []),
                          sources=["macheta(Sofascore)", "WebSearch叙事补"],
                          note=f"integrate_match {match['home']} {sc} {match['away']}")
        except Exception as e:
            print(f"  ⚠️ CHANGELOG 记录失败:{e}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="单场赛后 raw JSON 路径")
    ap.add_argument("--ts", required=True, help="raw 留底时间戳 YYYY-MM-DD_HHMM")
    ap.add_argument("--today", required=True, help="今天 YYYY-MM-DD（防泄露基准）")
    ap.add_argument("--td", default="2026-06-10_0228", help="team_data 子目录（默认迭代版）")
    a = ap.parse_args()
    from naming_util import valid_ts, valid_asof
    valid_ts(a.ts); valid_ts(a.td); valid_asof(a.today)        # 命名规范强制(花名直接报错)
    integrate(json.load(open(a.raw, encoding="utf-8")), a.td, a.ts, a.today)


if __name__ == "__main__":
    main()
