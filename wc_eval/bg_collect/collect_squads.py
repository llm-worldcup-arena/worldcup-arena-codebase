#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""世界杯 2026 · bg 球员层采集器（维基队页【整页全文】→ 解析当前阵容）。

一份代码把规矩全定死，跑它出活，不再手动：
  抓取 : 维基 API 的【整页 wikitext】源码（合规 UA 直连；被 403 时用 --from-raw 只解析已存原文）
  raw  : wc_runs/raw/bg/<采集时分>/<TEAM>.wikitext              ← 整页全文原文（源码，未加工）
  data : wc_runs/data/static/persons.json                       ← 人物（按 person_id 增量更新）
         wc_runs/data/bg/asof=<ASOF>/squad.json                 ← 阵容快照（队-号-位-俱乐部）

跑法：
  python3 collect_squads.py --only ESP        # 先测一队
  python3 collect_squads.py                    # 全 48 队
  python3 collect_squads.py --from-raw         # 不抓网，只解析 raw 里已存的 wikitext
"""
import os, re, json, argparse, unicodedata, urllib.request, urllib.parse
from datetime import datetime

ASOF = "2026-06-08"                       # data 快照按【日期】（asof = 截至某日，不带分钟）
BASE = "/home/ubuntu/worldcup_2026/wc_runs"

def run_ts():                             # raw 目录按【采集时分】，精确到分钟
    return datetime.now().strftime("%Y-%m-%d_%H%M")

def latest_run_ts():                      # --from-raw 找最近一次「球员阵容」目录（认 nat fs 模板，避开教练 infobox）
    base = f"{BASE}/raw/bg"
    cands = []
    for d in os.listdir(base):
        dd = f"{base}/{d}"
        if not os.path.isdir(dd):
            continue
        wts = [f for f in os.listdir(dd) if f.endswith(".wikitext")]
        if wts and "nat fs g player" in open(f"{dd}/{wts[0]}", encoding="utf-8").read(3000):
            cands.append(d)
    return max(cands) if cands else None

BG = f"{BASE}/bg"                                      # ── background 根(新结构) ──
def raw_path(ts, team):    return f"{BASE}/raw/bg/{ts}/{team}.wikitext"   # raw 不变,永远整页原文
def persons_path():        return f"{BG}/persons.json"          # 实体·带 history
def teams_path():          return f"{BG}/teams.json"            # 实体·带 history
def matches_path():        return f"{BG}/matches.json"          # 实体·所有届
def venues_path():         return f"{BG}/venues.json"           # 实体·带 history
def static_path(name):     return f"{BG}/static/{name}.json"    # 纯关系(groups/bracket)
def snap_path(asof, name): return f"{BG}/snapshots/asof={asof}/{name}.json"  # 慢变快照
def squad_path(asof):      return snap_path(asof, "squad")

# 维基要求「合规 UA」（标明用途+联系方式）；用浏览器伪装 UA 反而会被 403。
UA = "WorldCup2026-BG-Research/1.0 (academic benchmark; mailto:zhenran.w.1103@gmail.com)"

# 48 队：FIFA 三字码 → 维基页面名（美/加/澳/瑞典/新西兰是 "men's ... soccer/football"）
WIKI_PAGE = {
    "MEX": "Mexico national football team", "RSA": "South Africa national football team",
    "KOR": "South Korea national football team", "CZE": "Czech Republic national football team",
    "CAN": "Canada men's national soccer team", "BIH": "Bosnia and Herzegovina national football team",
    "QAT": "Qatar national football team", "SUI": "Switzerland national football team",
    "BRA": "Brazil national football team", "MAR": "Morocco national football team",
    "HAI": "Haiti national football team", "SCO": "Scotland national football team",
    "USA": "United States men's national soccer team", "PAR": "Paraguay national football team",
    "AUS": "Australia men's national soccer team", "TUR": "Turkey national football team",
    "GER": "Germany national football team", "CUW": "Curaçao national football team",
    "CIV": "Ivory Coast national football team", "ECU": "Ecuador national football team",
    "NED": "Netherlands national football team", "JPN": "Japan national football team",
    "SWE": "Sweden men's national football team", "TUN": "Tunisia national football team",
    "BEL": "Belgium national football team", "EGY": "Egypt national football team",
    "IRN": "Iran national football team", "NZL": "New Zealand men's national football team",
    "ESP": "Spain national football team", "CPV": "Cape Verde national football team",
    "KSA": "Saudi Arabia national football team", "URU": "Uruguay national football team",
    "FRA": "France national football team", "SEN": "Senegal national football team",
    "IRQ": "Iraq national football team", "NOR": "Norway national football team",
    "ARG": "Argentina national football team", "ALG": "Algeria national football team",
    "AUT": "Austria national football team", "JOR": "Jordan national football team",
    "POR": "Portugal national football team", "COD": "DR Congo national football team",
    "UZB": "Uzbekistan national football team", "COL": "Colombia national football team",
    "ENG": "England national football team", "CRO": "Croatia national football team",
    "GHA": "Ghana national football team", "PAN": "Panama national football team",
}

# ───────────────────────── 抓取（维基 API） ─────────────────────────
def wiki_api(params):
    params.setdefault("redirects", 1)          # 跟随重定向（如南非队页是重定向）
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Api-User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")

def fetch_full_page(page):
    """抓【整页】wikitext 源码（不分段）——阵容、教练 infobox、世界杯史都在这一份里。"""
    data = json.loads(wiki_api({"action": "parse", "page": page,
                                "prop": "wikitext", "format": "json"}))
    return data.get("parse", {}).get("wikitext", {}).get("*", "")


def fetch_save(page, raw_dir, fname):
    """抓整页 wikitext + 存 raw 原文（raw 全量留底：凡查过的页都留着原文）。"""
    wt = fetch_full_page(page)
    if raw_dir and wt:
        os.makedirs(raw_dir, exist_ok=True)
        open(f"{raw_dir}/{fname}", "w", encoding="utf-8").write(wt)
    return wt

# ───────────────────────── 解析（wikitext → 球员） ─────────────────────────
def slugify(name):
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    n = re.sub(r"[^a-zA-Z0-9]+", "_", n).strip("_").lower()
    return "per_" + n

def clean_link(s):
    """[[A|B]]→B，[[A]]→A，{{sortname|名|姓}}→名 姓，其余原样。"""
    s = s.strip()
    m = re.match(r"\{\{\s*sortname\s*\|([^|}]+)\|([^|}]+)", s)
    if m:
        return f"{m.group(1).strip()} {m.group(2).strip()}"
    m = re.match(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", s)
    return m.group(1).strip() if m else s

def parse_birth(age_param):
    m = re.search(r"(\d{4})\|(\d{1,2})\|(\d{1,2})", age_param)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""

def extract_player_blocks(wt):
    """按括号配平，提取每个 {{nat fs g player ...}} 整块（容忍内部嵌套模板）。"""
    blocks, key, i = [], "{{nat fs g player", 0
    while True:
        start = wt.find(key, i)
        if start < 0:
            break
        depth, j = 0, start
        while j < len(wt):
            if wt[j:j+2] == "{{": depth += 1; j += 2
            elif wt[j:j+2] == "}}":
                depth -= 1; j += 2
                if depth == 0: break
            else: j += 1
        blocks.append(wt[start:j]); i = j
    return blocks

def split_top_params(inner):
    """按顶层 | 切分，忽略 {{}} 和 [[]] 内部的 |。"""
    parts, cur, dc, db, i = [], "", 0, 0, 0
    while i < len(inner):
        two = inner[i:i+2]
        if two == "{{": dc += 1; cur += two; i += 2; continue
        if two == "}}": dc -= 1; cur += two; i += 2; continue
        if two == "[[": db += 1; cur += two; i += 2; continue
        if two == "]]": db -= 1; cur += two; i += 2; continue
        ch = inner[i]
        if ch == "|" and dc == 0 and db == 0:
            parts.append(cur); cur = ""; i += 1; continue
        cur += ch; i += 1
    parts.append(cur)
    return parts

def parse_player_block(block):
    inner = block[2:-2]                         # 去掉外层 {{ }}
    kv = {}
    for part in split_top_params(inner)[1:]:    # 第 0 段是 "nat fs g player"
        if "=" in part:
            k, v = part.split("=", 1)
            kv[k.strip()] = v.strip()
    name = clean_link(kv.get("name", ""))
    cap = (kv.get("other", "") + kv.get("captain", "")).lower()
    return {
        "no": int(kv["no"]) if kv.get("no", "").isdigit() else None,
        "pos": kv.get("pos", ""),
        "name_en": name,
        "person_id": slugify(name),
        "birthdate": parse_birth(kv.get("age", "")),
        "caps": int(kv["caps"]) if kv.get("caps", "").isdigit() else None,
        "goals": int(kv["goals"]) if kv.get("goals", "").isdigit() else None,
        "club": clean_link(kv.get("club", "")),
        "clubnat": kv.get("clubnat", ""),
        "is_captain": "captain" in cap and "vice" not in cap,
    }

MONTHS = {m: i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August",
     "September","October","November","December"], 1)}

def parse_caps_asof(intro):
    # 文字: "as of 4 June 2026"（含 updated/correct as of …）
    m = re.search(r"as of\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", intro, re.I)
    if m and m.group(2).capitalize() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2).capitalize()]:02d}-{int(m.group(1)):02d}"
    # 模板: {{as of|2026|6|4}}
    m = re.search(r"\{\{\s*as of\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", intro, re.I)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""

def squad_segment(wt):
    """从整页截出「Current squad」这一段（标题后 → 下一个同级/更高标题前）。
    只在这一段里找球员，免得把同样用 {{nat fs}} 的「Recent call-ups」也算进来。"""
    m = re.search(r"(=+)\s*Current squad\s*=+", wt, re.I)
    if not m:
        m = re.search(r"(=+)\s*[^=\n]*squad[^=\n]*=+", wt, re.I)
    if not m:
        return ""
    level, start = len(m.group(1)), m.end()
    for nm in re.finditer(r"\n(=+)[^=\n].*?=+[ \t]*\n", wt[start:]):
        if len(nm.group(1)) <= level:
            return wt[start:start + nm.start()]
    return wt[start:]

def parse_squad(wt):
    seg = squad_segment(wt) or wt              # 整页 → 只取 Current squad 段
    intro = seg.split("{{nat fs")[0]
    intro = re.sub(r"<ref.*?</ref>", "", intro, flags=re.S)
    intro = re.sub(r"<[^>]+>", "", intro)
    intro = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", intro)
    intro = re.sub(r"=+\s*Current squad\s*=+", "", intro).strip()
    players = [parse_player_block(b) for b in extract_player_blocks(seg)]
    return players, {"named_for": " ".join(intro.split())[:300],
                     "caps_asof": parse_caps_asof(intro)}

def strip_wiki(s):
    """去 ref / 模板 / 链接 / 标签 / 斜体 / HTML 实体，留纯文本（<br> 转 / 分隔多值）。"""
    s = re.sub(r"<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " / ", s, flags=re.I)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("''", "")
    s = re.sub(r"&\w+;", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" '\"/-")

def parse_team_infobox(wt):
    """队页 infobox 取球队补充字段：昵称 / 主场 / 成立年（首场国际比赛年份近似）。"""
    def grab(key):
        m = re.search(r"\|\s*" + key + r"\s*=\s*([^\n]+)", wt, re.I)
        return strip_wiki(m.group(1)) if m else ""
    first = grab("First game")
    ym = re.search(r"\b(18|19|20)\d{2}\b", first)
    return {"name_en": grab("Name"), "confederation": grab("Confederation").split("(")[0].strip(),
            "nickname": grab("Nickname"), "home_stadium": grab("Home Stadium"),
            "founded": int(ym.group()) if ym else None}

# ───────────────────────── 落盘（persons / squad） ─────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def upsert_persons(team, players, caps_asof):
    persons = load_json(persons_path(), [])
    by_id = {p["person_id"]: p for p in persons}
    for pl in players:
        rec = by_id.get(pl["person_id"], {})
        player = rec.get("player", {})                       # 合并·保留球员页补的(身高/生涯俱乐部/全名…)
        player.update({"position": pl["pos"], "intl_caps": pl["caps"],
                       "intl_goals": pl["goals"], "is_captain": pl["is_captain"],
                       "as_of": caps_asof or ASOF})          # as-of 口径日期(草稿统一标注)
        rec.update({
            "person_id": pl["person_id"],
            "name_zh": rec.get("name_zh", ""),
            "name_en": pl["name_en"],
            "birthdate": pl["birthdate"],
            "nationality": team,
            "roles": sorted(set(rec.get("roles", []) + ["player"])),
            "player": player,
        })
        rec.setdefault("history", [])                        # 事件流(伤病/停赛/转会)·起步空
        by_id[pl["person_id"]] = rec
    dump_json(persons_path(), sorted(by_id.values(), key=lambda p: p["person_id"]))

def update_squad(asof, team, players, meta):
    sq = load_json(squad_path(asof), {})
    if not isinstance(sq, dict) or "teams" in sq:          # 非 dict / 旧 teams 包裹 → 重建
        sq = {}
    sq[team] = {                                            # 新结构: {team: {players:[…]}}（直接，无包裹）
        "named_for": meta["named_for"], "caps_asof": meta["caps_asof"],
        "players": [{"person_id": p["person_id"], "no": p["no"], "pos": p["pos"],
                     "club": p["club"], "clubnat": p["clubnat"]} for p in players],
    }
    dump_json(squad_path(asof), sq)

# ───────────────────────── 主流程 ─────────────────────────
def run_team(team, ts, asof, from_raw):
    rp = raw_path(ts, team)
    if from_raw:
        if not os.path.exists(rp):
            print(f"  [{team}] 跳过：没有 raw 文件 {rp}"); return False
        wt = open(rp, encoding="utf-8").read()
    else:
        wt = fetch_full_page(WIKI_PAGE[team])
        if not wt:
            print(f"  [{team}] 整页抓取失败"); return False
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        open(rp, "w", encoding="utf-8").write(wt)
    players, meta = parse_squad(wt)
    if not players:
        print(f"  [{team}] 解析到 0 人（模板可能不同，需单独看）"); return False
    upsert_persons(team, players, meta["caps_asof"])
    update_squad(asof, team, players, meta)
    print(f"  [{team}] {len(players)} 人  | caps_asof={meta['caps_asof'] or '?'} | {meta['named_for'][:50]}…")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑指定队，逗号分隔，如 ESP,ARG")
    ap.add_argument("--from-raw", action="store_true", help="不抓网，只解析已存的 raw wikitext")
    ap.add_argument("--asof", default=ASOF, help="data 快照日期")
    ap.add_argument("--run-ts", help="raw 目录时间戳(带分钟)；抓取默认当前时刻，--from-raw 默认最近一次")
    args = ap.parse_args()
    from naming_util import valid_ts, valid_asof
    valid_asof(args.asof); valid_ts(getattr(args,"run_ts",None))   # 命名规范强制
    ts = args.run_ts or (latest_run_ts() if args.from_raw else run_ts())
    if not ts:
        print("找不到可用的 raw 时间戳目录"); return
    print(f"raw 目录: raw/bg/{ts}/   data: asof={args.asof}\n")
    targets = args.only.split(",") if args.only else list(WIKI_PAGE)
    ok = 0
    for t in targets:
        t = t.strip().upper()
        if t not in WIKI_PAGE:
            print(f"  [{t}] 不在 48 队名单"); continue
        try:
            ok += run_team(t, ts, args.asof, args.from_raw)
        except urllib.error.HTTPError as e:
            print(f"  [{t}] HTTP {e.code} {e.reason}")
        except Exception as e:
            print(f"  [{t}] 出错: {type(e).__name__}: {e}")
    print(f"\n完成 {ok}/{len(targets)} 队 → persons.json / squad.json（asof={args.asof}）")

if __name__ == "__main__":
    main()
