#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""块7·Transfermarkt 球员档案采集（经 Apify · automation-lab actor，批量·便宜·并发）。
抱「补全球员档案」大方向：身价 / 惯用脚 / 合同 / 双国籍 / 转会史 …（维基都没有）。

数据源：Apify Actor  automation-lab/transfermarkt-scraper（searchQueries 数组一次采全队）。

【铁律·两步走】
  ① raw 全量留底 + 分子文件夹：完整 JSON 一字不改存 raw/bg/<ts>/transfermarkt/tm_<队>.json + 写 _source.md。
  ② 再从 raw 提取（从宽，多留 tm_*）。改了提取逻辑用 --from-raw 从 raw 重提取，不重采、不花钱。

【准确性】TM 出生**年份** ⨯ 维基 birthdate 交叉校验：年份不符 = 同名搜错人 → **剔除 TM 数据**（不污染）。
  原则：认人信维基（身份锚），身价/合同/惯用脚信 TM；重复的身高/位置不拿 TM 覆盖维基。
【并发】联网采集用线程池（默认 12 并发）；提取在主线程串行（写 persons 线程安全）。
【凭证】APIFY_TOKEN 从环境变量读，绝不写进代码/不提交 git。

跑：APIFY_TOKEN=xxx python3 collect_transfermarkt.py [--only ARG] [--workers 12]
    python3 collect_transfermarkt.py --from-raw 2026-06-09_1111   # 不联网，按新逻辑从 raw 重提取
"""
import os, re, json, unicodedata, urllib.request, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collect_squads import BASE, run_ts, persons_path, snap_path, load_json, dump_json

ACTOR = "automation-lab~transfermarkt-scraper"
ASOF  = "2026-06-08"
TM_KEYS = ("market_value_eur","market_value_asof","market_value_raw","foot","contract_until","tm_height_cm",
           "nationality_tm","tm_full_name","tm_position","tm_current_club","tm_club_join",
           "tm_transfer_history","tm_player_id","tm_url")


def apify_token():
    t = os.environ.get("APIFY_TOKEN")
    if not t:
        raise SystemExit("✗ 缺环境变量 APIFY_TOKEN（凭证不写进代码）。跑法：APIFY_TOKEN=xxx python3 collect_transfermarkt.py …")
    return t


def apify_run(inp):
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={apify_token()}"
    req = urllib.request.Request(url, data=json.dumps(inp).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "curl/8"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=300).read())


def raw_dir_of(ts):
    d = f"{BASE}/raw/bg/{ts}/transfermarkt"
    os.makedirs(d, exist_ok=True)
    return d


def save_raw_full(items, ts, team):
    with open(f"{raw_dir_of(ts)}/tm_{team}.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def write_source(ts, teams, n_players):
    md = f"""# 采集来源说明 · Transfermarkt 球员档案

- **采集种类**：球员档案（身价/惯用脚/合同/双国籍/转会史…）
- **数据源**：Apify 平台 Actor `automation-lab/transfermarkt-scraper`（Transfermarkt 抓取）
- **采集时间**：{ts}（精确到分钟）｜**方式**：每队 `searchQueries` 批量、线程池并发
- **采集范围**：{len(teams)} 队、约 {n_players} 名球员
- **raw**：本目录 `tm_<队>.json` = actor 返回**完整 JSON 全量留底**（一字不改）
- **提取**：market_value_eur / foot / contract_until / nationality_tm / tm_* …（从宽；其余字段仍在 raw）
- **准确性**：TM 出生年份 ⨯ 维基 birthdate 交叉校验，**年份不符=同名搜错人→剔除 TM**（`tm_mismatch` 标记）
- **凭证**：`APIFY_TOKEN`（环境变量，未入库）｜**用途**：世界杯 2026 预测 benchmark
"""
    with open(f"{raw_dir_of(ts)}/_source.md", "w", encoding="utf-8") as f:
        f.write(md)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def to_iso(s):
    if not s: return None
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m: return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def extract(d, our_birthdate):
    tm_bd = to_iso(d.get("dateOfBirth"))
    verified = (tm_bd[:4] == our_birthdate[:4]) if (tm_bd and our_birthdate) else None   # 比出生年份
    mv_asof = None
    mu = re.search(r"update:?\s*([\d/]+)", str(d.get("marketValue") or ""), re.I)
    if mu: mv_asof = to_iso(mu.group(1))
    tm_h, hm = None, re.search(r"([\d,\.]+)\s*m\b", str(d.get("height") or ""))   # TM 身高(职业库更权威)
    if hm:
        try:
            c = round(float(hm.group(1).replace(",", ".")) * 100); tm_h = c if 140 <= c <= 220 else None
        except ValueError: pass
    return {
        "tm_height_cm":       tm_h,
        "market_value_eur":   d.get("marketValueNumeric"),
        "market_value_asof":  mv_asof,
        "market_value_raw":   d.get("marketValue"),
        "foot":               d.get("preferredFoot"),
        "contract_until":     to_iso(d.get("contractExpiry")),
        "nationality_tm":     d.get("nationality"),
        "tm_full_name":       d.get("fullName"),
        "tm_position":        d.get("position"),
        "tm_current_club":    d.get("currentClub"),
        "tm_club_join":       d.get("clubJoinDate"),
        "tm_transfer_history": d.get("transferHistory") or None,
        "tm_player_id":       str(d.get("playerId")) if d.get("playerId") else None,
        "tm_url":             d.get("url"),
        "tm_verified":        verified,
        "market_value_src":   "transfermarkt(automation-lab)",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只采某队，逗号分隔 FIFA 码")
    ap.add_argument("--asof", default=ASOF)
    ap.add_argument("--from-raw", dest="from_raw", help="不联网，从指定 raw 目录重提取（如 2026-06-09_1111）")
    ap.add_argument("--workers", type=int, default=12, help="并发线程数（联网采集）")
    args = ap.parse_args()
    from naming_util import valid_asof
    valid_asof(args.asof)   # 命名规范强制
    only = {c.strip().upper() for c in args.only.split(",")} if args.only else None

    by_id = {p["person_id"]: p for p in load_json(persons_path(), [])}
    squad = load_json(snap_path(args.asof, "squad"), {})
    teams = [t for t in sorted(squad) if not only or t in only]
    ts = run_ts()
    names_of = {t: [n for n in (by_id.get(pl["person_id"], {}).get("full_name")
                                or by_id.get(pl["person_id"], {}).get("name_en")
                                for pl in squad[t].get("players", [])) if n] for t in teams}

    # ── 第一步：拿每队 items（联网并发 + 存 raw / 或 from-raw 读）──
    team_items = {}
    if args.from_raw:
        print(f"=== 从 raw 重提取  {args.from_raw}  {len(teams)} 队 ===")
        for t in teams:
            rf = f"{BASE}/raw/bg/{args.from_raw}/transfermarkt/tm_{t}.json"
            if os.path.exists(rf):
                team_items[t] = json.load(open(rf, encoding="utf-8"))
    else:
        print(f"=== Transfermarkt 联网采集  ts={ts}  {len(teams)} 队  并发 {args.workers} ===")
        def fetch(t):
            if not names_of[t]:
                return t, []
            items = apify_run({"searchQueries": names_of[t], "maxPlayersPerQuery": 1, "includeTransferHistory": True})
            save_raw_full(items, ts, t)                          # 各队不同文件，线程安全
            return t, items
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for fut in as_completed([ex.submit(fetch, t) for t in teams]):
                try:
                    t, items = fut.result(); team_items[t] = items
                    print(f"  [{t}] 采到 {len(items)} 条")
                except Exception as e:
                    print(f"  采集出错: {e}")
        write_source(ts, teams, sum(len(v) for v in team_items.values()))

    # ── 第二步：提取填充（主线程串行，写 persons 安全）──
    tot_ok = tot_warn = 0
    for t in teams:
        items = team_items.get(t, [])
        pids = [pl["person_id"] for pl in squad[t].get("players", [])]
        idx = {}
        for pid in pids:
            p = by_id.get(pid, {})
            for nm in (p.get("name_en"), p.get("full_name")):
                if nm: idx[norm(nm)] = pid
        for d in items:
            pid = idx.get(norm(d.get("name"))) or idx.get(norm(d.get("fullName")))
            if not pid:
                last = norm(d.get("name", "")).split(" ")[-1]
                pid = next((idx[k] for k in idx if k.endswith(" " + last) or k == last), None)
            if not pid:
                continue
            rec = by_id[pid]; plr = rec.setdefault("player", {})
            ext = extract(d, rec.get("birthdate"))
            if ext["tm_verified"] is False:                      # 出生年不符=搜错人→剔除 TM 数据
                for k in TM_KEYS: plr.pop(k, None)
                plr["tm_verified"] = False
                plr["tm_mismatch"] = f"出生年不符 维基{rec.get('birthdate')}≠TM{to_iso(d.get('dateOfBirth'))}（疑同名搜错人，TM数据已剔除）"
                tot_warn += 1
            else:
                plr.pop("tm_mismatch", None)
                for k, v in ext.items():
                    if v is not None: plr[k] = v
                if not rec.get("full_name") and ext["tm_full_name"]:
                    rec["full_name"] = ext["tm_full_name"]
                tot_ok += 1
    dump_json(persons_path(), sorted(by_id.values(), key=lambda p: p["person_id"]))
    print(f"\n完成 {len(teams)} 队 → persons.player（填充 {tot_ok} 人，剔除同名搜错 {tot_warn} 人）；raw 全量留底")


if __name__ == "__main__":
    main()
