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
    for p in (f"{ROOT}/wc_runs/bg/static/groups.json", f"{ROOT}/wc_runs/bg/static/groups.json"):
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return {}


def load_matches():
    """赛程 matches.json(每场 date/round/group/venue_id/team_a/team_b/result)。"""
    p = f"{ROOT}/wc_runs/bg/matches.json"
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


_HOSTS = {"MEX", "USA", "CAN"}                                        # 2026 三东道主
_MX_CITY = {"Mexico City", "Guadalajara", "Zapopan", "Monterrey"}
_CA_CITY = {"Toronto", "Vancouver"}
_ROUND_CN = {"group": "小组赛", "r32": "32 强", "r16": "16 强", "qf": "1/4 决赛", "sf": "半决赛", "final": "决赛"}


def match_header(home, away):
    """比赛抬头:指定这场未来比赛(赛事/阶段/组/日期/场地/主客/真主场 or 中立/未打)。从 matches.json 读。"""
    mt = next((m for m in load_matches() if m.get("team_a") == home and m.get("team_b") == away), None)
    if not mt:
        return f"2026 世界杯 · 主队 {home} vs 客队 {away}(赛果未出,预测)"
    venues = json.load(open(f"{ROOT}/wc_runs/bg/venues.json", encoding="utf-8"))
    v = venues.get(mt.get("venue_id"), {})
    vname, vcity = v.get("name", "?"), v.get("city", "?")
    rd = _ROUND_CN.get(mt.get("round"), mt.get("round", ""))
    grp = f"{mt.get('group')} 组 · " if mt.get("group") else ""
    vcountry = "MEX" if vcity in _MX_CITY else "CAN" if vcity in _CA_CITY else "USA"
    if home in _HOSTS and vcountry == home:
        site = f"{vname}({vcity})—— {home} 为东道主、享真实主场之利"
    else:
        site = f"{vname}({vcity},中立场地)—— 双方均非本场东道主,名义主队 {home} 无真实主场加成"
    status = "本场尚未开打(预测即将进行的这一场)" if mt.get("result") is None else "本场已结束"
    return (f"2026 世界杯 · {rd} · {grp}{mt.get('date', '')}\n"
            f"场地:{site}\n主队 {home} vs 客队 {away} · {status}")


# 亚洲让球盘:固定盘口(主队让球数,负 = 主队让球)。来源:多方赔率核对。
# 让球是市场给定的一条线,模型只预测「该线下 主胜盘 / 走盘 / 客胜盘」—— 不是自选盘口。
_HANDICAP = {
    ("MEX", "RSA"): -1.0,    # 墨西哥 -1(阿兹特克主场;Yahoo / BoyleSports 主 -1)
    ("KOR", "CZE"): -0.5,    # 韩国 -0.5(ESPN spread 韩 -0.5)
    ("CAN", "BIH"): -0.5,    # 加拿大 -0.5(主场;ESPN / SportsGambler 加 -0.5)
    ("USA", "PAR"): -0.5,    # 美国 -0.5(主场;ESPN / FanDuel 美 -0.5)
}


def match_handicap(home, away):
    """本场固定让球盘口(主队让球数,负 = 主队让球)。None = 未定(前端用公式兜底)。"""
    return _HANDICAP.get((home, away))


def handicap_clause(home, away):
    """让球 prompt 说明:固定盘口 + 主胜盘/走盘/客胜盘 判定(覆盖主队让球场景)。"""
    h = match_handicap(home, away)
    if h is None:
        return None
    ab = abs(h); need = int(ab) + 1
    if ab == int(ab):                                    # 整数盘:有走盘
        return (f"本场亚洲让球盘固定盘口:{home}(主)让 {int(ab)} 球。"
                f"判定:{home} 净胜 ≥ {need} 球 →「主胜盘」;正好净胜 {int(ab)} 球 →「走盘」;打平或输 →「客胜盘」。")
    return (f"本场亚洲让球盘固定盘口:{home}(主)让 {ab} 球(半球盘,无走盘)。"
            f"判定:{home} 净胜 ≥ {need} 球 →「主胜盘」;否则 →「客胜盘」。")


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
