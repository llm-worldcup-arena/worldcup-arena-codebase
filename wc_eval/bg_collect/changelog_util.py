#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【team_data 每队变更日志 · 统一写入】方便监督:每支队 <TEAM>/CHANGELOG.md 逐轮、逐条记录改动。
- 块A = summary.md 按原结构的增量(近期状态/⑦关键动态…)
- 块B = wc2026/ 世界杯专属块的增量(赛后播报/伤停/状态…)
两条线(integrate_match.py 块A、wc2026_build.py 块B)都调本工具,集中格式、杜绝各写各的。

用法(py 内):
  from changelog_util import append_change
  append_change(team_dir, snapshot="2026-06-12_1252", prev="2026-06-10_1310",
                block_a=["[近期状态] +1行: 2026-06-11 主 RSA 2-0"],
                block_b=["[赛后播报/] +2026-06-11_vs_RSA.md"],
                sources=["ESPN","FOX","match_broadcast(13源)"])
最新一轮置顶;同一轮重复调用则把新条目并入该轮(不重复建段)。
"""
import os
import re

CHANGELOG = "CHANGELOG.md"


def _round_header(snapshot, prev):
    base = f"## {snapshot}"
    return base + (f" (距上版 {prev})" if prev else "")


def append_change(team_dir, snapshot, prev=None, block_a=None, block_b=None,
                  sources=None, note=""):
    """把一轮改动写进 <team_dir>/CHANGELOG.md。最新轮置顶;同一 snapshot 段已存在则并入。"""
    block_a = block_a or []
    block_b = block_b or []
    sources = sources or []
    path = os.path.join(team_dir, CHANGELOG)
    team = os.path.basename(team_dir.rstrip("/"))

    # 组装本轮要追加的条目正文(不含 ## 段标题)
    lines = []
    if block_a:
        lines.append("**块A · summary.md(原结构)**")
        lines += [f"- {x}" for x in block_a]
    if block_b:
        lines.append("**块B · wc2026/(世界杯专属)**")
        lines += [f"- {x}" for x in block_b]
    if note:
        lines.append(f"**说明**:{note}")
    if sources:
        lines.append(f"**检索来源**:{', '.join(sources)}")
    if not lines:
        lines.append("- (本轮无新增)")
    body = "\n".join(lines)

    hdr = _round_header(snapshot, prev)
    existing = open(path, encoding="utf-8").read() if os.path.exists(path) else f"# {team} · 修改日志\n> 每轮改动逐条留底,最新置顶。块A=summary 原结构增量;块B=wc2026 专属块增量。\n"

    if hdr in existing:
        # 同一轮已存在 → 把新 body 追加进该段末尾(段到下一个 '## ' 或文件末)
        pat = re.compile(re.escape(hdr) + r".*?(?=\n## |\Z)", re.S)
        existing = pat.sub(lambda m: m.group(0).rstrip() + "\n" + body + "\n", existing, count=1)
        open(path, "w", encoding="utf-8").write(existing)
        return path

    # 新轮 → 插在标题行(# …)之后、其余轮之前(置顶)
    m = re.search(r"(^# .*?\n(?:>.*\n)?)", existing)
    head = m.group(1) if m else ""
    rest = existing[len(head):]
    new = head + f"\n{hdr}\n{body}\n\n" + rest.lstrip("\n")
    open(path, "w", encoding="utf-8").write(new)
    return path


if __name__ == "__main__":
    # 自测
    import tempfile
    d = tempfile.mkdtemp()
    td = os.path.join(d, "MEX")
    os.makedirs(td)
    append_change(td, "2026-06-12_1252", "2026-06-10_1310",
                  block_a=["[近期状态] +1行: 2026-06-11 主 RSA 2-0 世界杯A组第1轮",
                           "[⑦关键动态] +1行: 🟨 Montes 红牌停赛"],
                  block_b=["[赛后播报/] +2026-06-11_vs_RSA.md", "[伤停与可用性.md] +Montes 停赛"],
                  sources=["ESPN", "华盛顿邮报", "FOX", "match_broadcast(13源)"])
    print(open(os.path.join(td, "CHANGELOG.md"), encoding="utf-8").read())
