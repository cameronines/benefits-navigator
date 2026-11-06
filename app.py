import streamlit as st, plotly.graph_objects as go
import engine, llm

st.set_page_config(page_title="Cliff Navigator", page_icon="📈", layout="wide")
D = dict(hours=30, wage=22.0, kids=2, rent=1900, county="Alameda", raise_amt=4.0)
for k, v in D.items(): st.session_state.setdefault(k, v)
st.session_state.setdefault("chat", [])
st.session_state.setdefault("filled", set())   # profile fields captured (chat, persona, or manual edit)
st.session_state.setdefault("flash", (0, set()))
LIVING_WAGE = {"San Francisco": 57, "Alameda": 52, "Santa Clara": 58}  # PLACEHOLDER: replace w/ MIT figures
FIELDS = [("county", "📍 County", lambda v: v), ("hours", "⏱️ Hours / week", lambda v: f"{v:g}"),
          ("wage", "💵 Hourly wage", lambda v: f"${v:,.2f}"), ("kids", "👧 Kids", lambda v: f"{v}"),
          ("rent", "🏠 Monthly rent", lambda v: f"${v:,.0f}"), ("raise_amt", "📈 Raise offered", lambda v: f"+${v:,.2f}/hr")]

ABOUT = {"CalFresh (SNAP)": "Monthly food money on an EBT card, so groceries stretch further.",
         "Federal EITC": "A tax credit for working families. You get it when you file taxes, and it can be a refund even if you owe nothing.",
         "CalEITC": "California's version of the EITC. It stacks on top of the federal credit.",
         "Child Tax Credit": "A tax credit for each qualifying child.",
         "CA Young Child Tax Credit": "Extra California credit for families with children under 6.",
         "CalWORKs (TANF)": "Cash help for families with children, plus job support.",
         "Free/reduced school meals": "Free or cheaper breakfast and lunch at school for your kids.",
         "Lifeline phone/internet discount": "A monthly discount on your phone or internet bill."}

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
    st.toast("Got it — updated " + ", ".join(sorted(_changed)), icon="✅")

st.title("📈 Benefits Navigator")
st.caption("What benefits are you eligible for? Will this raise actually help? Bay Area · synthetic data only · estimates, not legal advice")

S = st.session_state
n_flash, flashed = S.flash
st.markdown(f"""<style>
.pcard{{border:1px solid rgba(128,128,128,.35);border-radius:10px;padding:8px 12px;margin:5px 0;display:flex;justify-content:space-between}}
.pcard.empty{{opacity:.55;border-style:dashed}} .pcard.done{{border-color:#2e9e5b}}
@keyframes flash{n_flash}{{0%{{background:#ffd54f;transform:scale(1.06);box-shadow:0 0 14px #ffb300}}100%{{background:transparent;transform:scale(1);box-shadow:none}}}}
.pcard.new{{animation:flash{n_flash} 1.8s ease-out}}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("🧾 Your profile")
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
    with st.expander("✏️ Adjust manually"):
        st.selectbox("County", llm.COUNTIES, key="county", on_change=mark, args=("county",))
        st.slider("Hours / week", 5, 50, key="hours", on_change=mark, args=("hours",))
        st.slider("Hourly wage ($)", 12.0, 60.0, step=0.5, key="wage", on_change=mark, args=("wage",))
        st.slider("Kids", 0, 4, key="kids", on_change=mark, args=("kids",))
        st.slider("Monthly rent ($)", 500, 5000, step=50, key="rent", on_change=mark, args=("rent",))
        st.slider("Raise offered ($/hr)", 0.0, 15.0, step=0.5, key="raise_amt", on_change=mark, args=("raise_amt",))

ready = {f[0] for f in FIELDS} <= S.filled

@st.cache_data(show_spinner="Running tax-benefit simulation…")
def run(hours, kids, rent, county):
    p = dict(hours=hours, kid_ages=[4, 7, 10, 13][:kids], rent=rent, county=county, max_wage=70)
    df = engine.sweep(p); return df, engine.find_cliffs(df)

def gate(step):
    """Return True if the conversation is complete; otherwise show a lock message."""
    if not ready:
        missing = [lab for k, lab, _ in FIELDS if k not in S.filled]
        st.info(f"🔒 Step 1 first: finish the conversation so this step can use your details. Still needed: {', '.join(missing)}")
    else:
        st.caption(f"✅ Based on your conversation: {S.hours:g} hrs/wk · ${S.wage:.2f}/hr · {S.kids} kids · ${S.rent:,.0f} rent · {S.county} · +${S.raise_amt:g}/hr raise")
    return ready

if ready:
    df, cliffs = run(S.hours, S.kids, S.rent, S.county)
    facts = engine.raise_report(df, S.wage, S.raise_amt)
    facts.update(county=S.county, kids=S.kids, hours=S.hours, rent=S.rent, cliff_zones=cliffs, wages_are_hourly_usd=True,
                 programs=engine.program_report(df, S.wage, S.raise_amt))

tab1, tab2, tab3 = st.tabs(["1️⃣ Tell your story", "2️⃣ Understand your income & benefits", "3️⃣ Next steps"])

with tab1:
    st.markdown("**Start here.** Describe your situation in your own words. Everything in steps 2–3 is built from what you say.")
    for m in S.chat:
        st.chat_message(m["role"]).write(m["content"])
    if msg := st.chat_input("e.g. I work 30 hrs at $22, two kids ages 4 and 7, rent $2,800 in Oakland, offered $4 more"):
        S.chat.append({"role": "user", "content": msg})
        with st.spinner("Reading your message and updating your profile…"):
            reply, upd = llm.intake_turn(S.chat, {})
        S.chat.append({"role": "assistant", "content": reply})
        S.pending = upd; st.rerun()
    if ready: st.success("Profile complete. Open step 2 to see what this raise really does →")

with tab2:
    if gate(2):
        progs = facts["programs"]
        total = sum(v["annual_now"] for v in progs.values())
        st.subheader("🎉 Support you likely qualify for right now")
        if progs:
            st.success(f"Based on what you told us, your household may get about **${total:,}/year** (~${total // 12:,}/month) from programs like these. You've earned this support by working. Using it is what it's for.")
            for name, v in progs.items():
                a, b = v["annual_now"], v["annual_after_raise"]
                c_a, c_b = st.columns([1, 3])
                c_a.metric(name, f"${a:,}/yr", f"{b - a:+,} after raise" if b != a else "no change with raise", delta_color="off" if b == a else "normal")
                c_b.markdown(f"**{name}** · {ABOUT.get(name, '')}")
            st.caption("Estimates from the tax-benefit model. Also worth checking (not calculated here): Medi-Cal, WIC, childcare help, housing help.")
        else:
            st.info("At this income the model doesn't find these programs. Medi-Cal, childcare help and other programs may still apply. See step 3.")
        if facts["monthly_change"] > 0:
            st.info("💪 Good news: even after any benefit changes, this raise leaves you better off each month. Benefits shrink gradually as pay rises by design, so earning more still comes out ahead here.")
        elif facts["monthly_change"] < 0:
            st.warning("⚠️ This raise would leave you with less each month because benefits drop faster than pay rises. You're not imagining it. Step 3 helps you plan a number that clears this cliff.")
        st.subheader("📉 What the raise does")
        c1, c2 = st.columns(2)
        c1.metric("Take-home now (monthly)", f"${facts['net_now']:,}")
        c2.metric(f"After +${S.raise_amt:g}/hr", f"${facts['net_after']:,}", f"{facts['monthly_change']:+,}")
        fig = go.Figure(go.Scatter(x=df.wage, y=df.net_monthly, mode="lines", name="Net monthly resources", line=dict(width=3)))
        for z in cliffs: fig.add_vrect(x0=z["start_wage"], x1=z["end_wage"], fillcolor="red", opacity=0.15, line_width=0)
        for x, lab in [(S.wage, "Now"), (S.wage + S.raise_amt, "With raise")]:
            fig.add_trace(go.Scatter(x=[x], y=[engine.net_at(df, x)], mode="markers+text", text=[lab], textposition="top center",
                                     marker=dict(size=12), showlegend=False))
        fig.add_vline(x=min(LIVING_WAGE[S.county], 70), line_dash="dot")
        fig.update_layout(xaxis_title="Hourly wage ($)", yaxis_title="Monthly net resources ($)", height=480, margin=dict(t=20))
        chart, legend = st.columns([3, 1.4])
        chart.plotly_chart(fig, use_container_width=True)
        with legend:
            st.markdown("#### 🔎 How to read this")
            st.markdown("**Blue line**: money your household has each month (pay + benefits + credits − taxes) at each hourly wage.")
            st.markdown(f"**● Now (${S.wage:g}/hr)**: ${facts['net_now']:,}/mo  \n**● With raise (${S.wage + S.raise_amt:g}/hr)**: ${facts['net_after']:,}/mo")
            if cliffs:
                st.markdown("**🟥 Red zone = a cliff.** Earning more *here* leaves you with *less* each month, because benefits drop faster than pay rises.")
                for z in cliffs:
                    now_in = z["start_wage"] <= S.wage <= z["end_wage"]
                    after_in = z["start_wage"] <= S.wage + S.raise_amt <= z["end_wage"]
                    st.markdown(f"- From **${z['start_wage']:.2f}** to **${z['end_wage']:.2f}/hr**, you could lose up to **${z['max_loss']:,.0f}/mo**. You're back ahead at **${z['breakeven_wage']:.2f}/hr**." if z["breakeven_wage"] else f"- From **${z['start_wage']:.2f}/hr** up, you could lose up to **${z['max_loss']:,.0f}/mo**.")
                    if now_in and not after_in: st.success("You're **in** this zone now. This raise takes you **past** it. 🎉")
                    elif now_in and after_in: st.warning("You're **in** this zone, and this raise leaves you **still inside** it. Aim higher; see step 3.")
                    elif after_in: st.warning("This raise would move you **into** the zone, so you'd take home less. Aim past the zone; see step 3.")
                    elif S.wage > z["end_wage"]: st.info("You're already **past** this zone.")
                    else: st.info("This zone is **above** your raise; a later raise could cross it.")
            else:
                st.success("**No red zone for your situation.** Every raise leaves you ahead.")
            st.markdown("**┆ Dotted line**: living wage (placeholder figure)")
        st.caption(f"Engine: {df.attrs['source']}. Verify thresholds with official sources (benefitscal.com, county office).")

with tab3:
    if gate(3):
        st.subheader("📈 Plan your raise")
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
            st.caption("Estimate from web search: " + ", ".join(mk.get("sources", [])[:3]) + " · verify before you negotiate.")
            facts.update(market_rate_usd_per_hr=dict(low=mk["low"], typical=mk["typical"], high=mk["high"]), suggested_target_usd_per_hr=target)
        elif mk:
            st.warning(mk.get("error") or "Couldn't find reliable market figures for that role; try a more common job title.")
        if st.button("Generate my negotiation script"):
            with st.spinner("Writing your negotiation script…"):
                st.markdown(llm.negotiation_script(facts, lang))
        st.divider()
        st.subheader("🧭 Get help with other next steps")
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
