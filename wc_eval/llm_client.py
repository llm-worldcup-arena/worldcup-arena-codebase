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


# ── 联网搜索版：搜索不是 prompt 能开的，是各家 API 的「工具/参数」，且接口各不相同（2026-06-11 实测 DMXAPI）：
#    Claude → Anthropic 原生 /v1/messages + web_search 工具；GPT / 豆包 → /v1/responses + web_search 工具；
#    Gemini → 原生 /v1beta:generateContent + google_search 工具；Kimi / GLM 经 DMXAPI 为第三方托管通道，
#    无服务端搜索（喂 tools 会被丢弃或只回 tool_call 没人执行）→ 这俩仍走上面的 chat()，评测需注明不对称。

def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def chat_search(messages, model, temperature=0.3, timeout=300, max_uses=5):
    """带【真联网搜索】的一轮对话，返回回复文本。只支持 claude*/gpt*/doubao*/gemini*，其余抛 ValueError。
    参数策略：各通道只传实测能过的最小集（gpt-5 系经 responses 不收 temperature → 不传）。"""
    cfg = load_config()
    root = cfg["base_url"].rstrip("/").removesuffix("/v1")          # https://www.dmxapi.com
    auth = {"Authorization": f"Bearer {cfg['_key']}"}
    m = model.lower()

    if m.startswith("claude"):                                       # Anthropic 原生：system 提到顶层参数
        sys_txt = "\n".join(x["content"] for x in messages if x["role"] == "system")
        body = {"model": model, "max_tokens": 16000,                  # thinking 模型禁自定温度 → 不传 temperature
                "messages": [x for x in messages if x["role"] != "system"],
                "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}]}
        if sys_txt:
            body["system"] = sys_txt
        d = _post(f"{root}/v1/messages", body,
                  {**auth, "x-api-key": cfg["_key"], "anthropic-version": "2023-06-01"}, timeout)
        return "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")

    if m.startswith("gpt") or m.startswith("doubao"):                # OpenAI Responses 兼容通道
        d = _post(f"{root}/v1/responses",
                  {"model": model, "input": messages, "tools": [{"type": "web_search"}]}, auth, timeout)
        return "".join(c.get("text", "") for o in d.get("output", []) if o.get("type") == "message"
                       for c in o.get("content", []))

    if m.startswith("gemini"):                                       # Google 原生：google_search 接地
        sys_txt = "\n".join(x["content"] for x in messages if x["role"] == "system")
        body = {"contents": [{"role": "user", "parts": [{"text": x["content"]}]}
                             for x in messages if x["role"] != "system"],
                "tools": [{"google_search": {}}], "generationConfig": {"temperature": temperature}}
        if sys_txt:
            body["systemInstruction"] = {"parts": [{"text": sys_txt}]}
        d = _post(f"{root}/v1beta/models/{model}:generateContent", body,
                  {**auth, "x-goog-api-key": cfg["_key"]}, timeout)
        parts = d["candidates"][0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))   # 滤掉思考块

    raise ValueError(f"{model} 经 DMXAPI 无服务端联网搜索（Kimi/GLM 为托管通道），请走 chat()")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", default="用一句话介绍 2026 世界杯")
    ap.add_argument("--model", help="覆盖默认模型")
    a = ap.parse_args()
    print(chat([{"role": "user", "content": a.prompt}], model=a.model))


if __name__ == "__main__":
    main()
