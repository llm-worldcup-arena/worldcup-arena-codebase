**English** | [中文](README_zh.md)

# World Cup 2026 · Multi-LLM Prediction Benchmark

> 🌐 **Live demo:** https://llm-worldcup-arena.github.io/

Six **flagship, state-of-the-art (SOTA)** LLMs (Claude / GPT / Gemini / Kimi / GLM / Seed) read **pre-match dossiers** of all 48 teams and predict the 2026 World Cup — match markets, group winners, and tournament outrights — then get scored against real results into a model leaderboard.

## What it does

- **Data**: a pre-match dossier for each of the 48 teams (`wc_runs/team_data/`) — squad, recent form, injuries, World Cup history, market value — collected from multiple sources (Wikipedia / Transfermarkt / Elo) and cross-checked;
- **Predict**: the 6 models read the dossiers and make three kinds of predictions (below);
- **Score**: after the matches, compare against real results → model leaderboard.

> No leakage: only the clean snapshot *before* each prediction point is fed in; actual results are never included.

## Three prediction types

| Type | Input | Predicts |
|---|---|---|
| **Match (7 markets)** | Both teams' full dossiers | 1X2 / handicap / O-U 2.5 / BTTS / odd-even / HT-FT / correct score |
| **Group winner** | The group's 4 dossiers | Winner of each of the 12 groups |
| **Tournament outrights** | 48-team digest (`extract_brief`) | Champion / finalists / semifinalists / winning confederation / total goals |

## Quick start

```bash
# 1. Zero third-party deps — Python 3.8+ (stdlib urllib for API calls)

# 2. Configure your API keys
cp config/secrets.local.json.example config/secrets.local.json
#    DMX_API_KEY is required (Claude/GPT/Gemini/Seed go through DMXAPI).
#    MOONSHOT_API_KEY / ZHIPU_API_KEY are optional — only needed if you want
#    Kimi & GLM to use live web search (their DMXAPI routes have no server-side search).

# 3. Run predictions (6/11 opening matches as an example)
cd wc_eval/predict
python3 predict_match.py  --home MEX --away RSA --snapshot 2026-06-10_1310   # match, 7 markets
python3 predict_group.py  --snapshot 2026-06-10_1310                          # 12 group winners
python3 predict_global.py --snapshot 2026-06-10_1310                          # tournament outrights
python3 merge_batch.py    <batch-timestamp>                                    # merge into one JSON
```

## Layout

| Dir | Contents |
|---|---|
| `wc_eval/` | Code: `bg_collect/` (data collection) + `predict/` (6-model prediction) |
| `wc_skills/` | Three skills: data collection / incremental update / prediction |
| `config/` | LLM config (`llm.json` + key template) |
| `wc_runs/` | Data & outputs: `team_data/` (48 dossiers), `predictions/`, `bg/` (structured data) |
| `docs/` | Design docs: codebase map, data design, plan, collection plan |

## The 6 models

Each is a **thinking/reasoning flagship** from its family, with live web search enabled. We pick the variant that exposes a reasoning trace (e.g. `claude-opus-4-6-thinking` rather than 4-8, which doesn't surface one over DMXAPI):

Claude `claude-opus-4-6-thinking` · GPT `gpt-5.2` · Gemini `gemini-3.1-pro-preview-thinking` · Kimi `kimi-k2.6` · GLM `glm-5.1` · Seed `doubao-seed-2-0-pro-260215`.

Claude / GPT / Gemini / Seed are called via **DMXAPI** (OpenAI-compatible). **Kimi and GLM call their official APIs directly** (Moonshot / Zhipu) — DMXAPI's routes for those two have no server-side web search, so to keep all six "open-book" they use the official endpoints. The exact channel, temperature and token limits per model are recorded in [`wc_eval/predict/models.json`](wc_eval/predict/models.json).

## More docs

- Codebase map (what each py/skill does, collection → prediction) → [`docs/CODEBASE.md`](docs/CODEBASE.md)
- Data / dossier design → [`docs/BG_DESIGN.md`](docs/BG_DESIGN.md)
- Overall plan → [`docs/PLAN.md`](docs/PLAN.md)
- Prediction feeding & token budget → [`wc_eval/predict/FEED_DESIGN.md`](wc_eval/predict/FEED_DESIGN.md)
