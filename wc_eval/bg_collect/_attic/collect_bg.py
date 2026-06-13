#!/usr/bin/env python3
"""【已弃用 · 留档】API-Football 版采集器。
免费档拿不到 2026（报错只允 2022–2024），未投用；2026 实际走维基,
见 collect_squads.py + wc_skills/wc-data-collect。本文件保留作「API 方案试过」的记录。
————————————————————————————————————————————————————————————————

世界杯 background 数据采集 —— 按 BG_DESIGN.md 实施。

数据源:API-Football(v3,免费档,含世界杯)为主;
        国家队生涯 caps / Elo 等 API-Football 给不全的,标注 → 另源(FBref/Wikidata/eloratings)。
输出:范式化 JSON,ensure_ascii=False。
  raw:  wc_runs/data_raw/asof=YYYY-MM-DD/<endpoint>_<team>.json   ← API 原始 JSON 响应(未加工)
  data: wc_runs/data/static/{persons,teams}.json + bg/asof=YYYY-MM-DD/{squad,team_rank,...}.json

⚠️ build_* 的字段映射按 API-Football v3 常见结构写;**拿到 key 后用真实返回校准**(标 ★校准)。
⚠️ 没 key 跑不了真采集(数据从 API 来)。先 --dry-run 看流程。
"""
from __future__ import annotations
import argparse, json, os, re, urllib.request
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Optional

# ============ 配置 ============
API_KEY  = os.environ.get("API_FOOTBALL_KEY", "")
API_BASE = "https://v3.football.api-sports.io"
WC_LEAGUE_ID = 1        # ★校准:拿 key 后查 /leagues?search=World Cup 确认 id
WC_SEASON    = 2026
ROOT = Path("wc_runs")

# ============ id 映射 ============
def person_id(name_en: str) -> str:
    return "per_" + re.sub(r"[^a-z0-9]+", "_", name_en.lower()).strip("_")

# 国家名 → FIFA 三字码(★校准:补全 48 队;API 返回的是国家名,我们用三字码当 team_id）
_NAT3 = {"Spain": "ESP", "Argentina": "ARG", "France": "FRA", "Brazil": "BRA"}  # … 待补
def nat3(country: Optional[str]) -> Optional[str]:
    return _NAT3.get(country or "", (country or "")[:3].upper() or None)

def _num(x) -> Optional[int]:
    try: return int(re.sub(r"\D", "", str(x))) if x else None
    except Exception: return None

# ============ 采集:调 API-Football，并把原始响应落 raw ============
def _api_get(path: str, params: Dict[str, Any], raw_dir: Path, tag: str) -> Dict[str, Any]:
    if not API_KEY:
        raise SystemExit("缺 API_FOOTBALL_KEY:注册免费档拿 key,或用 --dry-run")
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(f"{API_BASE}/{path}?{qs}", headers={"x-apisports-key": API_KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    # 原则:raw 存 API 原始 JSON 响应(未加工)
    write_json(raw_dir / f"{tag}.json", data)
    return data

def fetch_teams(raw_dir: Path) -> List[dict]:
    return _api_get("teams", {"league": WC_LEAGUE_ID, "season": WC_SEASON}, raw_dir, "teams").get("response", [])

def fetch_squad(team_api_id: int, raw_dir: Path) -> List[dict]:
    return _api_get("players/squads", {"team": team_api_id}, raw_dir, f"squad_{team_api_id}").get("response", [])

def fetch_player(player_api_id: int, raw_dir: Path) -> dict:
    resp = _api_get("players", {"id": player_api_id, "season": WC_SEASON}, raw_dir, f"player_{player_api_id}").get("response", [])
    return resp[0] if resp else {}

# ============ 组装:API 原始响应 → BG_DESIGN.md 的 JSON(纯代码映射，不用 LLM) ============
def build_persons(player_records: List[dict]) -> List[dict]:
    """player_records: 每个是 /players 的一条 response。→ static/persons.json"""
    out = []
    for rec in player_records:
        p = rec.get("player", {})
        st = (rec.get("statistics") or [{}])[0]
        name_en = f"{p.get('firstname','')} {p.get('lastname','')}".strip() or p.get("name", "")
        out.append({
            "person_id": person_id(name_en),
            "name_zh": "",                                   # ★API 无中文名 → 译名表/人工补
            "name_en": name_en,
            "birthdate": (p.get("birth") or {}).get("date"),
            "nationality": nat3((p.get("birth") or {}).get("country") or p.get("nationality")),
            "roles": ["player"],
            "player": {
                "position": (st.get("games") or {}).get("position"),
                "height_cm": _num(p.get("height")),
                # ★API-Football 给的是【俱乐部赛季】统计,不是【国家队生涯 caps】;
                #   intl_caps / intl_goals → 另源(FBref / Wikidata),此处留空待补
                "intl_caps": None, "intl_goals": None,
            },
        })
    return out

def build_teams(team_records: List[dict]) -> List[dict]:
    out = []
    for rec in team_records:
        t = rec.get("team", {})
        out.append({
            "team_id": nat3(t.get("name")) or (t.get("code") or "").upper(),
            "name_zh": "", "name_en": t.get("name"),          # ★中文名待补
            "founded": t.get("founded"),
            # wc_titles / wc_best / wc_appearances / qualifying → ★另源(FIFA 官方/历史),API 不直接给
        })
    return out

def build_squad_snapshot(squads_by_team: Dict[str, List[dict]]) -> Dict[str, list]:
    """squads_by_team: {team_id: /players/squads 的 players 列表}。→ bg/asof/squad.json"""
    out: Dict[str, list] = {}
    for tid, players in squads_by_team.items():
        out[tid] = [{"person_id": person_id(pl.get("name","")), "shirt": pl.get("number"),
                     "role": pl.get("position")} for pl in players]
    return out

def build_team_rank(fifa: Dict[str, int], elo: Dict[str, int]) -> Dict[str, dict]:
    return {tid: {"fifa": fifa.get(tid), "elo": elo.get(tid)} for tid in set(fifa) | set(elo)}

# FIFA 排名 / Elo:API-Football 没有 → 另源
def fetch_fifa_rank() -> Dict[str, int]: return {}   # ★FIFA 官方 / football-data.org
def fetch_elo() -> Dict[str, int]:       return {}   # ★eloratings.net

# ============ 落盘(ensure_ascii=False) ============
def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

# ============ main ============
def main() -> None:
    ap = argparse.ArgumentParser(description="采集世界杯 bg → 范式化 JSON(按 BG_DESIGN.md)")
    ap.add_argument("--asof", default=date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    raw_dir    = ROOT / "raw" / "bg" / f"asof={a.asof}"
    static_dir = ROOT / "data" / "static"
    bg_dir     = ROOT / "data" / "bg" / f"asof={a.asof}"
    print(f"raw → {raw_dir}/   data → {static_dir}/ + {bg_dir}/")
    if a.dry_run:
        print("dry-run:不调 API。拿到 key 后去掉 --dry-run 真跑。"); return

    teams = fetch_teams(raw_dir)                              # 48 队(原始响应已落 raw)
    write_json(static_dir / "teams.json", build_teams(teams))

    squads_by_team, all_players = {}, []
    for rec in teams:
        api_id = rec.get("team", {}).get("id")
        tid    = nat3(rec.get("team", {}).get("name"))
        squad  = fetch_squad(api_id, raw_dir)
        players = (squad[0].get("players") if squad else []) or []
        squads_by_team[tid] = players
        for pl in players:
            all_players.append(fetch_player(pl.get("id"), raw_dir))

    write_json(static_dir / "persons.json",   build_persons(all_players))
    write_json(bg_dir / "squad.json",         build_squad_snapshot(squads_by_team))
    write_json(bg_dir / "team_rank.json",     build_team_rank(fetch_fifa_rank(), fetch_elo()))
    print(f"完成:{len(teams)} 队 / {len(all_players)} 人")

if __name__ == "__main__":
    main()
