# Benefits Cliff Navigator

A Streamlit demo that helps Bay Area single parents answer: **"Will this raise actually help me?"**

When pay rises, benefits like CalFresh and the EITC shrink. Sometimes they shrink faster than pay grows, so take-home money goes *down*. This is the "benefits cliff". The app finds it, explains it in plain language, and helps the user plan what to do next.

> **Synthetic data only.** This is a hackathon demo. Estimates only, not legal or eligibility advice.

## Run it

Needs Python 3.12 (PolicyEngine-US doesn't install on 3.9).

```
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
source .venv/bin/activate
export ANTHROPIC_API_KEY="sk-ant-..."   # never commit this
streamlit run app.py
```

Restart Streamlit after editing `engine.py` or `llm.py`. Streamlit hot-reloads `app.py` only, not imported modules.

Optional: `CLAUDE_MODEL` overrides the model (default `claude-sonnet-5-5`).

## The demo flow (three steps)

1. **Tell your story**: the user describes their situation in plain language. Claude extracts facts (hours, wage, kids, rent, county, raise offered) through a tool call (`update_profile`). A left-hand profile panel fills in card by card with a flash animation. Steps 2-3 stay locked until all six facts are captured.
   - Fastest path for a demo: the **"Load persona: Maria (Oakland)"** button fills everything.
2. **See the cliff**: shows the programs the household likely qualifies for now (with annual dollar amounts and how each changes after the raise), the take-home before and after the raise, the break-even wage, and a chart of net monthly resources across wages with cliff zones shaded red.
3. **Next steps**:
   - **Plan your raise**: the user enters their job. The app web-searches market pay for similar roles and suggests a target hourly wage. Claude then writes a negotiation script around it.
   - **Get help with other next steps**: the user picks tasks (report income change, claim tax credits, childcare, Medi-Cal, gather documents) and Claude walks them through each.

## Architecture

| File | Role |
|---|---|
| `app.py` | Streamlit UI: profile panel, step gating, tabs, charts. |
| `engine.py` | All the numbers. Wage sweep, cliff detection, per-program amounts. |
| `llm.py` | All Claude calls: intake extraction, explanations, script, next steps, market-rate search. |

## Where the data comes from

### Strong: benefit and tax numbers (PolicyEngine-US)
- `engine._pe_sweep` runs **PolicyEngine-US** (open source, `policyengine-us` 2.104.0) for a California household in tax year 2025. It sweeps annual earnings from $0 to $70/hr at the user's hours and returns net income plus each program: SNAP (CalFresh), EITC, CalEITC, CTC, CA Young Child Tax Credit, TANF (CalWORKs), school meals, Lifeline, and taxes.
- Rule parameters are stored with source links in the model. Spot checks:
  - EITC maximums cite 26 USC §32 and IRS Rev. Proc. 2025-32.
  - The SNAP shelter-deduction cap cites 7 USC §2014 and a USDA FNS allotment table.
  - The CTC amount parameter had no citation in its metadata.
- Source code: https://github.com/PolicyEngine/policyengine-us. Any number can be traced to a parameter file there.
- It's a model, not an official determination. The UI tells users to verify at benefitscal.com or their county office.

### Claude-sourced: market pay target
- `llm.market_rate` uses Claude's web search tool to find current pay for the user's role. It returns low, typical and high rates plus source URLs, which the UI shows.
- It's only as good as the pages found. If nothing reliable is found, the UI shows a warning and no number.
- The suggested target is computed by the app: `max(typical market rate, current wage + raise)`.

### Placeholders and approximations (say so in the demo)
- **Fallback model** (`engine._fallback`): hand-typed 2025 approximations of SNAP/EITC/CTC, marked "VERIFY". It only runs if PolicyEngine errors. The chart caption always shows which engine ran. Check it says `PolicyEngine-US` before demoing.
- **`LIVING_WAGE`** in `app.py`: made-up placeholder values for the dotted line on the chart. Replace with MIT Living Wage figures or remove.
- **Program blurbs** (`ABOUT` in `app.py`): general plain-language descriptions I wrote. Not sourced. Skim before presenting.

## Modeling assumptions and limits

- **County doesn't change the benefit math.** The engine hardcodes California; county only affects the living-wage line and the office Claude names.
- **Fixed household:** one parent aged 32, single filer, and kids always aged 4, 7, 10, 13 (first N, where N is the kid count). The chat's kid ages only set the count.
- Rent is applied to the parent. No childcare costs or health insurance premiums are modeled.
- **Not computed:** Medi-Cal/CHIP/WIC (per-person variables that would break the sweep's array shape). They're listed as "worth checking" with no dollar amounts.
- **Two PolicyEngine outputs to double-check before presenting:** about $24k/year of `household_benefits` at $0 earnings, and a CTC of $4,400 at $0 earnings. Both look different from what current law suggests. `household_benefits` isn't shown in the UI, but CTC is.

## Key design decisions

- **Claude never computes numbers.** The engine produces a `facts` dict. The prompts (`GROUND` in `llm.py`) tell Claude to use only those numbers, and the intake prompt forbids giving eligibility figures. Claude writes words, the model does the math. Caveat: this is enforced by prompt only, with no automated check of Claude's output.
- **Conversation first.** Steps 2-3 are locked until the chat captures all six facts, and each step opens with a "Based on your conversation: …" line, so it's obvious everything flows from what the user said. This was a deliberate change from a free-for-all tab layout.
- **Silent fallback, loud label.** The engine never crashes the demo (falls back on any exception), but the active source is stored in `df.attrs["source"]` and displayed under the chart.
- **Chat updates apply before widgets exist.** Streamlit forbids setting a widget's state after it's created, so chat results are stored in `S.pending` and applied at the top of `app.py` on the next rerun.
- **Positive framing.** Step 2 leads with the support the household already qualifies for ("you've earned this"), then the raise impact, with different messages for a net gain versus a net loss.
- **Spinners on every Claude button** so slow calls don't look frozen. The simulation result is cached on `(hours, kids, rent, county)`; the first run takes about 20 seconds.

## Ideas to strengthen credibility

1. Add a "Where do these numbers come from?" expander in step 2 listing each program and its statute or agency page.
2. Replace the living-wage placeholder and use the kid ages the user gives.
3. Cross-check one persona against benefitscal.com and report how close the estimates are.
