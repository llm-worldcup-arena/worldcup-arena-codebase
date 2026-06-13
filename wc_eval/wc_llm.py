#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【工具型 LLM · 统一入口】世界杯流程里所有"判断/生成/质检"类 LLM 调用都走这里——
**不再由对话里的 agent 临场做(那样换个对话就不可复现),而是 py 代码调 DMXAPI 的顶尖 Kimi**。

为什么单独一个模块:
  - 评测被测的 6 模型走 llm_client.chat_search()(带搜索、各家通道);
  - 这里是"干活的工人 LLM"(judge/clean/generate/audit/review),统一用 `Kimi-K2-Thinking`
    (DMXAPI 实测可用、返回干净 JSON、thinking 旗舰),便宜稳定、可并行。
  - 谁来跑都一样:导入本模块或命令行调,结果可复现,与 agent 当前对话无关。

并行:pmap() 用线程池(LLM 调用是 IO 等待,线程足够);默认 8 路,失败重试。

提供的工人(每个都有 py 函数 + CLI):
  judge_news      新闻三件套(新?要?对?)——是否新/要不要加/正确性
  clean_loop      数据清洁度自检(脏不脏/废话多不多)+ 修改循环(≤3 次)
  coach_brief     教练结构化 JSON + 收集信息 → 多层可读简介(覆盖 JSON + 多元素)
  predictable_long  赛事播报 long → "可预测版"(留全信息、情感高度概括)+ 质检
  snapshot_audit  预测前:通读两队 summary 找 自相矛盾/过期/泄露(语义级把关)
  postmatch_review 赛后:6 模型谁对谁错、错在哪类市场 的误差分析(论文素材)

跑:python3 wc_llm.py selftest
   python3 wc_llm.py judge-news --news /tmp/n.json --repo /tmp/titles.txt --summary /tmp/s.md
"""
import os, sys, json, re, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import chat, load_config

# 工具型 LLM 的模型/温度【从 config/llm.json 读,不写死在代码里】(本仓会 release;可变项进配置)。
# config 缺这两项时回退到合理默认(DMXAPI 顶尖 Kimi-thinking)。
_cfg = load_config()
WORKER_MODEL = _cfg.get("worker_model", "Kimi-K2-Thinking")
_TEMP = _cfg.get("worker_temperature", 1)


# ════════════════════════ 底层:JSON 调用 + 并行 ════════════════════════

def _strip_fence(t):
    """去掉 ```json ... ``` 围栏与 thinking 前言,取最外层 JSON 对象/数组(第一个开括号 → 最后一个对应闭括号)。"""
    t = re.sub(r"```(?:json)?", "", t).strip()
    cands = []
    for op, cl in (("{", "}"), ("[", "]")):
        i, j = t.find(op), t.rfind(cl)      # 第一个开 → 最后一个闭(对嵌套对象正确)
        if 0 <= i < j:
            cands.append((i, t[i:j + 1]))
    if cands:
        return min(cands, key=lambda c: c[0])[1]   # 取最靠前那个开括号(对象优先于行内数组)
    return t


def kimi_json(system, user, retries=3, timeout=180, model=WORKER_MODEL):
    """调 Kimi 要 JSON,解析失败重试。返回 dict/list,彻底失败抛异常。"""
    last = None
    for k in range(retries):
        try:
            raw = chat([{"role": "system", "content": system},
                        {"role": "user", "content": user}],
                       model=model, temperature=_TEMP, timeout=timeout)
            return json.loads(_strip_fence(raw))
        except Exception as e:
            last = e
    raise RuntimeError(f"kimi_json 解析失败({retries}次):{str(last)[:120]}")


def kimi_text(system, user, timeout=180, model=WORKER_MODEL):
    """调 Kimi 要纯文本(生成类)。"""
    return chat([{"role": "system", "content": system},
                 {"role": "user", "content": user}], model=model, temperature=_TEMP, timeout=timeout)


def pmap(fn, items, workers=8, label=""):
    """并行 map(线程池);返回与 items 等长的结果(异常位置为 None)。LLM 调用是 IO 等待,线程并行有效。"""
    out = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut = {ex.submit(fn, x): i for i, x in enumerate(items)}
        done = 0
        for f in as_completed(fut):
            i = fut[f]
            try:
                out[i] = f.result()
            except Exception as e:
                out[i] = {"_error": str(e)[:120]}
            done += 1
            if label:
                print(f"  [{label}] {done}/{len(items)}", end="\r", file=sys.stderr)
    if label:
        print(f"  [{label}] {len(items)}/{len(items)} 完成", file=sys.stderr)
    return out


# ════════════════════════ 工人 1:新闻三件套(新?要?对?) ════════════════════════

JUDGE_SYS = """你是世界杯数据管道的新闻审核员。对一条新闻做三判,只输出 JSON,不要解释。
**总原则:信息以"全"为主**——只要和这支球队/这场比赛沾边、能帮人更全面地了解或预测,就尽量收;不要求和预测【强】相关。宁可多带,只要干净、真实、不重复。
① is_new(是否新):对照"已有仓库标题"和"该队 summary ⑦已写内容",这条是否带来未记录过的新信息?
   - **完全是旧内容的重复**=false;带来任何新角度/新细节/新数据=true。
   - 🚨 **主题级判重(不只看文字)**:若这条与⑦里已有某条是【同一主题】(尤其【预测首发/阵型】【博彩赔率】【伤情综述】这类反复出现的),且**没有带来实质新口径**(只是换个源、换种措辞、阵型说法略不同但信息等价)→ **is_new=false**(纯主题dup,挡在门外);只有带来**真不同的新口径**(如全新阵型、新伤员、赔率明显变动)才 true。目标:同一主题⑦里不堆 2-3 条近似行。
② should_add(要不要加):**默认 true,从宽**。凡涉及该队的:伤停/停赛/名单/首发/阵型/战术/近期状态与战绩/赔率与盘口/对手与对位/动机士气/历史交锋/场地天气/球员个人状态/教练表态/舆论氛围……**统统可加**。只有这几类才 false:纯电视转播/订阅/购票/观赛指南这类与足球内容无关的后勤信息、纯标题党无实质、与已写内容【完全】重复。**赔率/赛前预览/状态回顾都要收(它们沾边且有信息量)**。
③ is_correct(正确性):事实是否可信?能从正文自证、人物归属正确(防张冠李戴:确认这人属于这支队/这个国家)、时效正确(非旧闻、未泄露未踢比分结果)。存疑=false。
④ 若三判全 true,给 summary_line:一句话中文、模仿足球档案口吻、含关键信息(数字/赔率/状态/日期)、末尾标「多源核实:源名」。**信息多时可写成 1-2 句,把沾边的有用点都带上,但要精炼干净、不注水**。
   ⚠️ **赔率写清楚、别糊**:博彩赔率要分两边写明、并注大热/冷门,**绝不能和"让球/受让"混着写**。
     正例:「博彩:瑞士 -500(大热)、卡塔尔 +1300(冷门),平 +650」。反例(禁止):「卡塔尔+1300大幅受让瑞士-500」(把胜负赔率和让球盘混淆、语义糊)。
     让球盘(亚盘/受让)是另一回事,只在确有让球数据时单独说明,不要拿胜负赔率当让球。
⑤ reason:一句话说明判断依据(尤其 false 的原因)。
输出 JSON: {"is_new":bool,"should_add":bool,"is_correct":bool,"summary_line":str,"reason":str}"""


def judge_news(news_text, source, team, repo_titles, summary_excerpt, published=""):
    """新闻三件套。news_text=正文;repo_titles=已有仓库标题列表;summary_excerpt=该队⑦段现状。"""
    user = (f"【队】{team}\n【来源】{source}　【发布】{published}\n"
            f"【已有仓库标题(判重用)】\n" + "\n".join(f"- {t}" for t in repo_titles[:60]) +
            f"\n\n【该队 summary ⑦关键动态现状(判新用)】\n{summary_excerpt[:3000]}\n\n"
            f"【待判新闻正文】\n{news_text[:6000]}")
    return kimi_json(JUDGE_SYS, user)


# ════════════════════════ 工人 1b:⑦ 去重合并(放宽过滤后,防同主题行累积) ════════════════════════

CONSOLIDATE_SYS = """你是球队档案编辑。给你一支队 summary「⑦关键动态」段的若干条 bullet,做【去重合并】——
放宽收录后,同一主题(尤其【预测首发/阵型】【伤情状态】【赔率】)常有多条重叠/被新消息更新过的旧行,需要整理。
铁规:
1. **不丢任何独立事实**:每个具体的人名/数字/伤情/战绩/赔率/日期都要保留;合并只去【重复与被取代】,不删信息。
2. **同主题多条 → 合并成一条**:如多条"预测首发"→留信息最全、日期最新的那套,其余独有细节并进来;旧的被新口径取代的(如"伤缺"被"已复出"取代)→以最新为准,但可注"(此前伤疑)"。
3. **保留来源标注**「多源核实:…」,合并时把涉及的源并列。
4. 风格、emoji(🏥🟢🟨等)、口吻保持与原文一致;**只输出整理后的 bullet 列表**(每条 - 开头),不要解释、不要标题。
5. 条数应**变少或持平**,绝不变多;若本来就没有重叠,原样返回。"""


def consolidate_seven(bullets_text):
    """把 ⑦ 段的 bullet 文本去重合并(同主题/被取代的行),保留全部独立事实。返回整理后的 bullet 文本。"""
    out = kimi_text(CONSOLIDATE_SYS, f"【⑦关键动态 现有 bullet】\n{bullets_text[:9000]}")
    return out.strip()


# ════════════════════════ 工人 1c:启动前 · 关键词建议(LLM 按情境判断要不要扩) ════════════════════════

SUGGEST_Q_SYS = """你是世界杯数据检索策划。给你一支队的【固定标准检索词】和当下情境,判断为了把这支队这一轮信息收【全】,
还该补哪些检索词(中/英)。原则:补充【固定词没覆盖、但当下确有价值】的角度(如临战的具体伤员名、刚换帅、签证/入境风波、
specific 对位、舆论热点)。只输出 JSON。不要重复已有的固定词。最多补 5 条,没有就空数组。
输出: {"add":[关键词字符串], "why":"一句话说明为何补这些(或为何无需补)"}"""


def suggest_queries(team, base_queries, context=""):
    """启动检索前,LLM 判断是否要在固定模板外补关键词。返回 {add:[...], why:...}。"""
    user = (f"【队】{team}\n【固定标准检索词】\n" + "\n".join(f"- {q}" for q in base_queries) +
            f"\n\n【当下情境(对手/日期/已知热点,可空)】\n{context or '(无特别情境)'}")
    try:
        return kimi_json(SUGGEST_Q_SYS, user)
    except Exception as e:
        return {"add": [], "why": f"(LLM建议失败,沿用固定词:{str(e)[:40]})"}


# ════════════════════════ 工人 7:多源交叉验证(单源→多源的把关,LLM 操作) ════════════════════════

XVERIFY_SYS = """你是事实核查员。给你一个【待核事实项】和它来自【多个来源】的说法,做交叉验证。只输出 JSON。
任务:① 判定 canonical(以多数/最权威/最新为准的确定值);② 找出来源间的分歧(谁说什么、可能的原因,如某源用旧任主帅);
③ confidence:high(多源一致或权威明确)/ medium(多数一致有少数异议)/ low(分歧大或仅单源)。
注意时效:换帅/伤愈/名单变动等,**以最新、最权威为准**,旧源不算反对。
输出: {"canonical": "确定值", "confidence":"high|medium|low", "discrepancy":"分歧说明(无则空串)", "sources_agree": 数字}"""


def cross_verify(fact_label, source_claims):
    """多源交叉验证。fact_label=要核的项(如"巴西主帅");source_claims=[{"source":..,"claim":..}]。
    返回 {canonical, confidence, discrepancy, sources_agree}。"""
    body = "\n".join(f"- 【{c.get('source','?')}】{c.get('claim','')}" for c in source_claims)
    return kimi_json(XVERIFY_SYS, f"【待核事实项】{fact_label}\n【各来源说法】\n{body}")


# ════════════════════════ 工人 8:赛后增量清洁+核实(integrate_match 的伤停/叙事进 summary 前) ════════════════════════

INCREMENT_SYS = """你是世界杯赛后数据审核员。给你某队某场赛后【要写进档案⑦的伤停/停赛条目】(agent 综合多源写的),
进 summary 前做清洁+核实——和"新闻进 summary 要过三判"对称。逐条:
① 清洁:去网页残留/口水/废话,留干净事实;② 张冠李戴核查:确认伤停的人确属【本队】(team),把不属于本队的人剔除;
③ 泄露核查:不得含本场之后比赛的结果/比分(本场赛果已单列、允许);④ 措辞:精炼、客观、保留来源标注。
输出 JSON: {"notes":[清洁核实后的条目字符串(- 开头,可比输入少,剔除张冠李戴的)], "removed":[剔除了什么及原因], "leak":bool}"""


def verify_increment(team, match_label, note_lines):
    """赛后伤停条目进 summary 前的 LLM 清洁+核实(防张冠李戴/泄露/脏)。返回 {notes:[...], removed:[...], leak:bool}。"""
    if not note_lines:
        return {"notes": [], "removed": [], "leak": False}
    body = "\n".join(note_lines)
    try:
        r = kimi_json(INCREMENT_SYS, f"【队】{team}　【本场】{match_label}\n【待写⑦的伤停/停赛条目】\n{body}")
        if isinstance(r.get("notes"), list):
            return r
    except Exception:
        pass
    return {"notes": note_lines, "removed": [], "leak": False, "_fallback": True}   # LLM 失败 → 原样(不阻断)


# ════════════════════════ 工人 2:清洁度自检 + 修改循环(≤3) ════════════════════════

CLEAN_CHECK_SYS = """你是数据质检员。判断给定文本【作为世界杯预测资料】是否干净、是否废话过多。只输出 JSON。
检查:① dirty(脏):有无 导航残留/广告/订阅提示/乱码/网页控件文字/与主题无关的串稿内容?
② verbose(废话多):有无大段与"预测这支球队下一场"无关的注水(历史抒情、套话、重复)?
③ issues:列出具体问题(每条 ≤20 字);④ keep_ratio:估计有用信息占比(0-1)。
判定:dirty 或 verbose 任一为 true,且 keep_ratio<0.85 → need_fix=true。
输出: {"dirty":bool,"verbose":bool,"need_fix":bool,"keep_ratio":number,"issues":[str]}"""

CLEAN_FIX_SYS = """你是数据清理员。把给定文本清理成干净的世界杯预测资料:
- 删:导航/广告/订阅/控件/串稿/与本队无关内容;
- 留:所有对预测有用的事实(伤停/状态/战绩/阵容/战术);
- 情感/抒情:不全删,但高度概括精简成一两句;
- 不杜撰、不添加原文没有的事实。
直接输出清理后的正文,不要解释、不要加标题。"""


def clean_check(text, kind="新闻正文"):
    return kimi_json(CLEAN_CHECK_SYS, f"【类型】{kind}\n【文本】\n{text[:8000]}")


def clean_loop(text, kind="新闻正文", max_rounds=3):
    """脏/废话自检 → 修改 循环(≤max_rounds)。返回 {text, rounds, history}。质检通过即停。"""
    history = []
    cur = text
    for r in range(max_rounds):
        chk = clean_check(cur, kind)
        history.append(chk)
        if not chk.get("need_fix"):
            return {"text": cur, "rounds": r, "passed": True, "history": history}
        cur = kimi_text(CLEAN_FIX_SYS, f"【类型】{kind}\n【问题】{chk.get('issues')}\n【原文】\n{cur[:8000]}")
    # 用满轮数仍未过 → 返回最后一版 + 标记
    return {"text": cur, "rounds": max_rounds, "passed": False, "history": history}


# ════════════════════════ 工人 3:教练可读简介(覆盖 JSON + 多元素) ════════════════════════

COACH_SYS = """你是足球数据编辑。把"主教练结构化数据"与"收集到的相关信息"融合成多层、可读的中文教练简介。
要求:① 覆盖结构化 JSON 里的所有要点(姓名/国籍/执教生涯/带过的队/任职时间等),不遗漏;
② 结合收集信息补充:执教风格/战术理念/与本队的磨合/大赛履历/近期争议或看点;
③ 分点呈现(3-6 点),每点一句话,客观、信息密度高、无套话注水;
④ 不杜撰:信息不足的点宁可不写,绝不编造。
直接输出 markdown 无序列表(- 开头),不要标题、不要前言。"""


def coach_brief(coach_json, extra_info=""):
    user = (f"【结构化数据】\n{json.dumps(coach_json, ensure_ascii=False, indent=1)}\n\n"
            f"【收集到的相关信息(新闻/百科节选,可能为空)】\n{extra_info[:6000] or '(暂无额外信息,仅据结构化数据)'}")
    txt = kimi_text(COACH_SYS, user)
    # 质检一遍(脏/废话),不过则修一次
    chk = clean_check(txt, "教练简介")
    if chk.get("need_fix"):
        txt = kimi_text(CLEAN_FIX_SYS, f"【类型】教练简介\n【问题】{chk.get('issues')}\n【原文】\n{txt}")
    return {"brief": txt.strip(), "qc": chk}


# ════════════════════════ 工人 4:可预测版 long ════════════════════════

PLONG_SYS = """你是足球赛事资料编辑。把一篇"赛事播报 long"改写成【可预测版 long】——它将直接放进球队档案、供模型预测下一场。
原则(关键):**尽量传达原文所有信息,只是按重要性分轻重**:
- 对预测有用的硬信息(比分过程/进球/红黄牌/伤退/战术/数据/球员表现/教练调整)→ 全部保留、清楚陈述;
- 情感/抒情/现场气氛/历史煽情 → 不全删,但高度概括精简(几句话带过,保留"读者能感知到的情绪",删掉冗长铺陈);
- 不杜撰、不添加原文没有的事实;不做预测结论(只整理事实供模型自己判断)。
输出干净 markdown(可用 #### 小标题分段),不要前言、不要"本文改写自"之类元话语。"""


def predictable_long(long_md):
    txt = kimi_text(PLONG_SYS, f"【原 long】\n{long_md[:14000]}")
    chk = clean_check(txt, "可预测版long")
    if chk.get("need_fix"):
        txt = kimi_text(CLEAN_FIX_SYS, f"【类型】可预测版long\n【问题】{chk.get('issues')}\n【原文】\n{txt[:12000]}")
    return {"plong": txt.strip(), "qc": chk}


# ════════════════════════ 工人 5:快照终审官(预测前语义把关) ════════════════════════

AUDIT_SYS = """你是世界杯 benchmark 的快照终审官。预测某场前,通读对阵两队的赛前资料,找出会损害预测质量的问题。只输出 JSON。
重点三类:
① contradiction(自相矛盾):同一队资料里前后**实质**打架(如一处说某人确定伤缺、另一处说他确定首发,且无"伤愈/最新口径"等过渡说明)。
② outdated(过期):明显是旧赛季/旧赛事的信息被当成当前的。
③ leakage(泄露):出现了"本场或本场之后比赛的结果/比分"——这是 benchmark 大忌,必须揪出。

⚠️ **不要误报这两种(它们不是矛盾)**:
 A. **近期战绩比分顺序约定**:「近期状态」里 **客场/中立场比赛一律"对手比分在前、本队在后"**(镜像 ESPN 显示)。所以"客 vs IRL 1-0(L)"= 爱尔兰1-本队0 = 本队0-1负,与别处"0-1负爱尔兰"**完全一致**,不是矛盾。同理"客 vs JPN 3-2(L)"=日本3-本队2=本队2-3负。看到客场"X-Y(L/W)"先按此约定换算再判。
 B. **信息更新分层**:旧行写"伤缺"、新行(带日期/「最新口径」/「伤愈」)写"可出战",属时序更新、不算矛盾;只有两条都声称是当前确定状态且方向相反才算。

对每个问题给 {type, team, quote(原文片段≤40字), why}。没问题则 issues 为空数组。
verdict:"pass"(可预测) 或 "block"。**只有 leakage、或 outdated/contradiction 严重到会误导预测,才 block**;轻微/存疑一律 pass 并列入 issues 供人核。有任何 leakage → 一律 block。
输出: {"verdict":"pass|block","issues":[{"type","team","quote","why"}]}"""


def snapshot_audit(home, away, home_summary, away_summary, match_meta=""):
    user = (f"【对阵】{home}(主) vs {away}(客)　{match_meta}\n\n"
            f"【{home} 赛前资料】\n{home_summary[:14000]}\n\n"
            f"【{away} 赛前资料】\n{away_summary[:14000]}")
    return kimi_json(AUDIT_SYS, user)


# ════════════════════════ 工人 6:赛后复盘官(误差分析,论文素材) ════════════════════════

REVIEW_SYS = """你是预测评测的赛后分析师。给定一场比赛的真实结果与 6 个模型对 7 个市场的预测,做误差复盘。只输出 JSON。
7 市场:胜平负/让球/大小2.5/双方进球/单双/半全场/正确比分。
分析:① per_market:每个市场,哪些模型对、哪些错(列模型名);② model_notes:每个模型一句话点评(强在哪/错在哪类);
③ collective:6 模型共性——是否集体看错某市场?为什么(如低估冷门/高估强队/比分普遍偏小)?
④ paper_point:一句话提炼可写进论文的发现(如"强弱悬殊场各模型胜平负高度一致但比分分歧大")。
输出: {"per_market":{市场:{"right":[模型],"wrong":[模型]}},"model_notes":{模型:str},"collective":str,"paper_point":str}"""


def postmatch_review(home, away, actual, preds):
    """actual={score,ht,...各市场真值};preds={模型:{7市场}}。"""
    user = (f"【比赛】{home} vs {away}　真实结果:{json.dumps(actual, ensure_ascii=False)}\n\n"
            f"【6 模型预测】\n{json.dumps(preds, ensure_ascii=False, indent=1)}")
    return kimi_json(REVIEW_SYS, user)


# ════════════════════════ CLI ════════════════════════

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selftest")
    p = sub.add_parser("judge-news")
    p.add_argument("--news"); p.add_argument("--repo"); p.add_argument("--summary")
    p.add_argument("--team", default="?"); p.add_argument("--source", default="?")
    p = sub.add_parser("clean")
    p.add_argument("--file", required=True); p.add_argument("--kind", default="新闻正文")
    p = sub.add_parser("coach")
    p.add_argument("--json", required=True); p.add_argument("--info", default="")
    p = sub.add_parser("audit")
    p.add_argument("--home", required=True); p.add_argument("--away", required=True)
    p.add_argument("--hs", required=True); p.add_argument("--as", dest="asum", required=True)
    a = ap.parse_args()

    if a.cmd == "selftest":
        print("模型:", WORKER_MODEL)
        print(kimi_json("只输出JSON", '回 {"ok":true,"model":"kimi"}'))
    elif a.cmd == "judge-news":
        news = open(a.news, encoding="utf-8").read() if a.news else ""
        repo = open(a.repo, encoding="utf-8").read().splitlines() if a.repo and os.path.exists(a.repo) else []
        summ = open(a.summary, encoding="utf-8").read() if a.summary and os.path.exists(a.summary) else ""
        print(json.dumps(judge_news(news, a.source, a.team, repo, summ), ensure_ascii=False, indent=1))
    elif a.cmd == "clean":
        print(json.dumps(clean_loop(open(a.file, encoding="utf-8").read(), a.kind), ensure_ascii=False, indent=1))
    elif a.cmd == "coach":
        cj = json.load(open(a.json, encoding="utf-8"))
        info = open(a.info, encoding="utf-8").read() if a.info and os.path.exists(a.info) else ""
        print(json.dumps(coach_brief(cj, info), ensure_ascii=False, indent=1))
    elif a.cmd == "audit":
        print(json.dumps(snapshot_audit(a.home, a.away,
              open(a.hs, encoding="utf-8").read(), open(a.asum, encoding="utf-8").read()),
              ensure_ascii=False, indent=1))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
