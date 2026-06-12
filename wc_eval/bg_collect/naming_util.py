#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【命名规范 · 统一校验】全工作区命名铁规集中在这里,各采集/整合脚本统一调,杜绝花名。
- 时间戳(raw 目录 / team_data 快照 / 预测批次):YYYY-MM-DD_HHMM(或基底 _base)
- 快照日期(data/bg/asof=):YYYY-MM-DD
配 CLAUDE.md「命名精确到分钟」铁律 + skill wc-data-collect / wc-incremental-update / wc-predict。
"""
import re
import datetime

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_(\d{4}|base)$")     # 日期_时分 或 日期_base
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")                # 日期


def now_ts():
    """当前时分戳 YYYY-MM-DD_HHMM。"""
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M")


def valid_ts(s, auto=False):
    """校验时间戳格式(YYYY-MM-DD_HHMM 或 _base)。
    auto=True 且 s 为空 → 返回当前时分;s 非空但不规范 → 直接报错(杜绝 _R1/_rerun 之类花名)。"""
    if not s:
        return now_ts() if auto else s
    if not _TS_RE.match(s):
        raise SystemExit(f"✗ 时间戳「{s}」不规范:必须 YYYY-MM-DD_HHMM(如 2026-06-12_1252)或 _base。")
    return s


def valid_asof(s, auto_today=False):
    """校验快照日期格式(YYYY-MM-DD)。auto_today=True 且 s 为空 → 返回今天。"""
    if not s:
        return datetime.date.today().strftime("%Y-%m-%d") if auto_today else s
    if not _DATE_RE.match(s):
        raise SystemExit(f"✗ asof 日期「{s}」不规范:必须 YYYY-MM-DD(如 2026-06-12)。")
    return s
