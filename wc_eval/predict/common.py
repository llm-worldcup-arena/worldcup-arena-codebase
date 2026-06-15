#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预测公共件:读 summary / 调 6 模型(DMXAPI)/ 解析 JSON / 存预测。被 predict_match / group / global 共用。

🚨 真正跑模型前必须先向用户汇报(见 skill wc-predict / 记忆 feedback-eval-report-first)。
"""
import os, sys, json, re, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 让 import llm_client（在 wc_eval/）
from llm_client import chat, chat_search

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 仓库根(可移植,不再硬编码)
PRED_DIR = f"{ROOT}/wc_eval/predict"


def load_models():
    """6 家旗舰评测对象。"""
    return json.load(open(f"{PRED_DIR}/models.json", encoding="utf-8"))["models"]


def read_summary(team, snapshot):
    """读某队某快照的 summary 全文（赛前/当轮干净版，本身防泄露）。单场/头名喂这个(完整)。"""
    f = f"{ROOT}/wc_runs/team_data/{snapshot}/{team}/summary.md"
    return open(f, encoding="utf-8").read() if os.path.exists(f) else f"（缺 {team} summary）"


# ── 全局预测用:从 summary 抽球队层面的几段，去掉 ⑤阵容全名单(5000+字细节)等，压到能喂 48 队 ──
_SECTION_PATS = {
    "速览": r"## 速览.*?(?=\n## )", "①": r"## ① .*?(?=\n## )", "②": r"## ② .*?(?=\n## )",
    "③": r"## ③ .*?(?=\n## )", "⑥": r"## ⑥ .*?(?=\n## )", "⑦": r"## ⑦ .*?(?=\n## )",
    "⑧": r"## ⑧ .*?(?=\n## )", "市值": r"## 球队市值.*?(?=\n## |\Z)", "近期": r"## 近期状态.*?(?=\n## )",
}


def extract_brief(summary, sections=("速览", "市值"), brief=("⑧", "⑦", "②", "③", "⑥"), brief_chars=200):
    """抽几段拼「全局速览」。
    sections=**整段**取(速览+⑦动态+⑧定位+市值);
    brief=**只取精华**(段标题+前 brief_chars 字)——给全局补 ②夺冠底蕴 / ③近期 / ⑥球星身价 而不爆 token。
    默认 ~2500 字/队,48 队控制在 GLM(128k)能放下。"""
    parts = []
    for s in sections:
        m = re.search(_SECTION_PATS.get(s, "(?!)"), summary, re.S)
        if m:
            parts.append(m.group(0).strip())
    for s in (brief or ()):
        m = re.search(_SECTION_PATS.get(s, "(?!)"), summary, re.S)
        if m:
            seg = m.group(0).strip()
            head = seg.split("\n", 1)[0]
            body = seg[len(head):].strip()
            parts.append(f"{head}\n{body[:brief_chars]}…" if len(body) > brief_chars else seg)
    return "\n\n".join(parts) or summary[:1500]   # 兜底:抽不到就截前 1500 字


def load_groups():
    """12 组分组 {A:[FIFA码...]}。优先 bg/static/groups.json，没有则空。"""
    for p in (f"{ROOT}/wc_runs/data_reference/static/groups.json", f"{ROOT}/wc_runs/data_reference/static/groups.json"):
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return {}


def load_matches():
    """赛程 matches.json(每场 date/round/group/venue_id/team_a/team_b/result)。"""
    p = f"{ROOT}/wc_runs/data_reference/matches.json"
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


_HOSTS = {"MEX", "USA", "CAN"}                                        # 2026 三东道主
_MX_CITY = {"Mexico City", "Guadalajara", "Zapopan", "Monterrey"}
_CA_CITY = {"Toronto", "Vancouver"}
_ROUND_CN = {"group": "小组赛", "r32": "32 强", "r16": "16 强", "qf": "1/4 决赛", "sf": "半决赛", "final": "决赛"}


def _kickoff_line(kts):
    """kickoff_ts(ISO,美东) → '开球:美东 6-11 15:00 / 北京 6-12 03:00'。空则空串。"""
    if not kts:
        return ""
    from datetime import datetime, timedelta
    try:
        dt = datetime.fromisoformat(kts)                 # 带 -04:00(美东 EDT)
    except ValueError:
        return ""
    bj = dt + timedelta(hours=12)                        # 北京 UTC+8 = 美东 EDT(UTC-4) + 12h
    return f"开球:美东 {dt.strftime('%-m-%d %H:%M')} / 北京 {bj.strftime('%-m-%d %H:%M')}"


def match_header(home, away):
    """比赛抬头:严格指定这场(赛事/阶段/组/日期/开球时间/场馆/海拔/主客/真主场 or 中立)。从 matches.json 读。"""
    mt = next((m for m in load_matches() if m.get("team_a") == home and m.get("team_b") == away), None)
    if not mt:
        return f"2026 世界杯 · 主队 {home} vs 客队 {away}(赛果未出,预测)"
    venues = json.load(open(f"{ROOT}/wc_runs/data_reference/venues.json", encoding="utf-8"))
    v = venues.get(mt.get("venue_id"), {})
    vname, vcity = v.get("name", "?"), v.get("city", "?")
    rd = _ROUND_CN.get(mt.get("round"), mt.get("round", ""))
    grp = f"{mt.get('group')} 组 · " if mt.get("group") else ""
    vcountry = "MEX" if vcity in _MX_CITY else "CAN" if vcity in _CA_CITY else "USA"
    if home in _HOSTS and vcountry == home:
        site = f"{vname}({vcity})—— {home} 为东道主、享真实主场之利"
    else:
        site = f"{vname}({vcity},中立场地)—— 双方均非本场东道主,名义主队 {home} 无真实主场加成"
    alt = v.get("altitude_m")
    alt_str = f" · 海拔 {alt}m{'(高原,影响体能/球速)' if isinstance(alt, (int, float)) and alt >= 1500 else ''}" if alt else ""
    ko = _kickoff_line(mt.get("kickoff_ts"))
    ko_line = f"{ko}\n" if ko else ""
    slug = f"{mt.get('date', '')}_{home}_vs_{away}"
    env_line = _env_line(slug, v.get("roof"))
    coach_line = _coach_line(home, away)
    rb = _referee_brief(slug)
    ref_block = f"主裁执法风格:\n{rb}\n" if rb else ""
    # 已结束与否查现实档案 results.json(赛果单一真源;matches.json 是赛程参考、不双存赛果)
    try:
        _res = json.load(open(f"{ROOT}/wc_runs/archive/results.json", encoding="utf-8"))["matches"].get(f"{home}_vs_{away}")
    except Exception:
        _res = None
    status = "本场已结束" if (_res or mt.get("result") is not None) else "本场尚未开打(预测即将进行的这一场)"
    return (f"2026 世界杯 · {rd} · {grp}{mt.get('date', '')}\n"
            f"{ko_line}"
            f"场地:{site}{alt_str}\n"
            f"{env_line}"
            f"{coach_line}"
            f"{ref_block}"
            f"主队 {home} vs 客队 {away} · {status}")


def _referee(slug):
    """读独立成熟仓库 data_processed/match_referee/<slug>.json(与 team_coach 同规格);回退 match_env。返回 referee dict。"""
    for p in (f"{ROOT}/wc_runs/data_processed/match_referee/{slug}.json",
              f"{ROOT}/wc_runs/data_processed/match_env/{slug}.json"):
        if os.path.exists(p):
            try:
                d = json.load(open(p, encoding="utf-8"))
                ref = d.get("referee") or {}
                # match_referee:brief 在顶层;match_env:brief 在 referee 内
                if "brief" in d and "brief" not in ref:
                    ref = {**ref, "brief": d.get("brief", "")}
                if ref.get("name"):
                    return ref
            except Exception:
                pass
    return {}


def _referee_brief(slug):
    return (_referee(slug).get("brief") or "").strip()


def coach_brief_text(team):
    """该队主帅可读简介(coach_enrich.py py-Kimi 生成,存 team_coach/<队>.json 的 brief)。无则空串。"""
    p = f"{ROOT}/wc_runs/data_processed/team_coach/{team}.json"
    if os.path.exists(p):
        try:
            b = (json.load(open(p, encoding="utf-8")) or {}).get("brief")
            return b.strip() if b else ""
        except Exception:
            pass
    return ""


def _coach_line(home, away):
    """主帅对位行:优先读成熟仓库 data_processed/team_coach/<队>.json(collect_team_coach.py 双写,
    含世界杯期间换帅更新);缺则回退 data_reference(teams.coach_id→persons)。无则空串。"""
    def nm(tid):
        p = f"{ROOT}/wc_runs/data_processed/team_coach/{tid}.json"
        if os.path.exists(p):
            try:
                c = json.load(open(p, encoding="utf-8")).get("coach") or {}
                return c.get("name") or c.get("name_zh") or c.get("name_en")
            except Exception:
                pass
        return None
    try:
        h, a = nm(home), nm(away)
        if not (h and a):                                    # 回退基础参考
            ts = {t["team_id"]: t.get("coach_id") for t in
                  json.load(open(f"{ROOT}/wc_runs/data_reference/teams.json", encoding="utf-8"))}
            ps = {p["person_id"]: p for p in
                  json.load(open(f"{ROOT}/wc_runs/data_reference/persons.json", encoding="utf-8"))}
            def ref_nm(tid):
                p = ps.get(ts.get(tid) or "")
                return (p.get("name_zh") or p.get("name_en")) if p else None
            h, a = h or ref_nm(home), a or ref_nm(away)
        return f"主帅:{home} {h} vs {away} {a}\n" if h and a else ""
    except Exception:
        return ""


def _env_line(slug, roof=None):
    """环境行:天气读 data_processed/match_env/<slug>.json;主裁读独立仓库 data_processed/match_referee/(回退 env)。无则空串。"""
    parts = []
    p = f"{ROOT}/wc_runs/data_processed/match_env/{slug}.json"
    if os.path.exists(p):
        try:
            wx = ((json.load(open(p, encoding="utf-8")).get("weather") or {}).get("开球时段"))
            if wx:
                w = (f"天气(开球时段):{wx.get('天况')} {wx.get('温度C')}°C(体感{wx.get('体感C')}°C) · "
                     f"降水概率{wx.get('降水概率%')}% · 风{wx.get('风速kmh')}km/h · 湿度{wx.get('湿度%')}%")
                if roof in ("retractable", "fixed-canopy"):
                    w += "(场馆带顶棚,天气影响有限)"
                parts.append(w)
        except Exception:
            pass
    rf = _referee(slug)        # 主裁来自独立成熟仓库 match_referee/
    if rf.get("name"):
        parts.append(f"主裁:{rf['name']}" + (f" · VAR:{rf['var']}" if rf.get("var") else ""))
    return ("环境:" + " | ".join(parts) + "\n") if parts else ""


# 亚洲让球盘:固定盘口(主队让球数,负 = 主队让球)。来源:多方赔率核对。
# 让球是市场给定的一条线,模型只预测「该线下 主胜盘 / 走盘 / 客胜盘」—— 不是自选盘口。
_HANDICAP = {
    ("MEX", "RSA"): -1.0,    # 墨西哥 -1(阿兹特克主场;Yahoo / BoyleSports 主 -1)
    ("KOR", "CZE"): -0.5,    # 韩国 -0.5(ESPN spread 韩 -0.5)
    ("CAN", "BIH"): -0.5,    # 加拿大 -0.5(主场;ESPN / SportsGambler 加 -0.5)
    ("USA", "PAR"): -0.5,    # 美国 -0.5(主场;ESPN / FanDuel 美 -0.5)
    # —— 6/13(多源核对 2026-06-13;正值=主队受让) ——
    ("BRA", "MAR"): -0.5,    # 巴西 -0.5(bet365 -175 / OddsShark / Covers 明示 Brazil -0.5)
    ("QAT", "SUI"): +1.0,    # 瑞士(客)让 1(ML 瑞 -425 vs 卡 +1400 悬殊,常规对应客让1;Covers/oddschecker)
    ("HAI", "SCO"): +0.5,    # 苏格兰(客)让 0.5(ML 苏 -175,与 BRA -175→-0.5 同价位;Covers)
    ("AUS", "TUR"): +0.5,    # 土耳其(客)让 0.5(ML 土 -135 小幅优势,1/4盘归整为半球;Covers)
    # —— 6/14(多源核对 2026-06-14) ——
    ("GER", "CUW"): -2.5,    # 德国 -2.5(库拉索最小参赛国;AH 市场 -2.5至-3.5,取-2.5评分线;LiveScore/CBS/ESPN)
    ("CIV", "ECU"): +0.5,    # 厄瓜多尔(客)让 0.5(ML 厄 +135 微favorite vs 科特迪瓦 +270;ECU -0.5 goal line -130;CBS/oddspedia)
    ("NED", "JPN"): -0.5,    # 荷兰 -0.5(AH 荷 -0.5 -104/-115;ESPN/Yahoo/Covers)
    ("SWE", "TUN"): -0.5,    # 瑞典 -0.5(ML 瑞 -115;AH 瑞 -0.5 -119;ESPN/Covers/Lineups)
    # —— 6/15(多源核对 2026-06-15) ——
    ("KSA", "URU"): +1.0,    # 乌拉圭(客)让1(URU -220 ML / AH -1.25,取整1评分线;OddsShark/SportsLine/ESPN)
    ("ESP", "CPV"): -2.0,    # 西班牙 -2(ESP -1250 ML 巨热 vs CPV首秀;WH -2@17/20,区间-1.5~-2.5;FOX/CBS)
    ("IRN", "NZL"): -0.5,    # 伊朗 -0.5(IRN -118/-120 ML 小热;FanDuel/bet365/ESPN)
    ("BEL", "EGY"): -0.5,    # 比利时 -0.5(BEL -150 ML;bet365/FOX/Ladbrokes)
}


def match_handicap(home, away):
    """本场固定让球盘口(主队让球数,负 = 主队让球)。None = 未定(前端用公式兜底)。"""
    return _HANDICAP.get((home, away))


def handicap_clause(home, away):
    """让球 prompt 说明:固定盘口 + 主胜盘/走盘/客胜盘 判定。
    h<0 = 主队让球;h>0 = 主队受让(即客队让球,客强主弱场景)。"""
    h = match_handicap(home, away)
    if h is None:
        return None
    ab = abs(h); need = int(ab) + 1
    if h < 0:                                            # 主队让球
        if ab == int(ab):                                # 整数盘:有走盘
            return (f"本场亚洲让球盘固定盘口:{home}(主)让 {int(ab)} 球。"
                    f"判定:{home} 净胜 ≥ {need} 球 →「主胜盘」;正好净胜 {int(ab)} 球 →「走盘」;打平或输 →「客胜盘」。")
        return (f"本场亚洲让球盘固定盘口:{home}(主)让 {ab} 球(半球盘,无走盘)。"
                f"判定:{home} 净胜 ≥ {need} 球 →「主胜盘」;否则 →「客胜盘」。")
    # 主队受让(客队让球)
    if ab == int(ab):                                    # 整数盘:有走盘
        return (f"本场亚洲让球盘固定盘口:{away}(客)让 {int(ab)} 球(即 {home} 受让)。"
                f"判定:{away} 净胜 ≥ {need} 球 →「客胜盘」;正好净胜 {int(ab)} 球 →「走盘」;打平或 {home} 赢 →「主胜盘」。")
    return (f"本场亚洲让球盘固定盘口:{away}(客)让 {ab} 球(半球盘,无走盘;即 {home} 受让)。"
            f"判定:{away} 净胜 ≥ {need} 球 →「客胜盘」;否则({away} 小胜不足/平/负)→「主胜盘」。")


def _search_ids():
    """models.json 里 search=true 的模型(经 DMXAPI 可真联网,见 llm_client.chat_search)。"""
    try:
        return {m["id"] for m in load_models() if m.get("search")}
    except Exception:
        return set()


def _extract_last_json(txt):
    """扫描文本里所有【括号配对平衡】的 {...} 块(支持嵌套、忽略字符串内的花括号),返回最后一个能 json.loads 的。
    比旧的 re.findall(r"\\{[^{}]*\\}") 健壮:旧版只吃扁平 JSON,模型一旦返回嵌套结构就误抓、贪婪兜底还会吞进分析文字。"""
    objs, depth, start, in_str, esc = [], 0, -1, False, False
    for i, ch in enumerate(txt):
        if in_str:                                   # 字符串内:只处理转义与收尾引号,花括号不计深度
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                objs.append(txt[start:i + 1])
    for c in reversed(objs):                         # 答案 JSON 通常在末尾 → 从后往前取第一个能解析的
        try:
            return json.loads(c)
        except Exception:
            continue
    return None


def _clean_values(obj):
    """入库前清洗:去掉模型抄进答案的括号提示(如"双（全场总进球数）"→"双")与首尾空白。
    治本——脏值进档案会让 score.py 精确匹配静默判错、与前端解析不一致(GPT单双那个缺口)。"""
    if isinstance(obj, str):
        return re.sub(r"[（(].*?[)）]", "", obj).strip()
    if isinstance(obj, list):
        return [_clean_values(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _clean_values(v) for k, v in obj.items()}
    return obj


def ask_json(model_id, system, user, retries=2, temperature=0.3):
    """调 LLM 要结构化 JSON。模型可先分析、最后给 JSON → 抓【最后一个】能解析的 JSON 对象。失败重试。
    models.json 标 search=true 的模型自动走联网搜索通道(chat_search),其余闭卷(chat)。
    返回 {"_json": dict, "_raw": 全文, "_search": bool}(_json 已清洗括号尾巴/空白,杜绝脏值)。失败返回 None。"""
    use_search = model_id in _search_ids()
    if use_search:                       # 明告模型有真搜索工具,鼓励主动用(光在 prompt 里说"可以搜"并不会真联网)
        system = "你已接入实时联网搜索工具,可主动搜索最新信息(伤停/状态/赔率/赛果等)辅助判断。\n" + system
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for _ in range(retries + 1):
        try:
            if use_search:
                txt = chat_search(msgs, model=model_id, temperature=temperature, timeout=480)
            else:
                txt = chat(msgs, model=model_id, temperature=temperature,
                           timeout=300, reasoning_effort="high")  # thinking 拉满 high 档(实测均可传)
            obj = _extract_last_json(txt)            # 括号配对抽取(支持嵌套,见 _extract_last_json)
            if obj is not None:
                return {"_json": _clean_values(obj), "_raw": txt.strip(), "_search": use_search}   # 入库前清洗脏值
        except Exception as e:
            print(f"      {model_id} 失败: {str(e)[:60]}")
    return None


_BATCH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}$")     # 批次命名铁规:YYYY-MM-DD_HHMM


def run_ts(override=None):
    """预测批次时间戳,**标准格式 YYYY-MM-DD_HHMM**(精确到分钟)。
    传 override(来自 --run-ts)必须合规,否则直接报错 —— 把命名规范【强制在代码里】,
    杜绝随手起非规范批次名(如 ..._rerun)。各 predict 脚本统一用 run_ts(a.run_ts)。"""
    if override:
        if not _BATCH_RE.match(override):
            raise SystemExit(f"✗ 批次名「{override}」不规范:必须 YYYY-MM-DD_HHMM(如 2026-06-12_0323)。")
        return override
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M")


def save_pred(kind, batch_ts, data, meta=None):
    """存到 predictions/<批次日期_时分>/<kind>.json（首次写 _meta.md 批次说明）。
    预测文件 + 赛后 results.json + _meta.md 同放一个「精确到分钟」的批次目录,合规可追溯。"""
    d = f"{ROOT}/wc_runs/predictions/{batch_ts}"
    os.makedirs(d, exist_ok=True)
    path = f"{d}/{kind}.json"
    if os.path.exists(path):                       # 合并:保留已有模型,只更新本次跑的(支持分模型补跑)
        try:
            old = json.load(open(path, encoding="utf-8")); old.update(data); data = old
        except Exception:
            pass
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if meta and not os.path.exists(f"{d}/_meta.md"):
        open(f"{d}/_meta.md", "w", encoding="utf-8").write(meta)
    print(f"  ✅ 存 → predictions/{batch_ts}/{kind}.json")
    return path


def save_prompt(batch_ts, kind, system, user):
    """留存该预测【实际用的 prompt】(System+User,含真实抬头+summary)到
    predictions/<批次>/_prompts/<kind>.txt —— 和预测结果放一块,可追溯当时喂了什么。每类存一份。"""
    d = f"{ROOT}/wc_runs/predictions/{batch_ts}/_prompts"
    os.makedirs(d, exist_ok=True)
    p = f"{d}/{kind}.txt"
    if not os.path.exists(p):                              # 同类 prompt 对各模型一致,存一份样本即可
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"【System】\n{system}\n\n{'='*64}\n【User】\n{user}")
