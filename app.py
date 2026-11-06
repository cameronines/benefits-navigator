import streamlit as st, plotly.graph_objects as go
import engine, llm

st.set_page_config(page_title="Cliff Navigator", page_icon="◆", layout="wide")
D = dict(hours=40, wage=22.0, kids=2, rent=1900, county="Alameda", raise_amt=4.0)
for k, v in D.items(): st.session_state.setdefault(k, v)
st.session_state.setdefault("chat", [])
st.session_state.setdefault("filled", set())   # profile fields captured (chat, persona, or manual edit)
st.session_state.setdefault("flash", (0, set()))
LIVING_WAGE = {"San Francisco": 57, "Alameda": 52, "Santa Clara": 58}  # PLACEHOLDER: replace w/ MIT figures
FIELDS = [("county", "County", lambda v: v), ("hours", "Hours / week", lambda v: f"{v:g}"),
          ("wage", "Hourly wage", lambda v: f"${v:,.2f}"), ("kids", "Kids", lambda v: f"{v}"),
          ("rent", "Monthly rent", lambda v: f"${v:,.0f}"), ("raise_amt", "Raise offered", lambda v: f"+${v:,.2f}/hr")]

ABOUT = {"CalFresh (SNAP)": "Monthly food money on an EBT card, so groceries stretch further.",
         "Federal EITC": "A tax credit for working families. You get it when you file taxes, and it can be a refund even if you owe nothing.",
         "CalEITC": "California's version of the EITC. It stacks on top of the federal credit.",
         "Child Tax Credit": "A tax credit for each qualifying child.",
         "CA Young Child Tax Credit": "Extra California credit for families with children under 6.",
         "CalWORKs (TANF)": "Cash help for families with children, plus job support.",
         "Free/reduced school meals": "Free or cheaper breakfast and lunch at school for your kids.",
         "Lifeline phone/internet discount": "A monthly discount on your phone or internet bill."}

def A(label, url, cls=""):
    return f'<a class="{cls}" href="{url}" target="_blank" rel="noopener noreferrer">{label} ↗</a>'

PROGRAM_LINKS = {
    "CalFresh (SNAP)": "https://www.cdss.ca.gov/inforesources/calfresh",
    "Federal EITC": "https://www.irs.gov/credits-deductions/individuals/earned-income-tax-credit-eitc",
    "CalEITC": "https://www.ftb.ca.gov/file/personal/credits/california-earned-income-tax-credit.html",
    "Child Tax Credit": "https://www.irs.gov/credits-deductions/individuals/child-tax-credit",
    "CA Young Child Tax Credit": "https://www.ftb.ca.gov/file/personal/credits/young-child-tax-credit.html",
    "CalWORKs (TANF)": "https://www.cdss.ca.gov/calworks",
    "Free/reduced school meals": "https://www.cde.ca.gov/ls/nu/sn/",
    "Lifeline phone/internet discount": "https://www.fcc.gov/lifeline-consumers"}
COUNTY_OFFICE = {"San Francisco": ("SF Human Services Agency", "https://www.sfhsa.org"),
                 "Alameda": ("Alameda County Social Services", "https://socialservices.alamedacountyca.gov/index.page"),
                 "Santa Clara": ("Santa Clara County", "https://www.sccgov.org")}

def mark(key): st.session_state.filled.add(key)

# apply chat-extracted updates before widgets are created
_upd = st.session_state.pop("pending", {})
_changed = set()
for k, v in _upd.items():
    if k == "kid_ages": st.session_state["kids"] = min(len(v), 4); k = "kids"
    elif k in ("raise_amt", "wage"): st.session_state[k] = float(v)
    else: st.session_state[k] = v
    _changed.add(k)
if _changed:
    st.session_state.filled |= _changed
    st.session_state.flash = (st.session_state.flash[0] + 1, _changed)
    st.toast("Got it — updated " + ", ".join(sorted(_changed)))


S = st.session_state
n_flash, flashed = S.flash
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Source+Serif+4:wght@400;600&display=swap');
html, body, .stApp, [data-testid="stSidebar"] {{ font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif; }}
h1, h2, h3, h4, [data-testid="stMetricValue"] {{ font-family: 'Source Serif 4', Georgia, serif !important; font-weight: 600; letter-spacing: -0.01em; color: #141413; }}
h1 {{ font-size: 2.4rem; }}
footer, #MainMenu {{ visibility: hidden; }}
.stApp [data-testid="stHeader"] {{ background: transparent; }}
.stButton > button {{ border-radius: 8px; border: 1px solid #141413; background: #141413; color: #faf9f5; font-weight: 500; }}
.stButton > button:hover {{ background: #3d3d3a; border-color: #3d3d3a; color: #faf9f5; }}
.stButton > button:disabled {{ background: #e8e6dc; border-color: #d1cfc5; color: #87867f; }}
[data-testid="stSidebar"] .stButton > button {{ background: transparent; color: #141413; }}
[data-testid="stSidebar"] .stButton > button:hover {{ background: #e8e6dc; color: #141413; }}
.pcard {{ border: 1px solid #d1cfc5; border-left: 3px solid #d1cfc5; border-radius: 8px; padding: 8px 12px; margin: 5px 0;
          display: flex; justify-content: space-between; background: #faf9f5; font-size: 0.92rem; }}
.pcard.empty {{ color: #87867f; background: transparent; border-style: dashed; border-left-style: dashed; }}
.pcard.done {{ border-left-color: #788c5d; }}
@keyframes flash{n_flash} {{ 0% {{ background: #f3d3c4; transform: scale(1.04); box-shadow: 0 0 12px rgba(217,119,87,.45); }}
                            100% {{ background: #faf9f5; transform: scale(1); box-shadow: none; }} }}
.pcard.new {{ animation: flash{n_flash} 1.8s ease-out; }}
[data-testid="stMetric"] {{ background: #f0eee6; border-radius: 10px; padding: 12px 16px; }}
[data-testid="stAlert"] {{ border-radius: 10px; }}
[data-testid="stHeaderActionElements"], .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a, .stMarkdown h4 a {{ display: none !important; }}
.simload {{ background: #f0eee6; border-radius: 16px; padding: 36px 24px 30px; text-align: center; margin: 0.4rem 0 1.4rem; }}
.simload svg {{ width: min(420px, 90%); height: auto; }}
.simload .t {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 1.6rem; font-weight: 600; margin-top: 8px; }}
.simload .s {{ color: #5e5d59; font-size: 0.95rem; margin-top: 4px; }}
.sim-line {{ stroke-dasharray: 1; stroke-dashoffset: 1; animation: simdraw 2.6s ease-in-out infinite; }}
@keyframes simdraw {{ 0% {{ stroke-dashoffset: 1; }} 70% {{ stroke-dashoffset: 0; }} 100% {{ stroke-dashoffset: 0; opacity: 0; }} }}
.sim-dot {{ transform-box: fill-box; transform-origin: center; animation: simpulse 1.6s ease-in-out infinite; }}
.sim-dot.d2 {{ animation-delay: .35s; }} .sim-dot.d3 {{ animation-delay: .7s; }} .sim-dot.d4 {{ animation-delay: 1.05s; }}
@keyframes simpulse {{ 0%, 100% {{ transform: scale(1); opacity: .9; }} 50% {{ transform: scale(1.18); opacity: 1; }} }}
.src {{ font-size: 0.8rem; font-weight: 500; color: #141413 !important; text-decoration: none !important; border-bottom: 1px solid #d97757; white-space: nowrap; }}
.src:hover {{ color: #c4553a !important; }}
.pcardx > .src {{ display: inline-block; margin-top: 10px; }}
.srcgrid ul {{ padding-left: 1.1rem; margin: 8px 0 0; }} .srcgrid li {{ font-size: 0.88rem; margin: 5px 0; color: #3d3d3a; }}
.srcgrid li a {{ color: #141413; text-decoration: underline; text-decoration-color: #d97757; text-underline-offset: 3px; }}
.srcgrid li a:hover {{ color: #c4553a; }}
.foot {{ margin-top: 40px; padding-top: 14px; border-top: 1px solid #d1cfc5; font-size: 0.8rem; color: #87867f; }}
.foot a {{ color: #5e5d59; }}
.block-container {{ padding-top: 2.2rem; max-width: 1200px; }}
.eyebrow {{ font-size: 0.72rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: #87867f; margin: 6px 0 4px; }}
.banner {{ position: relative; overflow: hidden; background: #f0eee6; border-radius: 16px; margin: 0 0 1.6rem; min-height: 220px; }}
.banner svg {{ position: absolute; right: 0; top: 0; height: 100%; width: 70%; }}
.banner-text {{ position: relative; padding: 34px 40px; max-width: 58%; }}
.banner-text h1 {{ font-size: 3rem; line-height: 1.05; margin: 6px 0 10px; padding: 0; }}
.banner-text p {{ font-size: 1.05rem; color: #3d3d3a; margin: 0 0 12px; }}
.banner-text .fine {{ font-size: 0.8rem; color: #87867f; }}
.cardgrid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; margin: 10px 0 8px; }}
.pcardx {{ background: #f0eee6; border-radius: 12px; padding: 16px 18px; }}
.pcardx .nm {{ font-family: 'Source Serif 4', Georgia, serif; font-weight: 600; font-size: 1.05rem; }}
.pcardx .amt {{ font-family: 'Source Serif 4', Georgia, serif; font-size: 1.7rem; font-weight: 600; margin: 4px 0 2px; }}
.pcardx .dl {{ font-size: 0.82rem; font-weight: 500; }} .pcardx .up {{ color: #788c5d; }} .pcardx .down {{ color: #c4553a; }} .pcardx .flat {{ color: #87867f; }}
.pcardx .ab {{ font-size: 0.86rem; color: #5e5d59; margin-top: 8px; }}
@media (max-width: 800px) {{ .banner-text {{ max-width: 100%; }} .banner svg {{ opacity: .35; width: 100%; }} }}
</style>""", unsafe_allow_html=True)

BANNER = """<div class="banner">
<svg viewBox="0 0 1000 240" preserveAspectRatio="xMaxYMid slice" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <circle cx="835" cy="70" r="92" fill="#d97757"/>
  <circle cx="930" cy="190" r="72" fill="#6a9bcc"/>
  <path d="M640 240 A82 82 0 0 1 804 240 Z" fill="#788c5d"/>
  <circle cx="745" cy="62" r="24" fill="#c46686"/>
  <path d="M470 205 C520 200 560 170 600 135 L650 128 L668 196 C700 202 740 150 790 112 C830 82 880 96 940 52"
        fill="none" stroke="#141413" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="470" cy="205" r="5" fill="#141413"/><circle cx="940" cy="52" r="5" fill="#141413"/>
</svg>
<div class="banner-text">
  <div class="eyebrow">Bay Area &nbsp;·&nbsp; Synthetic data demo</div>
  <h1>Benefits Navigator</h1>
  <p>See what support your household qualifies for, and whether a raise would really leave you better off.</p>
  <div class="fine">Estimates only, not legal advice.</div>
</div></div>"""
st.markdown(BANNER, unsafe_allow_html=True)

def eyebrow(n, text): st.markdown(f'<div class="eyebrow">0{n} / 03 &nbsp;·&nbsp; {text}</div>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Your profile")
    st.caption("Filled in from your conversation →")
    for key, label, fmt in FIELDS:
        done = key in S.filled
        cls = "done" if done else "empty"
        if done and key in flashed: cls += " new"
        val = fmt(S[key]) if done else "waiting…"
        st.markdown(f'<div class="pcard {cls}"><span>{label}</span><b>{val}</b></div>', unsafe_allow_html=True)
    st.progress(len(S.filled & {f[0] for f in FIELDS}) / len(FIELDS), text=f"{len(S.filled & {f[0] for f in FIELDS})}/{len(FIELDS)} details captured")
    if st.button("Load persona: Maria (Oakland)"):
        for k, v in D.items(): st.session_state[k] = v
        S.filled = {f[0] for f in FIELDS}; S.flash = (n_flash + 1, set(S.filled))
        st.rerun()
    lang = st.selectbox("Language", ["English", "Spanish", "Chinese (Simplified)", "Tagalog", "Vietnamese"])
    with st.expander("Adjust manually"):
        st.selectbox("County", llm.COUNTIES, key="county", on_change=mark, args=("county",))
        st.slider("Hours / week", 5, 50, key="hours", on_change=mark, args=("hours",))
        st.slider("Hourly wage ($)", 12.0, 60.0, step=0.5, key="wage", on_change=mark, args=("wage",))
        st.slider("Kids", 0, 4, key="kids", on_change=mark, args=("kids",))
        st.slider("Monthly rent ($)", 500, 5000, step=50, key="rent", on_change=mark, args=("rent",))
        st.slider("Raise offered ($/hr)", 0.0, 15.0, step=0.5, key="raise_amt", on_change=mark, args=("raise_amt",))

ready = {f[0] for f in FIELDS} <= S.filled

@st.cache_data(show_spinner=False)
def run(hours, kids, rent, county):
    p = dict(hours=hours, kid_ages=[4, 7, 10, 13][:kids], rent=rent, county=county, max_wage=70)
    df = engine.sweep(p); return df, engine.find_cliffs(df)

LOADER = """<div class="simload">
<svg viewBox="0 0 420 150" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <circle class="sim-dot" cx="320" cy="48" r="38" fill="#d97757"/>
  <circle class="sim-dot d2" cx="378" cy="108" r="28" fill="#6a9bcc"/>
  <path class="sim-dot d3" d="M190 150 A38 38 0 0 1 266 150 Z" fill="#788c5d"/>
  <circle class="sim-dot d4" cx="240" cy="40" r="12" fill="#c46686"/>
  <path class="sim-line" pathLength="1" d="M20 120 C70 116 100 96 130 74 L170 70 L184 118 C210 122 240 92 280 66 C310 46 345 56 400 22"
        fill="none" stroke="#141413" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
<div class="t">Running your benefits simulation</div>
<div class="s">Working out taxes, credits and benefits at every wage. This can take about 20 seconds the first time.</div>
</div>"""

def run_with_loader(*args):
    """Show the large themed loader only when the inputs changed (i.e. the simulation likely recomputes)."""
    if S.get("_simkey") == args: return run(*args)
    ph = st.empty(); ph.markdown(LOADER, unsafe_allow_html=True)
    try: return run(*args)
    finally: ph.empty(); S["_simkey"] = args

def gate(step):
    """Return True if the conversation is complete; otherwise show a lock message."""
    if not ready:
        missing = [lab for k, lab, _ in FIELDS if k not in S.filled]
        st.info(f"Step 1 first: finish the conversation so this step can use your details. Still needed: {', '.join(missing)}")
    else:
        st.caption(f"Based on your conversation: {S.hours:g} hrs/wk · ${S.wage:.2f}/hr · {S.kids} kids · ${S.rent:,.0f} rent · {S.county} · +${S.raise_amt:g}/hr raise")
    return ready

if ready:
    df, cliffs = run_with_loader(S.hours, S.kids, S.rent, S.county)
    facts = engine.raise_report(df, S.wage, S.raise_amt)
    facts.update(county=S.county, kids=S.kids, hours=S.hours, rent=S.rent, cliff_zones=cliffs, wages_are_hourly_usd=True,
                 programs=engine.program_report(df, S.wage, S.raise_amt))

tab1, tab2, tab3 = st.tabs(["1. Tell us about you", "2. Understand your income & benefits", "3. Next steps"])

with tab1:
    eyebrow(1, "Tell us about you")
    st.markdown("**Start here.** Describe your situation in your own words. Everything in steps 2–3 is built from what you say.")
    for m in S.chat:
        st.chat_message(m["role"]).write(m["content"])
    if msg := st.chat_input("e.g. I work 40 hrs at $22, two kids ages 4 and 7, rent $2,800 in Oakland, offered $4 more"):
        S.chat.append({"role": "user", "content": msg})
        with st.spinner("Reading your message and updating your profile…"):
            reply, upd = llm.intake_turn(S.chat, {})
        S.chat.append({"role": "assistant", "content": reply})
        S.pending = upd; st.rerun()
    if ready: st.success("Profile complete. Open step 2 to see what this raise really does →")

with tab2:
    eyebrow(2, "Understand your income &amp; benefits")
    if gate(2):
        progs = facts["programs"]
        total = sum(v["annual_now"] for v in progs.values())
        st.subheader("Support you likely qualify for right now")
        if progs:
            st.success(f"Based on what you told us, your household may get about **${total:,}/year** (~${total // 12:,}/month) from programs like these. You've earned this support by working. Using it is what it's for.")
            cells = []
            for name, v in progs.items():
                x, y = v["annual_now"], v["annual_after_raise"]
                d = y - x
                dl = ('<span class="dl flat">No change with raise</span>' if d == 0 else
                      f'<span class="dl {"up" if d > 0 else "down"}">{"+" if d > 0 else "−"}&#36;{abs(d):,} / yr after raise</span>')
                cells.append(f'<div class="pcardx"><div class="nm">{name}</div><div class="amt">&#36;{x:,}<span style="font-size:.85rem;font-weight:400;color:#87867f"> / yr</span></div>{dl}<div class="ab">{ABOUT.get(name, "")}</div>{A("Official page", PROGRAM_LINKS[name], "src") if name in PROGRAM_LINKS else ""}</div>')
            st.markdown('<div class="cardgrid">' + "".join(cells) + '</div>', unsafe_allow_html=True)
            st.caption("Estimates from the tax-benefit model. Also worth checking (not calculated here): Medi-Cal, WIC, childcare help, housing help.")
        else:
            st.info("At this income the model doesn't find these programs. Medi-Cal, childcare help and other programs may still apply. See step 3.")
        if facts["monthly_change"] > 0:
            st.info("Good news: even after any benefit changes, this raise leaves you better off each month. Benefits shrink gradually as pay rises by design, so earning more still comes out ahead here.")
        elif facts["monthly_change"] < 0:
            st.warning("This raise would leave you with less each month because benefits drop faster than pay rises. You're not imagining it. Step 3 helps you plan a number that clears this cliff.")
        st.subheader("What the raise does")
        c1, c2 = st.columns(2)
        c1.metric("Take-home now (monthly)", f"${facts['net_now']:,}")
        c2.metric(f"After +${S.raise_amt:g}/hr", f"${facts['net_after']:,}", f"{facts['monthly_change']:+,}")
        fig = go.Figure(go.Scatter(x=df.wage, y=df.net_monthly, mode="lines", name="Net monthly resources", line=dict(width=2.5, color="#141413")))
        for z in cliffs: fig.add_vrect(x0=z["start_wage"], x1=z["end_wage"], fillcolor="#d97757", opacity=0.2, line_width=0)
        for x, lab, col in [(S.wage, "Now", "#6a9bcc"), (S.wage + S.raise_amt, "With raise", "#d97757")]:
            fig.add_trace(go.Scatter(x=[x], y=[engine.net_at(df, x)], mode="markers+text", text=[lab], textposition="top center",
                                     marker=dict(size=12, color=col, line=dict(width=2, color="#faf9f5")), showlegend=False))
        fig.add_vline(x=min(LIVING_WAGE[S.county], 70), line_dash="dot", line_color="#87867f")
        fig.update_layout(xaxis_title="Hourly wage ($)", yaxis_title="Monthly net resources ($)", height=480, margin=dict(t=20), paper_bgcolor="#faf9f5", plot_bgcolor="#faf9f5",
                          font=dict(family="Inter, sans-serif", color="#141413"))
        fig.update_xaxes(gridcolor="#e8e6dc", zeroline=False); fig.update_yaxes(gridcolor="#e8e6dc", zeroline=False)
        chart, legend = st.columns([3, 1.4])
        chart.plotly_chart(fig, use_container_width=True)
        with legend:
            st.markdown("#### How to read this")
            st.markdown("**Dark line**: money your household has each month (pay + benefits + credits − taxes) at each hourly wage.")
            st.markdown(f"**● Now (${S.wage:g}/hr)**: ${facts['net_now']:,}/mo  \n**● With raise (${S.wage + S.raise_amt:g}/hr)**: ${facts['net_after']:,}/mo")
            if cliffs:
                st.markdown("**Shaded zone = a cliff.** Earning more *here* leaves you with *less* each month, because benefits drop faster than pay rises.")
                st.markdown(A("About benefits cliffs", "https://www.atlantafed.org/research-and-data/publications/partners-update/2022/08/30/cliff-dashboard-evaluations-insights-from-three-state-pilots", "src"), unsafe_allow_html=True)
                for z in cliffs:
                    now_in = z["start_wage"] <= S.wage <= z["end_wage"]
                    after_in = z["start_wage"] <= S.wage + S.raise_amt <= z["end_wage"]
                    st.markdown(f"- From **${z['start_wage']:.2f}** to **${z['end_wage']:.2f}/hr**, you could lose up to **${z['max_loss']:,.0f}/mo**. You're back ahead at **${z['breakeven_wage']:.2f}/hr**." if z["breakeven_wage"] else f"- From **${z['start_wage']:.2f}/hr** up, you could lose up to **${z['max_loss']:,.0f}/mo**.")
                    if now_in and not after_in: st.success("You're **in** this zone now. This raise takes you **past** it.")
                    elif now_in and after_in: st.warning("You're **in** this zone, and this raise leaves you **still inside** it. Aim higher; see step 3.")
                    elif after_in: st.warning("This raise would move you **into** the zone, so you'd take home less. Aim past the zone; see step 3.")
                    elif S.wage > z["end_wage"]: st.info("You're already **past** this zone.")
                    else: st.info("This zone is **above** your raise; a later raise could cross it.")
            else:
                st.success("**No shaded zone for your situation.** Every raise leaves you ahead.")
            st.markdown("**Dotted line**: living wage (placeholder figure; compare the " + A("MIT Living Wage Calculator", "https://livingwage.mit.edu/", "src") + ")", unsafe_allow_html=True)
        st.caption(f"Engine: {df.attrs['source']}. Verify thresholds with official sources (benefitscal.com, county office).")
        st.markdown('<div class="eyebrow" style="margin-top:28px">Sources &amp; methodology</div>', unsafe_allow_html=True)
        st.markdown('''<div class="cardgrid srcgrid">
<div class="pcardx"><div class="nm">How the numbers are calculated</div><ul>
<li>''' + A('PolicyEngine-US', 'https://github.com/PolicyEngine/policyengine-us') + ''', open-source tax and benefit model (2025 rules, California)</li>
<li>''' + A('26 U.S.C. §32 (EITC)', 'https://www.law.cornell.edu/uscode/text/26/32') + '''</li>
<li>''' + A('7 U.S.C. §2014 (SNAP)', 'https://www.law.cornell.edu/uscode/text/7/2014') + '''</li>
<li>''' + A('IRS Rev. Proc. 2025-32', 'https://www.irs.gov/pub/irs-drop/rp-25-32.pdf') + ''', 2025 inflation adjustments</li></ul></div>
<div class="pcardx"><div class="nm">Why cliffs happen</div><div class="ab">Many benefits phase out as income rises. When they shrink faster than pay grows, take-home money can fall.</div><ul>
<li>''' + A('Atlanta Fed CLIFF research', 'https://www.atlantafed.org/research-and-data/publications/partners-update/2022/08/30/cliff-dashboard-evaluations-insights-from-three-state-pilots') + '''</li></ul></div>
<div class="pcardx"><div class="nm">Check your own situation</div><ul>
<li>''' + A('BenefitsCal', 'https://benefitscal.com') + ''', California's official application portal</li>
<li>''' + A('GetCalFresh', 'https://www.getcalfresh.org/en/') + '''</li>
<li>Your county office (see step 3)</li></ul></div>
<div class="pcardx"><div class="nm">Known limits</div><div class="ab">These are estimates from a model, not eligibility decisions. County does not change the benefit math, kids are assumed to be ages 4, 7, 10 and 13, and the living-wage line is a placeholder.</div></div>
</div>''', unsafe_allow_html=True)

with tab3:
    eyebrow(3, "Next steps")
    if gate(3):
        st.subheader("Plan your raise")
        job = st.text_input("Your job (e.g. barista at Starbucks)", key="job")
        if st.button("Find market rate for my role") and job:
            with st.spinner("Searching current pay for similar roles…"):
                try: S.market = dict(job=job, county=S.county, **llm.market_rate(job, S.county))
                except Exception as e: S.market = dict(job=job, county=S.county, error=f"{type(e).__name__}: {e}")
        mk = S.get("market")
        if mk and mk.get("typical"):
            target = max(mk["typical"], S.wage + S.raise_amt)
            st.metric("Suggested target ($/hr)", f"${target:,.2f}",
                      f"market range ${mk['low']:g}–${mk['high']:g} (typical ${mk['typical']:g}) for {mk['job']}")
            from urllib.parse import urlparse
            links = [A(urlparse(u).netloc.removeprefix("www."), u, "src") for u in mk.get("sources", [])[:3] if str(u).startswith(("http://", "https://"))]
            st.markdown('<div class="ab" style="font-size:.86rem;color:#5e5d59">Estimate from web search' + (": " + " &nbsp;·&nbsp; ".join(links) if links else "") + ". Verify before you negotiate.</div>", unsafe_allow_html=True)
            facts.update(market_rate_usd_per_hr=dict(low=mk["low"], typical=mk["typical"], high=mk["high"]), suggested_target_usd_per_hr=target)
        elif mk:
            st.warning(mk.get("error") or "Couldn't find reliable market figures for that role; try a more common job title.")
        if st.button("Generate my negotiation script"):
            with st.spinner("Writing your negotiation script…"):
                st.markdown(llm.negotiation_script(facts, lang))
        st.divider()
        office = COUNTY_OFFICE[S.county]
        st.markdown('<div class="eyebrow">Official places to act</div>', unsafe_allow_html=True)
        st.markdown(" &nbsp;·&nbsp; ".join([A(office[0], office[1], "src"), A("Apply or check eligibility: BenefitsCal", "https://benefitscal.com", "src"),
            A("Report CalFresh changes", "https://www.cdss.ca.gov/inforesources/calfresh/report-changes", "src"),
            A("Medi-Cal", "https://www.dhcs.ca.gov/services/medi-cal", "src"),
            A("WIC", "https://www.cdph.ca.gov/Programs/CFH/DWICSN/Pages/Program-Landing1.aspx", "src")]), unsafe_allow_html=True)
        st.subheader("Get help with other next steps")
        st.markdown("Pick any and we will walk you through them.")
        NEXT = {"report": "Report my income change to the county (CalFresh / Medi-Cal)",
                "taxes": "Claim my tax credits (EITC, CalEITC, Child Tax Credit)",
                "childcare": "Find childcare help",
                "health": "Check Medi-Cal / health coverage",
                "docs": "Gather the documents I need"}
        picks = st.multiselect("Next steps", list(NEXT), format_func=NEXT.get)
        if st.button("Help me with these", disabled=not picks):
            with st.spinner("Preparing your next steps…"):
                st.markdown(llm.next_steps(facts, lang, [NEXT[k] for k in picks]))

st.markdown("<div class='foot'>Benefit calculations by " + A("PolicyEngine-US", "https://github.com/PolicyEngine/policyengine-us") + ". Explanations and scripts written by Claude from those results. "
            "Synthetic data only. Estimates, not legal or eligibility advice. Confirm with " + A("BenefitsCal", "https://benefitscal.com") + " or your county office.</div>", unsafe_allow_html=True)
