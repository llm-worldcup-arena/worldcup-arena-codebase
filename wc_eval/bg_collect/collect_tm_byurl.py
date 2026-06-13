#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【补充工具 · 音译名球员身价（TM 链接采）】—— 配 skill `wc-data-collect` §4b。

何时用：`collect_transfermarkt.py`(automation-lab 按名字搜)对**韩/阿拉伯/中亚音译名**彻底无效
       （孙兴慜/Kim Min-jae 都搜空）→ KOR/EGY/中东/UZB 这些队改用本工具按 **TM 链接** 采身价。

方法（实测通，base 的 236 人 + 10 人身价就是这么补的）：
  ① 先 WebSearch `<球员名> transfermarkt` 拿每人 TM 数字 id（agent 活，命中 ~100%）→ 存成 {pid,tm_id} JSON；
  ② 本脚本用 `handsome_apostrophe/transfermarkt-scraper-v2` 的 `playerUrls` + **slug 占位 URL**
     `transfermarkt.us/x/profil/spieler/<id>` 批量采（**并发 4、每批 12**；40/批会超 250s）→ `market_value_numeric` 精确。
  ⚠️ 该 actor 的 **foot / height / club 字段解析错位、不可用**；惯用脚改用 WebSearch 读。

【安全】默认**只采集 + raw 全量留底，不碰 persons**；要写库须显式 `--apply`。APIFY_TOKEN 从环境变量读。

跑：APIFY_TOKEN=xxx python3 collect_tm_byurl.py --tmids ids.json          # 只采 + 留 raw（不动数据）
   APIFY_TOKEN=xxx python3 collect_tm_byurl.py --tmids ids.json --apply  # 额外把 market_value 写进 persons
   ids.json 格式：[{"pid":"per_son_heung_min","tm_id":"258923"}, ...]
"""
import os, json, argparse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from collect_squads import BASE, run_ts, persons_path, load_json, dump_json

ACTOR = "handsome_apostrophe~transfermarkt-football-scraper-v2"
BATCH, WORKERS = 12, 4   # 实测：40/批 >250s 超时，故每批 12、并发 4


def apify_token():
    t = os.environ.get("APIFY_TOKEN")
    if not t:
        raise SystemExit("✗ 缺环境变量 APIFY_TOKEN（凭证不写进代码）")
    return t


def fetch_batch(chunk):
    """一批 ≤12 人：slug 占位 URL → handsome actor → 返回 [(pid, 完整记录)]。"""
    urls = [f"https://www.transfermarkt.us/x/profil/spieler/{tid}" for _, tid in chunk]
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={apify_token()}"
    req = urllib.request.Request(url, data=json.dumps({"mode": "players", "playerUrls": urls}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=220).read())
    except Exception as e:
        print(f"  批失败: {e}"); return []
    bt = {str(p.get("player_id")): p for p in d}
    return [(pid, bt[tid]) for pid, tid in chunk if bt.get(tid)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmids", required=True, help="JSON: [{pid,tm_id}]（WebSearch 找到的 TM 数字 id）")
    ap.add_argument("--apply", action="store_true", help="把 market_value 写进 persons（默认只采+留 raw、不动数据）")
    a = ap.parse_args()

    recs = json.load(open(a.tmids, encoding="utf-8"))
    ids = [(r["pid"], str(r["tm_id"])) for r in recs if r.get("tm_id")]
    batches = [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]

    ts = run_ts(); rawd = f"{BASE}/data_raw/{ts}/tm_byurl"; os.makedirs(rawd, exist_ok=True)
    allp = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, res in enumerate(ex.map(fetch_batch, batches)):
            for pid, p in res:
                p["_our_pid"] = pid; allp[pid] = p
            print(f"  批 {i+1}/{len(batches)} 累计 {len(allp)}")

    # raw 全量留底 + _source.md（两步铁律第一步）
    json.dump(list(allp.values()), open(f"{rawd}/players.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(f"{rawd}/_source.md", "w", encoding="utf-8").write(
        "# 采集来源说明 · 音译名球员身价（TM 链接采）\n"
        f"- **数据源**：Apify · {ACTOR}（playerUrls + slug 占位 URL）\n"
        "- **方式**：WebSearch 找 TM 数字 id → 本工具批量采（并发 4、每批 12）\n"
        "- **可靠**：market_value_numeric / market_value_history；**foot/height/club 错位勿用**\n"
        "- **用于**：automation-lab 搜不到的音译名队（KOR/EGY/中东/UZB）｜配 wc-data-collect §4b\n")
    print(f"✅ 采 {len(allp)}/{len(ids)} 人 → data_raw/{ts}/tm_byurl/（raw 全量留底）")

    if a.apply:
        by_id = {p["person_id"]: p for p in load_json(persons_path(), [])}
        n = 0
        for pid, p in allp.items():
            mv = p.get("market_value_numeric")
            if by_id.get(pid) and mv:
                by_id[pid].setdefault("player", {})["market_value_eur"] = mv
                by_id[pid]["player"]["market_value_src"] = "transfermarkt(链接采·音译名)"
                n += 1
        dump_json(persons_path(), sorted(by_id.values(), key=lambda x: x["person_id"]))
        print(f"  --apply: 写 {n} 人 market_value 进 persons")
    else:
        print("  （默认不写 persons；要写库加 --apply）")


if __name__ == "__main__":
    main()
