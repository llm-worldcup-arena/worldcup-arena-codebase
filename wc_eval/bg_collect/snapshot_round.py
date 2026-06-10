#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【增量更新 · 版本链 · 补充工具】复制 team_data 最新日期版本 → 一个新快照。
配 skill `wc-incremental-update`。每轮赛后增量都在【最新版的副本】上做，不在旧版本/base 上直接改。

版本链：base(赛前) →复制→ R1 →复制→ R2 …  每个新快照 = 复制上一个最新版 + integrate 本轮新比赛。

跑：python3 snapshot_round.py --name 2026-06-15_R2                      # 自动找最新版、cp 成新快照
   python3 snapshot_round.py --name 2026-06-15_R2 --from 2026-06-11_R1  # 指定源版本
"""
import os, shutil, argparse, glob, re
from collect_squads import BASE

TD = f"{BASE}/team_data"


def latest_version():
    """team_data 里日期最新的版本目录名（名形如 YYYY-MM-DD_xxx，字典序=时间序）。"""
    vs = [os.path.basename(d.rstrip("/")) for d in glob.glob(f"{TD}/*/")
          if re.match(r"\d{4}-\d{2}-\d{2}", os.path.basename(d.rstrip("/")))]
    return sorted(vs)[-1] if vs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="新快照目录名，如 2026-06-15_R2")
    ap.add_argument("--from", dest="src", help="源版本（默认自动取 team_data 最新日期版）")
    a = ap.parse_args()

    src = a.src or latest_version()
    if not src:
        raise SystemExit("✗ team_data 下没有版本可复制")
    src_path, dst_path = f"{TD}/{src}", f"{TD}/{a.name}"
    if not os.path.exists(src_path):
        raise SystemExit(f"✗ 源版本不存在：{src}")
    if os.path.exists(dst_path):
        raise SystemExit(f"✗ {a.name} 已存在，换个名或先删")

    shutil.copytree(src_path, dst_path)
    n = len(glob.glob(f"{dst_path}/*/summary.md"))
    open(f"{dst_path}/_snapshot.md", "w", encoding="utf-8").write(
        f"# 增量快照 · {a.name}\n"
        f"- **复制自最新版**：`{src}`\n"
        f"- **用途**：本轮赛后用 `integrate_match.py --td {a.name}` 增量加入新踢的比赛后，喂 LLM 预测下一轮\n"
        f"- **防泄露**：只 integrate **已踢完、非待预测** 的场次（integrate 再兜 date≤today）\n"
        f"- **绝不**在此快照重跑 gen/replace/update（会冲掉手补）\n")
    print(f"✅ 复制最新版 {src} → {a.name}（{n} 队）")
    print(f"   下一步：collect_match → agent 补 → integrate_match.py <m.json> --td {a.name}")


if __name__ == "__main__":
    main()
