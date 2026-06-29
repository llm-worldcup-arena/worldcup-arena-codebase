#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【世界杯·赛事播报 · 收集层】直抓网页原始 HTML，机械抽取**逐字正文**（全程不经任何模型/改写/翻译/总结），
   存成 raws/<source>/<source>.json。这是「我要的就是原文」的实现：urllib 拿原始 HTML → 去 script/style/导航
   → 抽 <p> 真句子段落 → 即网页原文。CC 自己的联网，不调 DMXAPI。顶级源若被反爬挡（返回空/403）→ 标记待 Apify。

   skill: wc-match-broadcast。源 URL 由 CC 用 WebSearch 找好，写进一个 urls.json 喂进来。

跑：python3 fetch_sources.py --match M1 --urls /tmp/urls_M1.json
   urls.json 格式：[{"name":"ap_via_kktv","source":"美联社AP(经KKTV)","url":"https://...","tier":"2","lang":"es"}, ...]
"""
import os, sys, json, argparse, re, ssl, shutil, unicodedata, html as H
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # worldcup_2026/
RUNS = f"{ROOT}/wc_runs"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
BLOCK = re.compile(r"(?is)<(script|style|noscript|svg|head|nav|footer|aside|form|figure)[^>]*>.*?</\1>")
SCOPE = re.compile(r'(?is)<(article|main)[^>]*>(.*?)</\1>')
DIVSCOPE = re.compile(r'(?is)<div[^>]*(?:class|id)=["\'][^"\']*'
                      r'(?:content|article|body|nota|cuerpo|entry|post|story|main|texto)[^"\']*["\'][^>]*>')


def decode(raw, resp):
    cs = resp.headers.get_content_charset()
    if not cs:
        m = re.search(rb'charset=["\']?\s*([\w-]+)', raw[:3000], re.I)
        cs = m.group(1).decode("ascii", "ignore") if m else None
    for enc in [cs, "utf-8", "cp1252", "latin-1"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


def _norm(t):
    t = re.sub(r"(?is)<[^>]+>", " ", t)                      # 去掉 JSON-LD body 里夹带的 HTML 标签
    t = H.unescape(t)
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\b(\w+)( \1\b)+", r"\1", t)                  # 去相邻重复词（Attendance Attendance）
    t = re.sub(r"[ \t]*\n[ \t]*", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = t.strip()
    # 去开头报头/标语短行（直到第一段实质正文）
    lines = t.split("\n")
    while len(lines) > 1 and len(lines[0]) < 60 and "." not in lines[0] and "。" not in lines[0]:
        lines.pop(0)
    t = "\n".join(lines).strip()
    # 截掉正文之后混入的直播流尾巴（仅当出现在 300 字之后，避免误伤正文）
    for mk in (" en vivo DECISIÓN", " en vivo MINUTO", " en directo ", "Minuto a minuto", "LIVE BLOG", "Sigue el minuto"):
        i = t.find(mk)
        if i > 300:
            t = t[:i].strip()
    return t


def _iter(d):
    if isinstance(d, dict):
        yield d
        for v in d.values():
            yield from _iter(v)
    elif isinstance(d, list):
        for v in d:
            yield from _iter(v)


def from_jsonld(html):
    """优先取出版方 <script type=ld+json> 里的 articleBody —— 各家自己存的整篇正文，最干净的原文。"""
    best = ""
    for m in re.finditer(r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html):
        raw = m.group(1).strip()
        data = None
        for cand in (raw, (raw[raw.find("{"):raw.rfind("}") + 1] if "{" in raw else "")):
            try:
                data = json.loads(cand); break
            except Exception:
                continue
        if not data:
            continue
        for obj in _iter(data):
            if isinstance(obj, dict):
                b = obj.get("articleBody")
                if isinstance(b, str) and len(b) > len(best):
                    best = b
    return best.strip()


def paras(scope):
    out, seen = [], set()
    for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", scope):
        t = H.unescape(re.sub(r"(?is)<[^>]+>", " ", p))
        t = re.sub(r"[ \t\r\f\v]+", " ", t).strip()
        if len(t) >= 40 and re.search(r"[.。!?！？]", t) and t not in seen:
            seen.add(t); out.append(t)
    return "\n\n".join(out)


def paras_best(html):
    h = BLOCK.sub(" ", html)
    cands = [m.group(2) for m in SCOPE.finditer(h)]
    for m in DIVSCOPE.finditer(h):
        cands.append(h[m.end():m.end() + 20000])
    cands.append(h)
    best = ""
    for c in cands:
        t = paras(c)
        if len(t) > len(best):
            best = t
    return best


# 头部出现这些 = 直播页/电视推广页，不是赛报原文 → 整源弃用
LEAD_JUNK = ("welcome to our live", "live coverage", "live blog", "stay with us for live",
             "cómo ver", "dónde ver", "a qué hora", "qué canal", "sigue en vivo", "telecast",
             "será transmitido", "transmisión en vivo")
# 正文之后出现这些 = nav/电视/版权/社媒/直播流尾巴 → 从这里截断
TAIL_CUTS = ("Rate the players", "What the result means", "In pictures", "comeback in pictures",
             "Follow our World Cup coverage", "Thank you for joining", "Bienvenidos a la cobertura",
             "minuto a minuto", "Suscríb", "Copyright", "Derechos de autor", "Un producto de",
             "Todos los derechos", "Sigue el minuto", "dónde ver", "A qué hora", "Cómo ver",
             "Mirá también", "Seguí leyendo", "TE PUEDE INTERESAR", "LEE TAMBIÉN", "en vivo por",
             "Manténgase al tanto", "Estamos en", "se transmite", "Con información de", "EN VIVO",
             "Más noticias", "También te puede", "Lee también", "Síguenos",
             "¿Lo último", "Todo lo que debe saber", "deporte mundial está",
             "keep up to date with", "Follow Al Jazeera", "Al Jazeera Sport", "Sign up for",
             "media platform and only provides", "特别声明", "本文系", "责任编辑", "相关推荐",
             "热门跟贴", "热门评论", "返回搜狐", "原标题", "网易号", "免责声明", "举报", "点击进入专题",
             "更多精彩", "声明：", "延伸阅读", "推荐阅读", "关注我们", "扫码", "编辑：")


def article_clean(t):
    t = re.sub(r"As it happened \|.*?Sky Sports App", " ", t, flags=re.S)   # 去 Sky 中段导航条
    t = re.sub(r"[^\n]*pic\.twitter\.com/\S+[^\n]*", " ", t)                # 去嵌入推文引用块
    t = re.sub(r"^\s*Por [^\n.]{2,70}?,\s*[A-Z]{2,3}\s+", "", t)            # 去开头署名（Por X …, DF ）
    for mk in TAIL_CUTS:                                                     # 截掉正文后的 nav/电视/版权/社媒尾巴
        i = t.find(mk, 250)
        if i != -1:
            t = t[:i]
    t = re.sub(r"[ \t]*\n[ \t]*", "\n", t).strip()
    frag = re.split(r"[.!?。”\"]", t)[-1]                                    # 截断后若结尾残留无标点短碎片 → 回退到上个句末
    if 0 < len(frag.strip()) <= 50:
        t = t[:len(t) - len(frag)].strip()
    return t


def is_junk(t):
    """头部就是直播/电视推广 = 不是赛报原文。"""
    return any(m in t[:220].lower() for m in LEAD_JUNK)


def extract(html):
    """同时算 JSON-LD 正文 + 段落版，挑更干净的，再统一清洗（去导航/电视/版权尾巴）。"""
    para = _norm(paras_best(html))
    body = from_jsonld(html)
    jl = _norm(body) if body else ""
    bad = ((0 <= jl.find(" en vivo ") < 300)                 # 只躲「直播流」（混入别场），嵌入推文是正常的
           or "EN VIVO" in jl[:400] or "LIVE BLOG" in jl[:400] or "Minuto a minuto" in jl[:400])
    if len(jl) >= 400 and not bad:                           # JSON-LD 正文只要不脏就优先（出版方自带、最权威）
        return article_clean(jl), "jsonld:articleBody"
    return (article_clean(para), "html:paragraphs") if para else (article_clean(jl), "jsonld")


def meta(html):
    t = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    title = H.unescape(re.sub(r"\s+", " ", t.group(1)).strip()) if t else None
    og = re.search(r'(?is)<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html)
    if og:
        title = H.unescape(og.group(1).strip())
    pub = re.search(r'(?is)<meta[^>]+(?:property|name|itemprop)=["\']'
                    r'(?:article:published_time|datePublished|publishdate|publish-date)["\']'
                    r'[^>]+content=["\']([^"\']+)', html)
    return title, (pub.group(1) if pub else None)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es,en;q=0.8"})
    resp = urllib.request.urlopen(req, timeout=40, context=CTX)
    raw = resp.read()
    html = decode(raw, resp)
    title, pub = meta(html)
    text, method = extract(html)
    return text, method, title, pub, len(raw)


def resolve_match(mid):
    ms = json.load(open(f"{RUNS}/data_reference/matches.json", encoding="utf-8"))
    teams = {t["team_id"]: t for t in json.load(open(f"{RUNS}/data_reference/teams.json", encoding="utf-8"))}
    nm = lambda c, k: (teams.get(c, {}).get(k) or c)
    m = next((x for x in ms if x.get("match_id") == mid), None)
    if not m:
        sys.exit(f"✗ 无 {mid}")
    grp = m.get("group", "")
    comp = f"小组赛·{grp}组" if m.get("round") == "group" and grp else (m.get("round") or "世界杯")
    a, b = m["team_a"], m["team_b"]
    return {"date": m["date"], "home": a, "away": b,
            "home_en": nm(a, "name_en"), "away_en": nm(b, "name_en"),
            "home_zh": nm(a, "name_zh"), "away_zh": nm(b, "name_zh"),
            "comp": comp, "match_id": mid, "slug": f"{m['date']}_{a}_vs_{b}"}


def apify_token():
    t = os.environ.get("APIFY_TOKEN")
    if not t:
        p = f"{ROOT}/config/secrets.local.json"
        if os.path.exists(p):
            t = json.load(open(p, encoding="utf-8")).get("APIFY_TOKEN")
    return t


def fetch_apify(url, token):
    """直抓被反爬/JS 挡住时的兜底：Apify website-content-crawler（无头浏览器渲染 + 正文抽取）。"""
    act = "apify~website-content-crawler"
    inp = {"startUrls": [{"url": url}], "maxCrawlPages": 1,
           "crawlerType": "playwright:firefox", "saveMarkdown": False}
    api = f"https://api.apify.com/v2/acts/{act}/run-sync-get-dataset-items?token={token}"
    req = urllib.request.Request(api, data=json.dumps(inp).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    items = json.loads(urllib.request.urlopen(req, timeout=300).read())
    if not items:
        return "", None
    it = items[0]
    return article_clean(_norm(it.get("text") or "")), (it.get("metadata") or {}).get("title")


def _na(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def relevant(text, md):
    """正文是否真讲本场（防 Apify 跳转/抓串稿，如 Yahoo→USMNT、ESPN→分析专栏）。重音不敏感、含中文队名。"""
    blob = _na(text)
    keys = [md.get(k) for k in ("home_en", "away_en", "home", "away", "home_zh", "away_zh")]
    return sum(blob.count(_na(k)) for k in keys if k) >= 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True, help="matches.json 的 match_id，如 M1")
    ap.add_argument("--urls", required=True, help="urls.json：[{name,source,url,tier,lang}]")
    ap.add_argument("--min", type=int, default=300, help="正文低于此字数视作被挡/失败，标待 Apify")
    ap.add_argument("--no-apify", action="store_true", help="只做快速直抓,不启用 Apify 兜底")
    a = ap.parse_args()
    md = resolve_match(a.match)
    entries = json.load(open(a.urls, encoding="utf-8"))
    base = f"{RUNS}/data_processed/match_broadcast/{md['slug']}/raws"
    print(f"▶ 直抓真原文 {md['home_en']} vs {md['away_en']}（{md['date']}）→ {len(entries)} 源")
    token = apify_token()
    if token:
        print("  （APIFY_TOKEN 已配：直抓被挡的源将自动 Apify 兜底）")
    ok = dropped = 0
    for e in entries:
        name = e["name"]; method = "fail"
        try:
            text, method, title, pub, rawlen = fetch(e["url"])
        except Exception as ex:
            text, title, pub, rawlen = "", None, None, 0
            print(f"  ✗ {name:20s} 直抓异常：{str(ex)[:60]}")
        # ── 直抓被挡（空/反爬/直播垃圾）→ 有 token 则用 website-content-crawler 兜底（渲染 JS、绕反爬）──
        if (len(text) < a.min or is_junk(text)) and token and not a.no_apify and e.get("apify", True):
            try:
                atext, atitle = fetch_apify(e["url"], token)
                if len(atext) >= a.min and not is_junk(atext):
                    text, method, title = atext, "apify:website-content-crawler", (atitle or title)
                    print(f"  ↻ {name:18s} 直抓被挡 → Apify 兜底 ✅ {len(text)}字")
            except Exception as ex:
                print(f"  ✗ {name:18s} Apify 兜底失败：{str(ex)[:60]}")
        d = f"{base}/{name}"
        # ── 质量门：太短=反爬挡；头=直播/电视推广=非赛报；Apify 抓回与本场无关=串稿 → 一律弃用、清旧目录 ──
        off_topic = method and method.startswith("apify") and text and not relevant(text, md)
        if len(text) < a.min or is_junk(text) or off_topic:
            why = ("与本场无关(Apify 串稿/跳转)" if off_topic else
                   "反爬/空白" if len(text) < a.min else "直播页/电视推广(非赛报原文)")
            if os.path.isdir(d):
                shutil.rmtree(d)
            print(f"  ⚠️ 弃用 {name:18s} {len(text):5d}字（{why}）→ 待换源")
            dropped += 1
            continue
        os.makedirs(d, exist_ok=True)
        obj = {"source": e.get("source", name), "url": e["url"], "title": title,
               "published": pub or e.get("published"), "tier": e.get("tier"),
               "lang": e.get("lang"), "match": md,
               "fetched": f"raw-HTML 直抓 + 抽取({method}) + 清洗（逐字、未经任何模型/改写/翻译）",
               "status": "ok", "original_text": text,
               "_note": "网页赛报正文逐字留底（已去直播/电视/版权/导航杂讯）。"}
        json.dump(obj, open(f"{d}/{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        ok += 1; print(f"  ✅ {name:20s} {len(text):5d}字 原文  [{(title or '')[:38]}]")
    print(f"✔ 完成：{ok} 源干净赛报原文，{dropped} 源弃用 → {base}")


if __name__ == "__main__":
    main()
