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


def _secret(name):
    """读密钥：先环境变量，再 config/secrets.local.json（gitignore）。"""
    v = os.environ.get(name)
    if not v and os.path.exists(SECRET_PATH):
        v = json.load(open(SECRET_PATH, encoding="utf-8")).get(name)
    if not v:
        raise SystemExit(f"✗ 缺密钥 {name}：设环境变量或填 config/secrets.local.json")
    return v


def _kimi_search(messages, model, timeout, max_uses):
    """Kimi 官方直连（api.moonshot.cn）联网搜索 —— builtin $web_search 两步流程（DMXAPI 那条托管通道无服务端搜索，
    必须官方 key 直连）。实测要点：① k2.6 只允许 temperature=1；② 收到 $web_search tool_call 后把 arguments 原样
    回传(含 search_id),搜索由服务端执行;③ 回传的 assistant 消息必须补 reasoning_content 字段(思考模型要求)。"""
    key = _secret("MOONSHOT_API_KEY")
    auth = {"Authorization": f"Bearer {key}"}
    tools = [{"type": "builtin_function", "function": {"name": "$web_search"}}]
    msgs = list(messages)
    for _ in range(max_uses + 2):                                  # 限制总轮数，防失控
        d = _post("https://api.moonshot.cn/v1/chat/completions",
                  {"model": model, "messages": msgs, "temperature": 1, "tools": tools, "max_tokens": 8000},
                  auth, timeout)
        ch = d["choices"][0]
        msg = ch["message"]
        if ch.get("finish_reason") == "tool_calls":
            msgs.append({"role": "assistant", "content": msg.get("content") or "",
                         "reasoning_content": msg.get("reasoning_content") or "",
                         "tool_calls": msg["tool_calls"]})
            for tc in msg["tool_calls"]:
                msgs.append({"role": "tool", "tool_call_id": tc["id"],
                             "name": tc["function"]["name"], "content": tc["function"]["arguments"]})
            continue
        return msg.get("content") or ""
    return msgs[-1].get("content", "") if msgs else ""


def _zhipu_search(query, key, timeout=40):
    """调智谱独立搜索端点 /web_search,返回前 6 条摘要文本。供 GLM 函数调用执行联网。"""
    try:
        d = _post("https://open.bigmodel.cn/api/paas/v4/web_search",
                  {"search_engine": "search_std", "search_query": query},
                  {"Authorization": f"Bearer {key}"}, timeout)
        res = (d.get("search_result") or [])[:6]
        return "\n".join(f"[{i+1}] {r.get('title', '')}: {r.get('content', '')[:300]}"
                         f"（来源:{r.get('link', '')}）" for i, r in enumerate(res)) or "（无搜索结果）"
    except Exception as e:
        return f"（搜索失败:{str(e)[:60]}）"


def _glm_search(messages, model, timeout, max_uses):
    """GLM 智谱官方直连（open.bigmodel.cn）联网搜索 —— 函数调用 + 智谱自家 /web_search 执行（DMXAPI 那条托管通道
    无服务端搜索;智谱原生 in-chat web_search 工具实测不稳/易静默假搜,故改由模型自选 query、我方调智谱搜索端点执行,
    搜索引擎仍是智谱自家、公平）。glm-5.1 thinking 与函数调用可同开,temperature=1。"""
    key = _secret("ZHIPU_API_KEY")
    auth = {"Authorization": f"Bearer {key}"}
    tools = [{"type": "function", "function": {
        "name": "web_search",
        "description": "联网搜索实时信息（伤停/赛果/状态/赔率/新闻等），返回相关网页摘要",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "搜索关键词"}}, "required": ["query"]}}}]
    msgs = list(messages)
    for _ in range(max_uses + 2):
        d = _post("https://open.bigmodel.cn/api/paas/v4/chat/completions",
                  {"model": model, "messages": msgs, "thinking": {"type": "enabled"},
                   "tools": tools, "max_tokens": 8000, "temperature": 1.0}, auth, timeout)
        ch = d["choices"][0]
        msg = ch["message"]
        if ch.get("finish_reason") == "tool_calls" and msg.get("tool_calls"):
            msgs.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": msg["tool_calls"]})
            for tc in msg["tool_calls"]:
                q = ""
                try:
                    q = json.loads(tc["function"]["arguments"]).get("query", "")
                except Exception:
                    pass
                msgs.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": _zhipu_search(q, key) if q else "（空 query）"})
            continue
        return msg.get("content") or ""
    return msgs[-1].get("content", "") if msgs else ""


def chat_search(messages, model, temperature=0.3, timeout=300, max_uses=5):
    """带【真联网搜索】的一轮对话，返回回复文本。支持 claude*/gpt*/doubao*/gemini*（经 DMXAPI）+ kimi*/glm*（官方直连）。
    参数策略：各通道只传实测能过的最小集（gpt-5 系经 responses 不收 temperature → 不传）。"""
    cfg = load_config()
    root = cfg["base_url"].rstrip("/").removesuffix("/v1")          # https://www.dmxapi.com
    auth = {"Authorization": f"Bearer {cfg['_key']}"}
    m = model.lower()

    if m.startswith("kimi"):                                         # Moonshot 官方直连，不走 DMXAPI
        return _kimi_search(messages, model, timeout, max_uses)

    if m.startswith("glm"):                                          # 智谱官方直连，不走 DMXAPI
        return _glm_search(messages, model, timeout, max_uses)

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

    raise ValueError(f"{model} 无可用联网搜索通道（GLM 经 DMXAPI 为托管通道、无服务端搜索），请走 chat()")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", default="用一句话介绍 2026 世界杯")
    ap.add_argument("--model", help="覆盖默认模型")
    a = ap.parse_args()
    print(chat([{"role": "user", "content": a.prompt}], model=a.model))


if __name__ == "__main__":
    main()
