#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第0步试调：确认 World Cup 的 league id + 2026 赛季数据是否就绪。
原始返回直接存 raw（真·未加工 JSON）。只花 3 个请求探路。
跑法：API_FOOTBALL_KEY=xxx python3 probe_api.py
"""
import os, json, sys, urllib.request, urllib.parse

API_KEY = os.environ.get("API_FOOTBALL_KEY", "").strip()
HOST = "https://v3.football.api-sports.io"
RAW_DIR = "/home/ubuntu/worldcup_2026/wc_runs/data_raw/2026-06-07_api"


def call(path, params=None):
    url = HOST + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-apisports-key": API_KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def save_raw(name, text):
    os.makedirs(RAW_DIR, exist_ok=True)
    p = os.path.join(RAW_DIR, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def main():
    if not API_KEY:
        print("!! 没读到 API_FOOTBALL_KEY"); sys.exit(1)

    # 1) /status —— key 通不通 + 今日额度
    try:
        s = call("/status"); save_raw("_probe_status.json", s)
        sj = json.loads(s)
        resp = sj.get("response", {})
        print("=== /status ===")
        print("  账号:", resp.get("account", {}).get("email", "?"))
        print("  订阅:", resp.get("subscription", {}))
        print("  今日用量:", resp.get("requests", {}))
        if sj.get("errors"):
            print("  errors:", sj["errors"])
    except Exception as e:
        print("status 失败:", e); sys.exit(2)

    # 2) /leagues?id=1 —— 确认 league 1 是不是 World Cup，有哪些赛季
    l = call("/leagues", {"id": 1}); save_raw("_probe_league1.json", l)
    lj = json.loads(l)
    print("=== /leagues?id=1 ===  results:", lj.get("results"), " errors:", lj.get("errors"))
    for item in lj.get("response", []):
        lg = item.get("league", {})
        print("  league:", lg.get("id"), "|", lg.get("name"), "|", lg.get("type"))
        years = [se.get("year") for se in item.get("seasons", [])]
        print("  最近赛季:", years[-10:])

    # 3) /teams?league=1&season=2026 —— 2026 世界杯有几个队、字段长啥样
    t = call("/teams", {"league": 1, "season": 2026}); save_raw("_probe_teams_2026.json", t)
    tj = json.loads(t)
    print("=== /teams?league=1&season=2026 ===  results:", tj.get("results"), " errors:", tj.get("errors"))
    for item in tj.get("response", [])[:10]:
        tm = item.get("team", {})
        print("  ", tm.get("id"), "|", tm.get("name"), "| code:", tm.get("code"), "| country:", tm.get("country"))
    if tj.get("results", 0) > 10:
        print("  ...(共", tj.get("results"), "队)")


if __name__ == "__main__":
    main()
