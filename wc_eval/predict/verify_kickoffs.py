#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【开球时间核对 · 融进流程防再错】交叉核对三处的开球时间,挡住"西部时区场把美东时间算错"这类貌似合理的错值。
本类 bug 已犯两次(AUS-TUR 午夜 / 6-15 西雅图·亚特兰大),根因:FIX 表的【美东时间】是人工换算、对 PT/CT/MT 场易错。

三道核对:
  ① FIX(worldcup-app.js,网页显示源)↔ matches.json(kickoff_ts,预测prompt源)—— 两处美东时间必须一致;
  ② venue 城市 → 时区 → 反推【当地开球时刻】,落在合理档({11,12,13,14,15,18,19,21,22} 当地)外则告警;
  ③ 非美东(PT/CT/MT)场 —— 这类最易错,一律标"务必外部核对"(authoritative 赛程多源)。

⚠️ 自动核对挡不住"貌似合理的错值"(如西雅图 12pm↔3pm 都像真)——**最终防线仍是 agent 每轮 WebSearch 权威赛程核对**;
   本脚本把每天的场次连同 美东/当地/北京 三时间醒目打印,供 agent 对照,并对不一致/越界硬报错。

跑:python3 verify_kickoffs.py                      # 核对全部有 kickoff 的场
   python3 verify_kickoffs.py --date 2026-06-15    # 只核某日
   python3 verify_kickoffs.py --matches ESP-CPV,BEL-EGY
返回码:0=全过;非0=有不一致/越界(matchday 据此拦)。
"""
import os, re, json, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATCHES = f"{ROOT}/wc_runs/data_reference/matches.json"
WEB_APP = os.environ.get("WC_WEB_DIR") and f"{os.environ['WC_WEB_DIR']}/worldcup-app.js" \
    or f"{os.path.dirname(ROOT)}/worldcup_2026_web/site/worldcup-app.js"

# 美东相对各时区的偏移(ET 比当地早几小时):ET 同区=0,CT 慢1,MT 慢2,PT 慢3。当地 = 美东时刻 - offset。
CITY_TZ = {  # 网页 FIX 用的英文城市名 → 相对美东的小时差(当地 = ET - 值)
    # ET(0)
    "Miami": 0, "Atlanta": 0, "New York": 0, "Philadelphia": 0, "Boston": 0, "Toronto": 0,
    "East Rutherford": 0, "Foxborough": 0, "Nashville": 0,
    # CT(1)
    "Dallas": 1, "Houston": 1, "Kansas City": 1, "Monterrey": 1, "Mexico City": 1,
    "Guadalajara": 1, "Arlington": 1,
    # MT(2)
    "Denver": 2,
    # PT(3)
    "Los Angeles": 3, "Seattle": 3, "San Francisco": 3, "Santa Clara": 3, "Vancouver": 3, "Inglewood": 3,
}
# 世界杯北美赛程的常见【当地】开球档(小时);越界=可疑
SANE_LOCAL_HOURS = {11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22}


def parse_fix(path):
    """从 worldcup-app.js 解析 FIX 行 → [{date,grp,home_en,away_en,city_cn,city_en,et}]。"""
    t = open(path, encoding="utf-8").read()
    rows = []
    for m in re.finditer(r'\["(\d+\.\d+)","([^"]*)","([^"]+)","([^"]+)","([^"]*)","([^"]*)","([^"]*)"\]', t):
        d, grp, h, a, ccn, cen, et = m.groups()
        rows.append({"date": d, "grp": grp, "home": h, "away": a, "city_cn": ccn, "city_en": cen, "et": et})
    return rows


def et_to_local(et, city_en):
    off = CITY_TZ.get(city_en)
    if off is None or not re.match(r"^\d{1,2}:\d{2}$", et or ""):
        return None, off
    hh = int(et.split(":")[0])
    return (hh - off) % 24, off


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--matches", help="逗号分隔 A-B,..(FIFA码)")
    a = ap.parse_args()

    ms = json.load(open(MATCHES, encoding="utf-8"))
    # matches.json: (home_en? 用 FIFA 码) → 这里按 date+英队名对不上,改用 worldcup-app.js 的 NAME→码不可见;
    # 用 kickoff_ts 的小时(美东)做一致性核对,键 = (date, home_en, away_en) 经 FIX 的码映射。
    fix = parse_fix(WEB_APP)
    # 英队名 → FIFA 码(从 worldcup-app.js 的映射块解析)
    code = {}
    for m in re.finditer(r'"([^"]+)":"([A-Z]{3})"', open(WEB_APP, encoding="utf-8").read()):
        code[m.group(1)] = m.group(2)
    # matches.json 按 (date, A, B) 存 kickoff_ts(美东小时)
    mj = {}
    for m in ms:
        kt = m.get("kickoff_ts")
        hh = int(kt[11:13]) if kt and len(kt) >= 13 else None
        mj[(m.get("date"), m.get("team_a"), m.get("team_b"))] = hh

    want = None
    if a.matches:
        want = set(tuple(x.strip().split("-")) for x in a.matches.split(","))

    print("日期    组 对阵            场馆(城市)      美东   当地   北京   核对")
    print("─" * 78)
    issues, flags = [], []
    for r in fix:
        d_iso = "2026-" + r["date"].replace(".", "-").zfill(5).replace(".", "-")  # "6.15"→ rough
        # 规范 ISO 日期
        mo, dd = r["date"].split(".")
        d_iso = f"2026-{int(mo):02d}-{int(dd):02d}"
        hc, ac = code.get(r["home"]), code.get(r["away"])
        if a.date and d_iso != a.date:
            continue
        if want and (hc, ac) not in want:
            continue
        if not r["et"]:
            continue
        local, off = et_to_local(r["et"], r["city_en"])
        # 北京 = 美东 + 12(赛事期全程 EDT)
        ethh = int(r["et"].split(":")[0]); etmm = r["et"].split(":")[1]
        bj = f"{(ethh + 12) % 24:02d}:{etmm}"
        # ① 一致性:FIX 美东 vs matches.json 美东
        mjhh = mj.get((d_iso, hc, ac))
        consistent = (mjhh is None) or (mjhh == ethh)
        # ② 当地合理性
        sane = (local is None) or (local in SANE_LOCAL_HOURS)
        # ③ 非ET场标记
        nonet = off and off > 0
        tag = []
        if not consistent: tag.append(f"✗FIX≠matches({r['et']}vs{mjhh}:00)"); issues.append((hc, ac, "不一致"))
        if not sane: tag.append(f"✗当地{local}:00异常"); issues.append((hc, ac, "当地越界"))
        if nonet: tag.append("⚠非ET·务必外部核对"); flags.append((hc, ac, r["city_en"]))
        loc_s = f"{local:02d}:{etmm}" if local is not None else "  ?  "
        print(f"{d_iso} {r['grp']} {hc}-{ac:<3} {r['away'][:8]:<8} {r['city_en'][:12]:<12} {r['et']:>5}  {loc_s}  {bj}  {' '.join(tag) or '✓'}")

    print("─" * 78)
    if issues:
        print(f"❌ {len(issues)} 项硬问题(FIX↔matches 不一致 / 当地时间越界)——必须修正后再推。")
    if flags:
        print(f"⚠️  {len(flags)} 场在非美东时区(PT/CT/MT),最易把美东时间算错——"
              f"agent 务必用权威赛程(FIFA/CBS/Al Jazeera)外部核对当地↔美东换算。")
    if not issues and not flags:
        print("✅ 全部一致且在美东时区,低风险。")
    raise SystemExit(1 if issues else 0)


if __name__ == "__main__":
    main()
