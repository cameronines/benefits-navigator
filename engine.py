"""Wage-sweep engine. PolicyEngine-US first; stylized fallback so the demo never dies.
All fallback parameters are 2025 approximations: VERIFY against official sources."""
import numpy as np, pandas as pd

Y, WEEKS = 2025, 52
COMPONENTS = ["snap", "eitc", "ca_eitc", "ctc", "household_benefits", "household_tax",
              "tanf", "school_meal_net_subsidy", "lifeline", "ca_yctc"]
PROGRAMS = {"snap": "CalFresh (SNAP)", "eitc": "Federal EITC", "ca_eitc": "CalEITC", "ctc": "Child Tax Credit",
            "ca_yctc": "CA Young Child Tax Credit", "tanf": "CalWORKs (TANF)",
            "school_meal_net_subsidy": "Free/reduced school meals", "lifeline": "Lifeline phone/internet discount"}

def _pe_sweep(p, n=80):
    from policyengine_us import Simulation
    kids = {f"k{i}": {"age": {Y: a}} for i, a in enumerate(p["kid_ages"])}
    members = ["parent", *kids]
    max_inc = p["max_wage"] * p["hours"] * WEEKS
    sit = {
        "people": {"parent": {"age": {Y: 32}, "employment_income": {Y: 0}, "rent": {Y: p["rent"] * 12}}, **kids},
        "tax_units": {"tu": {"members": members}},
        "families": {"f": {"members": members}},
        "spm_units": {"s": {"members": members}},
        "marital_units": {"m": {"members": ["parent"]}, **{f"m{i}": {"members": [k]} for i, k in enumerate(kids)}},
        "households": {"h": {"members": members, "state_name": {Y: "CA"}}},
        "axes": [[{"name": "employment_income", "count": n, "min": 0, "max": max_inc, "period": Y}]],
    }
    sim = Simulation(situation=sit)
    inc = np.linspace(0, max_inc, n)
    df = pd.DataFrame({"annual": inc, "net_income": sim.calculate("household_net_income", Y)})
    for c in COMPONENTS:
        try: df[c] = sim.calculate(c, Y)
        except Exception: pass
    return df

def _fallback(p, n=80):
    k, hrs = len(p["kid_ages"]), p["hours"] * WEEKS
    inc = np.linspace(0, p["max_wage"] * hrs, n)
    fpl = 15650 + 5500 * k
    maxallot = {1: 292, 2: 536, 3: 768, 4: 975}.get(min(1 + k, 4), 975)
    snap = []
    for x in inc:
        g = x / 12
        if g > 2.0 * fpl / 12: snap.append(0); continue  # CA BBCE gross limit: a hard cliff
        net = g * 0.8 - 204
        excess = min(max(0, p["rent"] - 0.5 * net), 712)
        snap.append(max(0, maxallot - 0.3 * max(0, net - excess)) * 12)
    snap = np.array(snap)
    kk = min(k, 3)
    rin, mx, rout = [.0765, .34, .40, .45][kk], [632, 4328, 7152, 8046][kk], [.0765, .1598, .2106, .2106][kk]
    start = 10620 if kk == 0 else 19104
    eitc = np.maximum(0, np.minimum(rin * inc, mx) - np.maximum(0, inc - start) * rout)
    ti = np.maximum(0, inc - 23625)
    tax = 0.10 * np.minimum(ti, 17000) + 0.12 * np.clip(ti - 17000, 0, 47850)
    ctc = np.minimum(2200 * k, 0.15 * np.maximum(0, inc - 2500))
    net = inc - 0.0765 * inc - (tax - ctc) + eitc + snap
    return pd.DataFrame({"annual": inc, "net_income": net, "snap": snap, "eitc": eitc, "ctc": ctc})

def sweep(p):
    try: df, src = _pe_sweep(p), "PolicyEngine-US"
    except Exception as e: df, src = _fallback(p), f"Stylized fallback model ({type(e).__name__})"
    df["wage"] = df["annual"] / (p["hours"] * WEEKS)
    df["net_monthly"] = df["net_income"] / 12
    df.attrs["source"] = src
    return df

def net_at(df, wage): return float(np.interp(wage, df.wage, df.net_monthly))

def find_cliffs(df, tol=5.0):
    """Zones where earning more leaves monthly net resources lower."""
    w, n = df.wage.values, df.net_monthly.values
    zones, i = [], 1
    while i < len(df):
        if n[i] - n[i - 1] < -tol:
            s, peak = i, n[i - 1]
            j = i
            while j < len(df) and n[j] < peak: j += 1
            zones.append(dict(start_wage=w[s - 1], end_wage=w[min(j, len(df) - 1)],
                              breakeven_wage=w[j] if j < len(df) else None,
                              peak_net=peak, max_loss=peak - n[s:j].min()))
            i = j
        i += 1
    return zones

def raise_report(df, wage, raise_amt):
    new = wage + raise_amt
    a, b = net_at(df, wage), net_at(df, new)
    be = next((z["breakeven_wage"] for z in find_cliffs(df) if z["start_wage"] <= new <= (z["end_wage"] or 1e9)), None)
    return dict(current_wage=wage, new_wage=new, net_now=round(a), net_after=round(b),
                monthly_change=round(b - a), breakeven_wage=None if be is None else round(be, 2),
                data_source=df.attrs["source"])

def program_report(df, wage, raise_amt):
    """Estimated annual $ per program at current vs raised wage (only programs the engine computed)."""
    out = {}
    for c, label in PROGRAMS.items():
        if c in df:
            a, b = (round(float(np.interp(w, df.wage, df[c]))) for w in (wage, wage + raise_amt))
            if a or b: out[label] = dict(annual_now=a, annual_after_raise=b)
    return out
