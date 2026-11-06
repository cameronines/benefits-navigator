import os, json, anthropic
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
client = anthropic.Anthropic()
COUNTIES = ["San Francisco", "Alameda", "Santa Clara"]

TOOL = {"name": "update_profile", "description": "Save household facts the user stated. Only include fields mentioned.",
        "input_schema": {"type": "object", "properties": {
            "hours": {"type": "number", "description": "hours worked per week"},
            "wage": {"type": "number", "description": "current hourly wage in USD"},
            "kid_ages": {"type": "array", "items": {"type": "integer"}},
            "rent": {"type": "number", "description": "monthly rent USD"},
            "county": {"type": "string", "enum": COUNTIES},
            "raise_amt": {"type": "number", "description": "hourly raise offered or being considered"}}}}

INTAKE_SYS = ("You are a warm, concise benefits-navigator intake assistant for a single parent in the Bay Area. "
              "Whenever the user states household facts, call update_profile. Ask at most one short follow-up for "
              "missing info (hours, wage, kids' ages, rent, county, raise). Never give eligibility numbers yourself; "
              "the app computes them. This is a demo: tell users to use made-up data only.")

def intake_turn(history, profile):
    msgs = list(history)
    for _ in range(3):
        r = client.messages.create(model=MODEL, max_tokens=700, system=INTAKE_SYS, tools=[TOOL], messages=msgs)
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text"), profile
        msgs.append({"role": "assistant", "content": r.content})
        res = []
        for b in r.content:
            if b.type == "tool_use":
                profile.update({k: v for k, v in b.input.items() if v is not None})
                res.append({"type": "tool_result", "tool_use_id": b.id, "content": "saved"})
        msgs.append({"role": "user", "content": res})
    return "Got it.", profile

GROUND = ("Use ONLY the numbers in the provided JSON; never invent figures or rules. Plain language, 8th-grade reading "
          "level, supportive tone. Remind her this is an estimate and to confirm with her county social services office. "
          "Respond entirely in {lang}.")

def ask(task, facts, lang, max_tokens=1200):
    r = client.messages.create(model=MODEL, max_tokens=max_tokens, system=GROUND.format(lang=lang),
                               messages=[{"role": "user", "content": f"{task}\n\nFACTS:\n{json.dumps(facts, default=float)}"}])
    return "".join(b.text for b in r.content if b.type == "text")

def explain(facts, lang): return ask("Explain what this raise does to her monthly take-home resources and why (benefit phase-outs/cliffs). Give 3 short options for what she could do.", facts, lang)
def negotiation_script(facts, lang): return ask("Write a confident raise-negotiation script for her manager: opening line, the specific hourly number to ask for (use suggested_target_usd_per_hr if present, else breakeven_wage if present, else new_wage), citing the market_rate_usd_per_hr range if present, 3 value-based talking points about her work (leave [brackets] for her to fill in), and responses to 2 likely objections. Do NOT disclose her benefits to the employer; frame it around market value and pay equity.", facts, lang, 1600)
def next_steps(facts, lang, tasks):
    return ask("The user chose these next steps: " + "; ".join(tasks) + ". For EACH one give practical, encouraging, step-by-step help: which form or office is involved (use `county`), what to prepare, and a short draft message or script she can adapt when useful (leave [brackets] to fill in). Dollar figures may come ONLY from the facts (e.g. `programs`); otherwise give no amounts. Mark any rule, deadline or form name you are not certain of as 'verify'.", facts, lang, 2200)

def market_rate(job, county):
    """Web-search current Bay Area hourly pay for a role. Returns dict(low, typical, high, sources) or raises."""
    import re
    r = client.messages.create(
        model=MODEL, max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": (
            f"Search the web for current hourly pay for '{job}' roles in {county} County / the Bay Area, California. "
            "Use only figures that appear in the sources you find; do not guess. Reply with ONLY a JSON object: "
            '{"low": <usd/hr>, "typical": <usd/hr>, "high": <usd/hr>, "sources": ["<url>", ...]}. '
            'If you cannot find reliable figures reply {"low": null, "typical": null, "high": null, "sources": []}.')}])
    txt = "".join(b.text for b in r.content if b.type == "text")
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else dict(low=None, typical=None, high=None, sources=[])
