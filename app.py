import streamlit as st, plotly.graph_objects as go
import engine, llm

st.set_page_config(page_title="Cliff Navigator", page_icon="📈", layout="wide")
D = dict(hours=30, wage=22.0, kids=2, rent=2800, county="Alameda", raise_amt=4.0)
for k, v in D.items(): st.session_state.setdefault(k, v)
st.session_state.setdefault("chat", [])
LIVING_WAGE = {"San Francisco": 57, "Alameda": 52, "Santa Clara": 58}  # PLACEHOLDER: replace w/ MIT figures

# apply chat-extracted updates before widgets are created
for k, v in st.session_state.pop("pending", {}).items():
    if k == "kid_ages": st.session_state["kids"] = min(len(v), 4)
    elif k == "raise_amt": st.session_state["raise_amt"] = float(v)
    elif k == "wage": st.session_state["wage"] = float(v)
    else: st.session_state[k] = v

st.title("📈 Benefits Cliff Navigator")
st.caption("Will this raise actually help? Bay Area single parents · synthetic data only · estimates, not legal advice")

with st.sidebar:
    lang = st.selectbox("Language", ["English", "Spanish", "Chinese (Simplified)", "Tagalog", "Vietnamese"])
    if st.button("Load persona: Maria (Oakland)"):
        for k, v in D.items(): st.session_state[k] = v
        st.rerun()
    st.selectbox("County", llm.COUNTIES, key="county")
    st.slider("Hours / week", 5, 50, key="hours")
    st.slider("Hourly wage ($)", 12.0, 60.0, step=0.5, key="wage")
    st.slider("Kids", 0, 4, key="kids")
    st.slider("Monthly rent ($)", 500, 5000, step=50, key="rent")
    st.slider("Raise offered ($/hr)", 0.0, 15.0, step=0.5, key="raise_amt")

S = st.session_state

@st.cache_data(show_spinner="Running tax-benefit simulation…")
def run(hours, kids, rent, county):
    p = dict(hours=hours, kid_ages=[4, 7, 10, 13][:kids], rent=rent, county=county, max_wage=70)
    df = engine.sweep(p); return df, engine.find_cliffs(df)
df, cliffs = run(S.hours, S.kids, S.rent, S.county)
facts = engine.raise_report(df, S.wage, S.raise_amt)
facts.update(county=S.county, kids=S.kids, hours=S.hours, rent=S.rent, cliff_zones=cliffs, wages_are_hourly_usd=True,
             programs=engine.program_report(df, S.wage, S.raise_amt))

tab1, tab2, tab3, tab4 = st.tabs(["💬 Intake", "📊 Cliff chart", "🎯 Raise planner & script", "📋 Action pack"])

with tab1:
    for m in S.chat:
        st.chat_message(m["role"]).write(m["content"])
    if msg := st.chat_input("e.g. I work 30 hrs at $22, two kids ages 4 and 7, rent $2,800 in Oakland, offered $4 more"):
        S.chat.append({"role": "user", "content": msg})
        reply, upd = llm.intake_turn(S.chat, {})
        S.chat.append({"role": "assistant", "content": reply})
        S.pending = upd; st.rerun()

with tab2:
    c1, c2, c3 = st.columns(3)
    c1.metric("Take-home now (monthly)", f"${facts['net_now']:,}")
    c2.metric(f"After +${S.raise_amt:g}/hr", f"${facts['net_after']:,}", f"{facts['monthly_change']:+,}")
    c3.metric("Break-even wage", f"${facts['breakeven_wage']}/hr" if facts["breakeven_wage"] else "No cliff hit")
    fig = go.Figure(go.Scatter(x=df.wage, y=df.net_monthly, mode="lines", name="Net monthly resources", line=dict(width=3)))
    for z in cliffs: fig.add_vrect(x0=z["start_wage"], x1=z["end_wage"], fillcolor="red", opacity=0.15, line_width=0,
                                   annotation_text="cliff zone", annotation_position="top left")
    for x, lab in [(S.wage, "Now"), (S.wage + S.raise_amt, "With raise")]:
        fig.add_trace(go.Scatter(x=[x], y=[engine.net_at(df, x)], mode="markers+text", text=[lab], textposition="top center",
                                 marker=dict(size=12), showlegend=False))
    fig.add_vline(x=min(LIVING_WAGE[S.county], 70), line_dash="dot", annotation_text="Living wage (placeholder)")
    fig.update_layout(xaxis_title="Hourly wage ($)", yaxis_title="Monthly net resources ($)", height=480)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Engine: {df.attrs['source']}. Verify thresholds with official sources (benefitscal.com, county office).")
    if st.button("Explain this in plain language"):
        st.write(llm.explain(facts, lang))

with tab3:
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
        st.markdown(llm.negotiation_script(facts, lang))

with tab4:
    if st.button("Build my action pack"):
        st.markdown(llm.action_pack(facts, lang))
