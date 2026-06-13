#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【比赛环境 · 按场采集】一场比赛的"环境"= 比赛+时间+地点 三者确定的一揽子:
   开球时间(美东/北京) · 场馆(城市/海拔/顶棚) · 天气(开球时段,open-meteo 免费API) · 主裁(人名,WebSearch 得)。

存放(与 team_news 同一双写思路):
  data_processed/match_env/<date>_<HOME>_vs_<AWAY>.json   ← 成熟仓库(按场次,一场一份)
  data_raw/<时分>/match_env/<同名>.json                    ← 收集过程留底(本次新增/刷新)
  增量判断:场次已在仓库 → 默认跳过;--refresh 重拍(天气临近会变,赛前1天建议刷一次)。

下游:predict/common.match_header() 自动读本仓库 → 环境行(天气/主裁)进预测 prompt。

跑:python3 collect_match_env.py --home BRA --away MAR --ts 2026-06-13_0800
   python3 collect_match_env.py --home BRA --away MAR --ts ... --referee "Wilton Sampaio(巴西)" --refresh
"""
import os, sys, json, argparse, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = f"{ROOT}/wc_runs"
CURATED = f"{RUNS}/data_processed/match_env"
from naming_util import valid_ts

_WMO = {0: "晴", 1: "基本晴", 2: "局部多云", 3: "阴", 45: "雾", 48: "雾凇", 51: "毛毛雨", 53: "小雨", 55: "中雨",
        61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 80: "阵雨", 81: "强阵雨", 82: "暴雨", 95: "雷雨",
        96: "雷雨夹雹", 99: "强雷雨"}


def _load(p, d=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d


def resolve(home, away):
    """从 data_reference 拿这场的 date/kickoff/场馆(含坐标海拔顶棚)。"""
    mt = next((m for m in _load(f"{RUNS}/data_reference/matches.json", [])
               if m.get("team_a") == home and m.get("team_b") == away), None)
    if not mt:
        raise SystemExit(f"✗ matches.json 无 {home} vs {away}")
    v = _load(f"{RUNS}/data_reference/venues.json", {}).get(mt.get("venue_id"), {})
    return mt, v


def fetch_weather(lat, lon, kickoff_iso):
    """open-meteo(免费/无key):取【开球那一小时】的天气。时区强制 America/New_York 与 kickoff_ts 对齐。"""
    date = kickoff_iso[:10]
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           "&hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,"
           "wind_speed_10m,relative_humidity_2m,weather_code"
           f"&start_date={date}&end_date={date}&timezone=America%2FNew_York")
    d = json.loads(urllib.request.urlopen(url, timeout=30).read())
    hh = d.get("hourly", {})
    times = hh.get("time", [])
    key = kickoff_iso[:13]                               # 'YYYY-MM-DDTHH'
    i = next((k for k, t in enumerate(times) if t.startswith(key)), None)
    if i is None:
        return None
    code = (hh.get("weather_code") or [None] * len(times))[i]
    return {"温度C": hh["temperature_2m"][i], "体感C": hh["apparent_temperature"][i],
            "降水概率%": hh["precipitation_probability"][i], "降水mm": hh["precipitation"][i],
            "风速kmh": hh["wind_speed_10m"][i], "湿度%": hh["relative_humidity_2m"][i],
            "天况": _WMO.get(code, f"code{code}")}


def collect(home, away, ts, referee=None, referee_src=None, refresh=False, var=None):
    mt, v = resolve(home, away)
    slug = f"{mt['date']}_{home}_vs_{away}"
    cur = f"{CURATED}/{slug}.json"
    if os.path.exists(cur) and not refresh:
        print(f"  ⏭ {slug} 仓库已有 → 跳过(要更新天气/裁判用 --refresh)")
        return None
    kts = mt.get("kickoff_ts")
    wx = None
    if kts and v.get("lat"):
        try:
            wx = fetch_weather(v["lat"], v["lon"], kts)
        except Exception as e:
            print(f"  ⚠️ 天气获取失败:{str(e)[:60]}")
    bj = ""
    if kts:
        dt = datetime.datetime.fromisoformat(kts)
        bj = (dt + datetime.timedelta(hours=12)).strftime("%m-%d %H:%M")
    old = _load(cur, {})
    rec = {"match": {"slug": slug, "date": mt["date"], "home": home, "away": away,
                     "round": mt.get("round"), "group": mt.get("group")},
           "kickoff": {"美东": kts or "(未填,跑 fill_kickoffs.py)", "北京": bj},
           "venue": {"name": v.get("name"), "city": v.get("city"), "altitude_m": v.get("altitude_m"),
                     "roof": v.get("roof"), "surface": v.get("surface")},
           "weather": ({"开球时段": wx, "source": "open-meteo(免费预报API)",
                        "fetched": ts, "_note": "临近开球建议 --refresh 刷新"} if wx else
                       old.get("weather") or {"_note": "未获取(缺kickoff或坐标)"}),
           "referee": ({"name": referee, **({"var": var} if var else {}),
                        "source": referee_src or "WebSearch(FIFA官方指派)", "fetched": ts}
                       if referee else old.get("referee") or {"name": None, "_note": "待 WebSearch FIFA指派公告"}),
           "_note": "环境=比赛+时间+地点 确定;天气为开球时段;顶棚 retractable/fixed-canopy 时天气影响有限。"}
    os.makedirs(CURATED, exist_ok=True)
    rawd = f"{RUNS}/data_raw/{ts}/match_env"
    os.makedirs(rawd, exist_ok=True)
    body = json.dumps(rec, ensure_ascii=False, indent=1)
    open(cur, "w", encoding="utf-8").write(body)                    # ① 成熟仓库
    open(f"{rawd}/{slug}.json", "w", encoding="utf-8").write(body)  # ② 收集过程
    wtxt = f"{wx['天况']} {wx['温度C']}°C 降水{wx['降水概率%']}% 风{wx['风速kmh']}km/h" if wx else "无天气"
    print(f"  ✅ {slug}: {wtxt} | 裁判:{referee or '待检索'} | 顶棚:{v.get('roof')}")
    return cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--away", required=True)
    ap.add_argument("--ts", required=True, help="收集时分 YYYY-MM-DD_HHMM")
    ap.add_argument("--referee", help="主裁人名(国籍),WebSearch FIFA指派得")
    ap.add_argument("--var", dest="var", help="VAR视频助理裁判人名(可选)")
    ap.add_argument("--referee-src", dest="rsrc", help="裁判信息来源")
    ap.add_argument("--refresh", action="store_true", help="已有也刷新(天气临近会变)")
    a = ap.parse_args()
    valid_ts(a.ts)
    collect(a.home, a.away, a.ts, a.referee, a.rsrc, a.refresh, a.var)


if __name__ == "__main__":
    main()
