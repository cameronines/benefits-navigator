# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Benefits Cliff Navigator: a Streamlit demo that shows Bay Area single parents whether a raise actually increases net monthly resources once benefit phase-outs ("cliffs") are accounted for. Synthetic data only; outputs are estimates.

## Commands

Python 3.9 virtualenv lives in `.venv` (no git repo, no tests, no linter configured).

```
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # required: llm.py builds the client at import time
streamlit run app.py
```

Optional: `CLAUDE_MODEL` env var overrides the model (default `claude-sonnet-5-5`).

## Architecture

Three modules, flat layout:

- `app.py` — Streamlit UI. Sidebar sliders are bound to `st.session_state` keys (`hours, wage, kids, rent, county, raise_amt`). Four tabs: Intake chat, Cliff chart, Raise planner/script, Action pack.
- `engine.py` — numeric core. `sweep(params)` builds a DataFrame over wages (`wage`, `net_monthly`, plus benefit components); `find_cliffs` detects zones where net drops; `raise_report` produces the `facts` dict for the current-vs-raised wage.
- `llm.py` — all Claude calls. `intake_turn` runs a tool-use loop (`update_profile` tool) to extract household facts from chat; `explain`, `negotiation_script`, `action_pack` go through `ask()`.

### Data flow / non-obvious design

- **Engine fallback**: `engine.sweep` tries PolicyEngine-US (`_pe_sweep`) and on *any* exception silently uses `_fallback`, a stylized 2025 approximation (hardcoded SNAP/EITC/CTC parameters marked "VERIFY"). The active source is stored in `df.attrs["source"]` and shown in the chart caption — preserve this when changing the engine.
- **LLM never computes numbers**: the engine produces a `facts` dict; the `GROUND` system prompt in `llm.py` forces the model to use only those numbers. Keep eligibility/dollar math in `engine.py`, not in prompts. `intake_turn`'s system prompt likewise forbids giving eligibility numbers.
- **Chat → widget updates**: the intake tool results are stashed in `S.pending` and applied at the *top* of `app.py` on the next rerun, before widgets are instantiated (Streamlit forbids setting a widget's state key after creation). `kid_ages` only sets the `kids` count; the engine uses fixed ages `[4, 7, 10, 13][:kids]`.
- `run()` in `app.py` is `st.cache_data`-cached on `(hours, kids, rent, county)`; wage and raise are not part of the sweep (it sweeps wages 0–$70/hr and interpolates with `net_at`). The `county` is only used for the cache key/living-wage line — the engine hardcodes state CA.
- `LIVING_WAGE` in `app.py` is placeholder data (marked to be replaced with MIT figures). New counties must be added to both `llm.COUNTIES` and `LIVING_WAGE`.
- UI output language is passed through to the LLM prompts as `lang`.
