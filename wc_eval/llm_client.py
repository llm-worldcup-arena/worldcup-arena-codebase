#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 客户端 —— 读 config/llm.json + secret，调 DMXAPI（OpenAI 兼容）。供「预测」等需要 LLM 的环节统一使用。

key 来源优先级：① 环境变量（config 里 api_key_env 指定的名，如 DMX_API_KEY）② config/secrets.local.json（gitignore、不进库）。
统一在这里调 LLM，别在各脚本里硬编码 key / base_url。

跑：python3 llm_client.py "用一句话介绍世界杯"          # 自测
   python3 llm_client.py --model gpt-4o "..."            # 指定模型
   from llm_client import chat; chat([{"role":"user","content":"..."}], model="...")
"""
import os, json, argparse, re, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 仓库根(由本文件位置推导,可移植;不再硬编码绝对路径)
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


_BAD_SOURCE_LINE = re.compile(r"epochtimes|theepochtimes|大纪元|ntdtv|ntd\.com|新唐人|soundofhope|希望之声|"
                              r"minghui|明慧|secretchina|看中国|aboluowang|阿波罗|dajiyuan|bannedbook|"
                              r"dafahao|falun|法轮", re.I)


def _sanitize_for_moonshot(messages):
    """Moonshot content_filter 对少量敏感来源名会拒整段 prompt；仅删这些来源行，不改原始留档。"""
    out = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            m = {**m, "content": "\n".join(line for line in c.splitlines() if not _BAD_SOURCE_LINE.search(line))}
        out.append(m)
    return out


def _kimi_search(messages, model, timeout, max_uses):
    """Kimi 官方直连（api.moonshot.cn）联网搜索 —— builtin $web_search 两步流程（DMXAPI 那条托管通道无服务端搜索，
    必须官方 key 直连）。实测要点：① k2.6 只允许 temperature=1；② 收到 $web_search tool_call 后把 arguments 原样
    回传(含 search_id),搜索由服务端执行;③ 回传的 assistant 消息必须补 reasoning_content 字段(思考模型要求)。"""
    key = _secret("MOONSHOT_API_KEY")
    auth = {"Authorization": f"Bearer {key}"}
    tools = [{"type": "builtin_function", "function": {"name": "$web_search"}}]
    msgs = list(messages)
    sanitized = False
    for _ in range(max_uses + 2):                                  # 限制总轮数，防失控
        try:
            d = _post("https://api.moonshot.cn/v1/chat/completions",
                      {"model": model, "messages": msgs, "temperature": 1, "tools": tools, "max_tokens": 8000},
                      auth, timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code == 400 and "content_filter" in body and not sanitized:
                print("  ! Kimi 官方 content_filter,清理已知坏来源行后重试")
                msgs = _sanitize_for_moonshot(messages)
                sanitized = True
                continue
            raise
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


def web_search_urls(query, n=12, timeout=150):
    """通用联网搜索 → 返回 [{title, content, link}] **真实 URL 列表**。全 py 驱动、可复现,不需 agent。
    主通道 = Apify google-search-scraper(真实 Google 有机结果,质量高);失败回退智谱 /web_search。"""
    # 主:Apify Google 搜索(真实 Google organic results,FIFA/Sky/ESPN/Guardian 等)
    try:
        token = _secret("APIFY_TOKEN")
        d = _post(f"https://api.apify.com/v2/acts/apify~google-search-scraper/"
                  f"run-sync-get-dataset-items?token={token}",
                  {"queries": query, "maxPagesPerQuery": 1, "resultsPerPage": max(n, 10), "countryCode": "us"},
                  {"Content-Type": "application/json"}, timeout)
        org = []
        for it in (d or []):
            org += it.get("organicResults") or []
        if org:
            return [{"title": r.get("title", ""), "content": (r.get("description") or "")[:200],
                     "link": r.get("url", "")} for r in org[:n] if r.get("url")]
    except Exception:
        pass
    # 回退:智谱搜索端点
    try:
        key = _secret("ZHIPU_API_KEY")
        d = _post("https://open.bigmodel.cn/api/paas/v4/web_search",
                  {"search_engine": "search_std", "search_query": query},
                  {"Authorization": f"Bearer {key}"}, 40)
        return [{"title": r.get("title", ""), "content": (r.get("content") or "")[:200],
                 "link": r.get("link", "")} for r in (d.get("search_result") or [])[:n] if r.get("link")]
    except Exception:
        return []


def _glm_search(messages, model, timeout, max_uses):
    """GLM 联网搜索 —— 优先走 Z.AI/智谱官方 glm-5.2；联网由模型自选 query、我方用 web_search_urls(Apify Google)
    执行后喂回，保持与 DMX 模型相同的外部搜索执行路径。官方通道异常时回退 DMX 托管 glm，避免单点阻断。"""
    cfg = load_config()
    tools = [{"type": "function", "function": {
        "name": "web_search",
        "description": "联网搜索实时信息（伤停/赛果/状态/赔率/新闻等），返回相关网页摘要",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "搜索关键词"}}, "required": ["query"]}}}]

    def run_loop(url, auth, mid):
        msgs = list(messages)
        used_tool = False
        glm_max_uses = min(max_uses, int(os.environ.get("WC_GLM_MAX_USES", "3")))
        for _ in range(glm_max_uses + 1):                             # 默认最多 3 轮搜索,可用环境变量为慢场次收口
            d = _post(url, {"model": mid, "messages": msgs, "thinking": {"type": "enabled"},
                            "tools": tools, "max_tokens": 8000}, auth, timeout)
            ch = d["choices"][0]
            msg = ch["message"]
            if ch.get("finish_reason") == "tool_calls" and msg.get("tool_calls"):
                used_tool = True
                msgs.append({"role": "assistant", "content": msg.get("content") or "",
                             "reasoning_content": msg.get("reasoning_content") or "",
                             "tool_calls": msg["tool_calls"]})
                for tc in msg["tool_calls"]:
                    q = ""
                    try:
                        q = json.loads(tc["function"]["arguments"]).get("query", "")
                    except Exception:
                        pass
                    hits = web_search_urls(q, n=6) if q else []
                    txt = "\n".join(f"- {h['title']}：{h['content']}（{h['link']}）" for h in hits) or "（无结果）"
                    msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": txt})
                continue
            return msg.get("content") or ""
        if used_tool:
            msgs.append({"role": "user", "content": "请停止继续搜索，直接基于以上资料完成最终回答，并在最后输出唯一 JSON。"})
            d = _post(url, {"model": mid, "messages": msgs, "thinking": {"type": "enabled"},
                            "max_tokens": 8000}, auth, timeout)
            return d["choices"][0]["message"].get("content") or ""
        return msgs[-1].get("content", "") if msgs else ""

    try:
        key = _secret("ZHIPU_API_KEY")
        return run_loop("https://api.z.ai/api/paas/v4/chat/completions",
                        {"Authorization": f"Bearer {key}"}, "glm-5.2")
    except Exception as e:
        print(f"  ! GLM 官方通道失败,回退 DMX:{str(e)[:120]}")
        return run_loop(cfg["base_url"].rstrip("/") + "/chat/completions",
                        {"Authorization": f"Bearer {cfg['_key']}"}, model)


def _openrouter_search(messages, model, timeout, max_uses=5):
    """OpenRouter 通道(2026-06-18 定):Claude/GPT/Gemini 走这里(id 带斜杠,如 anthropic/claude-opus-4.8、
    openai/gpt-5.5-pro、google/gemini-3.1-pro-preview)。reasoning:{effort:high}=最高档思考 + 联网。
    实测各家小坑:① GPT 思考极重(~1.6万tok)→ 给大预算 max_tokens=24000(不然思考吃光、答案空);
    ② Gemini 必须用 web 插件(不是 :online)才回引用;其余 :online。Kimi/GLM 仍官方直连、Seed 仍 DMXAPI。"""
    key = _secret("OPENROUTER_API_KEY")
    prov = model.split("/")[0]                                       # anthropic / openai / google
    use_plugin = (prov == "google")                                 # Gemini:web 插件才出引用注解
    mid = model if use_plugin else model + ":online"
    body = {"model": mid, "messages": messages,
            "reasoning": {"effort": "high"},                         # 最高档思考
            "max_tokens": 24000 if prov == "openai" else 16000}      # GPT 思考极重,给足预算
    if use_plugin:
        body["plugins"] = [{"id": "web", "max_results": max_uses}]
    d = _post("https://openrouter.ai/api/v1/chat/completions", body,
              {"Authorization": f"Bearer {key}", "X-Title": "wc-arena"}, timeout)
    return d["choices"][0]["message"].get("content") or ""


def chat_search(messages, model, temperature=0.3, timeout=300, max_uses=5):
    """带【真联网搜索】的一轮对话，返回回复文本。支持 claude*/gpt*/doubao*/gemini*（经 DMXAPI）+ kimi*/glm*（官方直连）。
    参数策略：各通道只传实测能过的最小集（gpt-5 系经 responses 不收 temperature → 不传）。"""
    cfg = load_config()
    root = cfg["base_url"].rstrip("/").removesuffix("/v1")          # https://www.dmxapi.com
    auth = {"Authorization": f"Bearer {cfg['_key']}"}
    m = model.lower()

    if "/" in m:                                                     # OpenRouter 通道:id 带斜杠(anthropic/openai/google) → Claude/GPT/Gemini
        return _openrouter_search(messages, model, timeout, max_uses)

    if m.startswith("kimi"):                                         # Moonshot 官方直连，不走 DMXAPI
        return _kimi_search(messages, model, timeout, max_uses)

    if m.startswith("glm"):                                          # 智谱官方直连，不走 DMXAPI
        return _glm_search(messages, model, timeout, max_uses)

    if m.startswith("claude"):                                       # Anthropic 原生：system 提到顶层参数
        sys_txt = "\n".join(x["content"] for x in messages if x["role"] == "system")
        body = {"model": model, "max_tokens": 32000,                  # thinking 模型禁自定温度 → 不传 temperature
                "thinking": {"type": "enabled", "budget_tokens": 24000},  # 最高档思考(opus-4-8 需显式开;预算=上限,实际用多少算多少;-thinking后缀版会自动开但仍兼容)
                "messages": [x for x in messages if x["role"] != "system"],
                "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}]}
        if sys_txt:
            body["system"] = sys_txt
        d = _post(f"{root}/v1/messages", body,
                  {**auth, "x-api-key": cfg["_key"], "anthropic-version": "2023-06-01"}, timeout)
        return "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")

    if m.startswith("gpt") or m.startswith("doubao"):                # OpenAI Responses 兼容通道
        rbody = {"model": model, "input": messages, "tools": [{"type": "web_search"}],
                 "reasoning": {"effort": "high"}}                     # 最高档思考:gpt-5.5 与 豆包 seed 都吃此参数(实测豆包 reasoning 1067→1638 tok)
        d = _post(f"{root}/v1/responses", rbody, auth, timeout)
        return "".join(c.get("text", "") for o in d.get("output", []) if o.get("type") == "message"
                       for c in o.get("content", []))

    if m.startswith("gemini"):                                       # Google 原生：google_search 接地
        sys_txt = "\n".join(x["content"] for x in messages if x["role"] == "system")
        body = {"contents": [{"role": "user", "parts": [{"text": x["content"]}]}
                             for x in messages if x["role"] != "system"],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": temperature, "thinkingConfig": {"thinkingBudget": 24576}}}  # 最高档思考(默认就思考,显式给高预算)
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
