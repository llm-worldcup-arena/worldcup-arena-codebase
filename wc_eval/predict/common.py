#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预测公共件:读 summary / 调 6 模型(DMXAPI)/ 解析 JSON / 存预测。被 predict_match / group / global 共用。

🚨 真正跑模型前必须先向用户汇报(见 skill wc-predict / 记忆 feedback-eval-report-first)。
"""
import os, sys, json, re, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 让 import llm_client（在 wc_eval/）
from llm_client import chat

ROOT = "/home/ubuntu/worldcup_2026"
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


def ask_json(model_id, system, user, retries=2, temperature=0.3):
    """调 LLM 要结构化 JSON。模型可先分析、最后给 JSON → 抓【最后一个】能解析的 JSON 对象。失败重试。
    返回 {"_json": dict, "_raw": 全文}(保留分析全文,便于人看)。失败返回 None。"""
    for _ in range(retries + 1):
        try:
            txt = chat([{"role": "system", "content": system},
                        {"role": "user", "content": user}], model=model_id, temperature=temperature, timeout=300)
            for c in reversed(re.findall(r"\{[^{}]*\}", txt, re.S)):     # 取最后一个扁平 JSON(答案在末尾)
                try:
                    return {"_json": json.loads(c), "_raw": txt.strip()}
                except Exception:
                    continue
            m = re.search(r"\{.*\}", txt, re.S)                          # 兜底:贪婪
            if m:
                return {"_json": json.loads(m.group(0)), "_raw": txt.strip()}
        except Exception as e:
            print(f"      {model_id} 失败: {str(e)[:60]}")
    return None


def run_ts():
    """预测批次时间戳,精确到分钟(像 raw 命名规范)。"""
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
