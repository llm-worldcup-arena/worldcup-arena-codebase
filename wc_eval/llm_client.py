#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 客户端 —— 读 config/llm.json + secret，调 DMXAPI（OpenAI 兼容）。供「预测」等需要 LLM 的环节统一使用。

key 来源优先级：① 环境变量（config 里 api_key_env 指定的名，如 DMX_API_KEY）② config/secrets.local.json（gitignore、不进库）。
统一在这里调 LLM，别在各脚本里硬编码 key / base_url。

跑：python3 llm_client.py "用一句话介绍世界杯"          # 自测
   python3 llm_client.py --model gpt-4o "..."            # 指定模型
   from llm_client import chat; chat([{"role":"user","content":"..."}], model="...")
"""
import os, json, argparse, urllib.request

ROOT = "/home/ubuntu/worldcup_2026"
CFG_PATH = f"{ROOT}/config/llm.json"
SECRET_PATH = f"{ROOT}/config/secrets.local.json"


def load_config():
    cfg = json.load(open(CFG_PATH, encoding="utf-8"))
    env_name = cfg.get("api_key_env", "")
    key = os.environ.get(env_name)
    if not key and os.path.exists(SECRET_PATH):          # 回退到本地 secret（gitignore）
        key = json.load(open(SECRET_PATH, encoding="utf-8")).get(env_name)
    if not key:
        raise SystemExit(f"✗ 缺 LLM key：设环境变量 {env_name} 或填 config/secrets.local.json")
    cfg["_key"] = key
    return cfg


def chat(messages, model=None, temperature=0.7, timeout=120, **kw):
    """发一轮对话，返回回复文本（OpenAI /chat/completions 兼容）。"""
    cfg = load_config()
    body = {"model": model or cfg["default_model"], "messages": messages, "temperature": temperature, **kw}
    req = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['_key']}"},
        method="POST")
    d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    return d["choices"][0]["message"]["content"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", default="用一句话介绍 2026 世界杯")
    ap.add_argument("--model", help="覆盖默认模型")
    a = ap.parse_args()
    print(chat([{"role": "user", "content": a.prompt}], model=a.model))


if __name__ == "__main__":
    main()
