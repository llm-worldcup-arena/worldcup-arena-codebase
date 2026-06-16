#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按统一模板，从已采集的 data + raw 自动生成每队 team_data/<ts>/<队>/summary.md。
—— 一份「以队伍为载体」的赛前背景资料，供 LLM 预测用；信息全部来自采集真值（raw 可回溯）。

数据来源（全部已采）：
  teams.json / snapshots(team_rank,squad) / persons.json / matches / venues / static(groups)
  + 维基队页 raw（世界杯荣誉、近期赛果）+ 维基球员页 raw（年龄/位置/国脚/俱乐部生涯）

跑：python3 gen_summary.py                 # 全 48 队
    python3 gen_summary.py --only ARG,BRA  # 指定队
    python3 gen_summary.py --ts 2026-06-08_2336   # 指定输出时间目录
"""
import os, re, glob, json, argparse
from collect_squads import (BASE, persons_path, teams_path, snap_path,
                            matches_path, venues_path, static_path, load_json)

ASOF = "2026-06-08"

POSZH = {"Goalkeeper":"门将","Left-back":"左后卫","Left back":"左后卫","Right-back":"右后卫","Right back":"右后卫",
    "Full-back":"边后卫","Full back":"边后卫","Wing-back":"翼卫","Centre-back":"中后卫","Center-back":"中后卫",
    "Defender":"后卫","Defensive midfielder":"后腰","Central midfielder":"中场","Centre midfielder":"中场",
    "Attacking midfielder":"前腰","Midfielder":"中场","Winger":"边锋","Forward":"前锋","Centre-forward":"中锋",
    "Striker":"中锋","Second striker":"影锋","GK":"门将","DF":"后卫","MF":"中场","FW":"前锋"}
CLUBZH = {"Atlético Madrid":"马竞","Inter Miami":"迈阿密","Inter Miami CF":"迈阿密","River Plate":"河床",
    "Boca Juniors":"博卡","Manchester United":"曼联","Manchester City":"曼城","Tottenham Hotspur":"热刺",
    "Liverpool":"利物浦","Chelsea":"切尔西","Inter Milan":"国米","Internazionale":"国米","Benfica":"本菲卡",
    "Bayer Leverkusen":"勒沃库森","Real Madrid":"皇马","Barcelona":"巴萨","Paris Saint-Germain":"PSG",
    "Juventus":"尤文","Ajax":"阿贾克斯","Bayern Munich":"拜仁","Borussia Dortmund":"多特"}

def cz(c): return CLUBZH.get((c or "").strip(), c)
def pz(p):
    p = (p or "").strip()
    return POSZH.get(p) or next((v for k, v in POSZH.items() if k.lower() == p.lower()), p)
FOOTZH = {"left": "左", "right": "右", "both": "双"}

# 繁→简：name_zh 多为维基港译繁体，统一成大陆简体（两串等长一一对应；不等长则守卫为空、不崩）
_FAN = "於萬韓們價諾納爾盧裡圖達蘭維內喬費蓋凱蘇雲衛國後門陽陳隊雙韋頓風飛馮聖賓奧薩貝華澤約瑟羅魯賴遜齊歷麗麥錫鋒鐘銀長開關陸際隨靈靜顯驚體龍億傑傳優兒黃緊紐歐寧緹瑪現產畫異監盡確禮種積稱窮築節範糧級紀紅純細終組結給絡統絲經綠綱網緒線編緩縣縮績繼續罷義習聞聯聰職聽腳膚臨興艦藍藥蟲術補裝製複見視覺觀觸訂計討訓記訪設許訴診註評詞試詩話該詳認語誤說請諸課調談論謝識譜譯議護讀變讓豐財貨責貴買賀資賜賞賠賢賣質贊贏趕趙跡踐蹤車軌軍軒軟較載輔輕輛輝輩輪輸轉農遲遷遺遼邏鄉鄭釋鋼錄錢錯鍵鎖鏡鐵鑑閃閉閏間閘閣閱闆闊闖闢隔障險隱隴雕雖雜離雲電零響頁頂項順須預領頭頻顆題願類顧風飄飯飲養餓館駐駕騎驕骨鬆鬥鮮鳥鳳鴻點黨齒龐"
_JIAN = "于万韩们价诺纳尔卢里图达兰维内乔费盖凯苏云卫国后门阳陈队双韦顿风飞冯圣宾奥萨贝华泽约瑟罗鲁赖逊齐历丽麦锡锋钟银长开关陆际随灵静显惊体龙亿杰传优儿黄紧纽欧宁缇玛现产画异监尽确礼种积称穷筑节范粮级纪红纯细终组结给络统丝经绿纲网绪线编缓县缩绩继续罢义习闻联聪职听脚肤临兴舰蓝药虫术补装制复见视觉观触订计讨训记访设许诉诊注评词试诗话该详认语误说请诸课调谈论谢识谱译议护读变让丰财货责贵买贺资赐赏赔贤卖质赞赢赶赵迹践踪车轨军轩软较载辅轻辆辉辈轮输转农迟迁遗辽逻乡郑释钢录钱错键锁镜铁鉴闪闭闰间闸阁阅板阔闯辟隔障险隐陇雕虽杂离云电零响页顶项顺须预领头频颗题愿类顾风飘饭饮养饿馆驻驾骑骄骨松斗鲜鸟凤鸿点党齿庞"
FANJIAN = str.maketrans(_FAN, _JIAN) if len(_FAN) == len(_JIAN) else {}

def strip_cell(s):
    """单元格统一兜底清洗：去 <ref>/{{模板}}/[[wiki]]/<html>/height残留/位置#，残留 | 转 / 防破列。"""
    s = str(s if s is not None else "")
    s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/?>", "", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+?)\]\]", r"\1", s)              # [[A|B]]→B、[[B]]→B
    s = s.replace("[[", "").replace("]]", "")                            # 残缺括号兜底
    s = re.sub(r"\s*\(association football\)\s*", " ", s)                # 去消歧义后缀
    s = re.sub(r"[／/]?\s*height\s*=\s*[\d.]+\s*m\b", "", s, flags=re.I)     # 去串进来的 height
    s = re.sub(r"^[A-Za-z][\w\s'’\-]*#\s*", "", s)                       # 位置 Defender#Centre-back → Centre-back
    s = re.sub(r"<[^>]+>", "", s).replace("|", "/")
    s = s.translate(FANJIAN)                                             # 繁→简（港译繁体统一成简体）
    return re.sub(r"\s+", " ", s).strip() or "—"

def wiki_raw_dir():
    """最近一次含队页整页全文的 raw 目录。"""
    ds = sorted(glob.glob(f"{BASE}/data_raw/*/"), reverse=True)
    for d in ds:
        if glob.glob(d + "[A-Z][A-Z][A-Z].wikitext"):
            return d.rstrip("/")
    return None

# ---------- 球员页 raw 解析（年龄/细分位置/国脚/俱乐部生涯） ----------
def player_extra(wt):
    m = re.search(r'birth\s+date(?:\s+and\s+age)?\s*\|\s*(?:df=ye?s?\s*\|\s*)?(\d{4})\|(\d{1,2})\|(\d{1,2})', wt, re.I)
    age = 2026 - int(m.group(1)) - ((6,11) < (int(m.group(2)), int(m.group(3)))) if m else None
    pm = re.search(r'\|\s*position\s*=\s*(.+)', wt); pos = None
    if pm:
        s = re.sub(r'\{\{\s*hlist\s*\|([^}]*)\}\}', lambda m: m.group(1).split('|')[0], pm.group(1))  # {{hlist|A|B}}→A
        s = re.sub(r'\{\{[^{}]*\}\}', '', s)                                  # 去其他模板(efn/tooltip…)
        s = re.sub(r'<ref[^>]*>.*?</ref>|<ref[^>]*/?>|<!--.*?-->', '', s)
        pos = re.sub(r'\[\[([^\]|]*\|)?([^\]]+)\]\]', r'\2', s).strip().rstrip('|').split(',')[0].strip()
    nat = None
    for i in range(1, 9):
        tm = re.search(rf'\|\s*nationalteam{i}\s*=\s*(.+)', wt)
        if not tm or re.search(r'U-?\d|under-?\d|Olympic', tm.group(1), re.I): continue
        cm = re.search(rf'\|\s*nationalcaps{i}\s*=\s*(?:\[\[[^\]]*\|)?(\d+)', wt)
        gm = re.search(rf'\|\s*nationalgoals{i}\s*=\s*(?:\[\[[^\]]*\|)?(\d+)', wt)
        if cm: nat = f"{cm.group(1)}/{gm.group(1) if gm else '?'}"
    return age, pz(pos) if pos else "—", nat or "—"

def player_career(wt):
    out = []
    for i in range(1, 16):
        c = re.search(rf'\|\s*clubs{i}\s*=\s*(.+)', wt)
        if not c: continue
        val = re.sub(r'<ref[^>]*>.*?</ref>|<ref[^>]*/?>', '', c.group(1))                              # 去引用
        val = re.sub(r'\s*\|\s*(?:caps|goals|years|youthclubs|youthyears)\d*\s*=.*$', '', val)         # 去同行 caps/goals 残留
        name = re.sub(r'\[\[([^\]|]*\|)?([^\]]+)\]\]', r'\2', val).strip()
        if not name or 'loan' in name.lower(): continue
        cap = re.search(rf'\|\s*caps{i}\s*=\s*(\d+)', wt); go = re.search(rf'\|\s*goals{i}\s*=\s*(\d+)', wt)
        out.append(f"{cz(name)}({cap.group(1) if cap else '?'}/{go.group(1) if go else '?'})")
    return "→".join(out) if out else "—"

# ---------- 队页 raw 解析（世界杯荣誉 / 近期赛果） ----------
def parse_wc_honours(wt):
    m = re.search(r"'''\[\[FIFA World Cup\]\]'''(.*?)(?:\n\s*\*\s'''|\n==)", wt, re.S)
    seg = m.group(1) if m else ""
    def grab(label):
        mm = re.search(label + r"\s*\((\d+)\)[^\n]*", seg)
        if not mm: return None, []
        yrs = list(dict.fromkeys(re.findall(r"\|(\d{4})\]\]", mm.group(0)) or re.findall(r"(19\d\d|20\d\d)", mm.group(0))))
        return int(mm.group(1)), yrs
    cn, cy = grab(r"Champions"); rn, ry = grab(r"Runners-up")
    return {"title_n": cn, "title_y": cy, "runner_n": rn, "runner_y": ry}

def parse_recent(wt, code, n=6):
    out = []
    for b in re.findall(r"\{\{Football box collapsible(.*?)\n\}\}", wt, re.S):
        t1 = re.search(r"\|\s*team1\s*=.*?\|([A-Z]{3})\s*\}\}", b)
        t2 = re.search(r"\|\s*team2\s*=.*?\|([A-Z]{3})\s*\}\}", b)
        sc = re.search(r"\|\s*score\s*=\s*([0-9]+\s*[–-]\s*[0-9]+)", b)
        rs = re.search(r"\|\s*result\s*=\s*([WDL])", b)
        dt = re.search(r"\|\s*date\s*=\s*(\d{1,2}\s+[A-Z][a-z]+(?:\s+\d{4})?|[A-Z][a-z]+\s+\d{1,2}(?:,?\s*\d{4})?)", b)  # 认 '28 March' 和美式 'March 28'
        if not (t1 and t2 and sc): continue
        opp = t2.group(1) if t1.group(1) == code else t1.group(1)
        ha = "主" if t1.group(1) == code else "客"
        out.append(f"{(dt.group(1).strip() if dt else '?'):<16} {ha} vs {opp} {sc.group(1).replace(' ','')}{('('+rs.group(1)+')') if rs else ''}")
    return out[-n:]

# ---------- 生成 ----------
def gen(code, teams, rank, squad, persons, matches, venues, groups, wikidir):
    t = teams.get(code, {}); rk = rank.get(code, {}) or {}
    name_zh = t.get("name_zh") or code
    qpath = f"{wikidir}/{code}.wikitext"
    wt = open(qpath, encoding="utf-8").read() if os.path.exists(qpath) else ""
    hon = parse_wc_honours(wt); recent = parse_recent(wt, code)
    coach = persons.get(t.get("coach_id"), {})
    grp = next((g for g, mem in groups.items() if code in mem), None)
    mates = [m for m in (groups.get(grp, []) if grp else []) if m != code]
    L = []
    L.append(f"# {name_zh}（{t.get('name_en', code)}） — 2026 世界杯背景资料")
    L.append("（赛前资料，供预测使用；以维基/采集真值为准，含截至**预测时点**的公开信息；**仅排除「本场及本场之后比赛」的结果**——本场之前的真实赛果(热身赛/预选赛/早先小组赛等)属合法赛前信息、予以保留；可回溯 raw）\n")
    # 速览
    q = t.get("qualifying") or {}
    L.append("## 速览")
    L.append(f"- 队名 {name_zh}（{t.get('name_en',code)}）｜FIFA码 {code}｜{t.get('confederation','?')}"
             f"｜绰号 {re.sub(chr(40)+'[^'+chr(41)+']*'+chr(41),'',t.get('nickname') or '').split('/')[0].strip() or '—'}｜成立 {t.get('founded','—')}")
    L.append(f"- FIFA 排名 **{rk.get('fifa_rank','—')}**（{rk.get('fifa_asof','')}）｜Elo **{rk.get('elo','—')}**")
    if hon["title_n"]: L.append(f"- 世界杯 **{hon['title_n']} 冠**（{', '.join(hon['title_y'])}）" +
                                (f"、{hon['runner_n']} 亚（{', '.join(hon['runner_y'])}）" if hon['runner_n'] else ""))
    if grp: L.append(f"- 本届 **{grp} 组**，同组 {', '.join(mates)}")
    if q: L.append(f"- 预选赛 {q.get('played','?')} 战 {q.get('won','?')} 胜 {q.get('drawn','?')} 平 {q.get('lost','?')} 负"
                   f"，进 {q.get('gf','?')} 失 {q.get('ga','?')}")
    if coach: L.append(f"- 主帅 {coach.get('name_zh') or coach.get('name_en','—')}")
    # 世界杯战绩
    if hon["title_n"] or hon["runner_n"]:
        L.append("\n## 世界杯战绩")
        if hon["title_n"]: L.append(f"- 冠军 {hon['title_n']} 次：{', '.join(hon['title_y'])}")
        if hon["runner_n"]: L.append(f"- 亚军 {hon['runner_n']} 次：{', '.join(hon['runner_y'])}")
    # 近期状态
    if recent or q:
        L.append("\n## 近期状态")
        if q: L.append(f"- 本届预选赛（{t.get('confederation','')}）：{q.get('played','?')} 战 "
                       f"{q.get('won','?')} 胜 {q.get('drawn','?')} 平 {q.get('lost','?')} 负，"
                       f"进 {q.get('gf','?')} 失 {q.get('ga','?')}，净胜 {(q.get('gf') or 0)-(q.get('ga') or 0):+d}")
        if recent:
            L.append(f"- 近 {len(recent)} 场：")
            for r in recent: L.append(f"  - {r}")
    # 本届征程
    tm_matches = sorted([m for m in matches if code in (m.get("team_a"), m.get("team_b"))], key=lambda m: m.get("date") or "")
    if tm_matches:
        L.append("\n## 本届征程（小组赛）")
        L.append("| 日期 | 对手 | 球场 | 城市 |")
        L.append("|---|---|---|---|")
        for m in tm_matches:
            opp = m["team_b"] if m["team_a"] == code else m["team_a"]
            v = venues.get(m.get("venue_id"), {})
            L.append(f"| {m.get('date','')} | {opp or '?'} | {v.get('name','?')} | {v.get('city','?')} |")
    # 阵容全名单
    sq = (squad.get(code) or {}).get("players", [])
    if sq:
        L.append(f"\n## 阵容全名单（{len([p for p in sq if (p.get('no') or 99)<=26])} 人）")
        L.append("> 号·位置·姓名·全名·年龄·身高·脚·国脚(场/球)·身价·合同·双国籍·加盟现队·俱乐部生涯(出场/进球)·出生地（采集真值；身价/身高/脚/合同/国籍来自 Transfermarkt，缺=未采）\n")
        L.append("| 号 | 位置 | 姓名 | 全名 | 年龄 | 身高 | 脚 | 国脚 | 身价 | 合同 | 双国籍 | 加盟现队 | 俱乐部生涯 | 出生地 |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for pl in sorted(sq, key=lambda x: x.get("no") or 99):
            no = pl.get("no") or 99
            if no > 26: continue
            p = persons.get(pl["person_id"], {}); pp = p.get("player", {}) if isinstance(p.get("player"), dict) else {}
            f = f"{wikidir}/player_{pl['person_id']}.wikitext"
            pwt = open(f, encoding="utf-8").read() if os.path.exists(f) else ""
            age, pos, nat = player_extra(pwt) if pwt else (None, pz(pp.get("position")), f"{pp.get('intl_caps','—')}/{pp.get('intl_goals','—')}")
            car = player_career(pwt) if pwt else "—"
            if p.get("birthdate") and re.match(r"\d{4}-\d{2}-\d{2}$", p["birthdate"]):   # 年龄一律用核对过的生日(wikitext 可能是同名搜错的人)
                yy, mm, dd = map(int, p["birthdate"].split("-")); age = 2026 - yy - ((mm, dd) > (6, 9))
            if pp.get("position_verified"): pos = pp["position_verified"]               # 同名搜错→用核实位置
            if pp.get("club_verified"): car = f"现效力 {pp['club_verified']}"           # 同名搜错→wikitext生涯不可靠,用核实的现俱乐部
            if pp.get("intl_caps_verified") is not None:                                # 同名搜错→用核实的国脚出场数据
                nat = f"{pp['intl_caps_verified']}/{pp.get('intl_goals_verified', 0)}"
            zh = strip_cell(p.get("name_zh") or p.get("name_en", "?"))
            birth = strip_cell((p.get("birth_place") or "—").split(",")[0])
            full = strip_cell(p.get("full_name") or p.get("name_en") or "—")
            mv = pp.get("market_value_eur")
            mvs = ("—⚠️" if pp.get("tm_verified") is False else "—" if not mv else
                   f"{mv/1e8:.2f}亿€" if mv >= 1e8 else f"{mv/1e6:.0f}M€" if mv >= 1e6 else f"{mv/1e3:.0f}K€")
            h = pp.get("height_cm_verified") or pp.get("tm_height_cm") or pp.get("height_cm") or "—"  # 独立源核对值 > TM > 维基
            foot = FOOTZH.get(pp.get("foot"), "—")                       # 惯用脚(TM)
            contract = pp.get("contract_until") or "—"                       # 合同到期(TM)
            natdual = strip_cell(pp.get("nationality_tm") or "—")            # 双国籍(TM)
            joined = strip_cell(pp.get("tm_club_join") or "—")              # 加盟现队日期(TM)
            L.append(f"| {no} | {pz(strip_cell(pos))} | {zh} | {full} | {age or '—'} | {h} | {foot} | {nat} | {mvs} | {contract} | {natdual} | {joined} | {strip_cell(car)} | {birth} |")
    return "\n".join(L) + "\n"   # 补充档案已并入主表(14列)，不再单出一张表

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只生成某队，逗号分隔")
    ap.add_argument("--ts", default="2026-06-08_2336", help="输出 team_data 时间目录")
    args = ap.parse_args()
    from naming_util import valid_ts
    valid_ts(args.ts)   # 命名规范强制
    only = {c.strip().upper() for c in args.only.split(",")} if args.only else None

    teams = {t["team_id"]: t for t in load_json(teams_path(), [])}
    rank = load_json(snap_path(ASOF, "team_rank"), {})
    squad = load_json(snap_path(ASOF, "squad"), {})
    persons = {p["person_id"]: p for p in load_json(persons_path(), [])}
    matches = load_json(matches_path(), [])
    venues = load_json(venues_path(), {})
    groups = load_json(static_path("groups"), {})
    wikidir = wiki_raw_dir()
    outbase = f"{BASE}/team_data/{args.ts}"

    codes = [c for c in sorted(teams) if not only or c in only]
    print(f"=== 生成 summary  {len(codes)} 队  → team_data/{args.ts}/<队>/summary.md ===")
    for code in codes:
        md = gen(code, teams, rank, squad, persons, matches, venues, groups, wikidir)
        d = f"{outbase}/{code}"; os.makedirs(d, exist_ok=True)
        open(f"{d}/summary.md", "w", encoding="utf-8").write(md)
        zh = len(re.findall(r'[一-鿿]', md))
        print(f"  [{code}] {teams[code].get('name_zh') or code}  {zh}字")
    print(f"\n完成 {len(codes)} 队")

if __name__ == "__main__":
    main()
