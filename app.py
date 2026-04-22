"""
app.py — West Bengal 2026 Election Decision Intelligence
=========================================================
Party-neutral. User configures party labels in sidebar.
All 23 districts. State overview + district deep dive.

Run: streamlit run app.py
"""

import datetime
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
sys.path.insert(0, str(Path("pipeline").resolve()))
try:
    from importlib import import_module
    _gen = import_module("00_generate_demo_data") if False else None
except Exception:
    _gen = None

def run_generator(district=None):
    """Call generator directly in-process — much faster than subprocess."""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("gen", "pipeline/00_generate_demo_data.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if district:
        mod.generate_district(district)
    else:
        mod.generate_all()
    st.cache_data.clear()

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WB 2026 — Election Decision Intelligence",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROCESSED = Path("data/processed")
PROCESSED.mkdir(parents=True, exist_ok=True)

ALL_DISTRICTS = [
    "Murshidabad","North 24 Parganas","South 24 Parganas","Purba Medinipur",
    "Hooghly","Nadia","Paschim Medinipur","Howrah","Malda","Purba Bardhaman",
    "Bankura","Birbhum","Cooch Behar","Uttar Dinajpur","Paschim Bardhaman",
    "Jalpaiguri","Purulia","Alipurduar","Dakshin Dinajpur","Darjeeling",
    "Jhargram","Kolkata","Kalimpong",
]

CAT_LABELS = {"A":"A — Secure","B":"B — Swing","C":"C — Unfavourable","D":"D — SIR Crisis"}
CAT_COLORS = {"A":"#1D9E75","B":"#BA7517","C":"#E24B4A","D":"#7F77DD"}


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_classified(district: str) -> pd.DataFrame:
    p = PROCESSED / f"booths_classified_{district.lower().replace(' ','_')}.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["ac_code"] = pd.to_numeric(df["ac_code"], errors="coerce").astype("Int64")
        df["part_no"] = pd.to_numeric(df["part_no"], errors="coerce").astype("Int64")
        return df
    return pd.DataFrame()

@st.cache_data(ttl=300)
def load_form20(district: str) -> pd.DataFrame:
    p = PROCESSED / f"form20_{district.lower().replace(' ','_')}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

@st.cache_data(ttl=300)
def load_workers(district: str) -> pd.DataFrame:
    p = PROCESSED / f"campaign_workers_{district.lower().replace(' ','_')}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

@st.cache_data(ttl=300)
def load_targets(district: str) -> pd.DataFrame:
    p = PROCESSED / f"daily_targets_{district.lower().replace(' ','_')}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

@st.cache_data(ttl=300)
def load_state_summary() -> pd.DataFrame:
    p = PROCESSED / "state_summary.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

def save_df(df: pd.DataFrame, district: str, prefix: str):
    df.to_csv(PROCESSED / f"{prefix}_{district.lower().replace(' ','_')}.csv", index=False)
    st.cache_data.clear()


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🗳️ WB 2026")
    st.caption("Election Decision Intelligence")

    st.markdown("---")
    st.markdown("**Configure party labels**")
    st.caption("Map P1–P4 to actual party names for your analysis")
    p_labels = {
        "P1": st.text_input("P1 label", value="Party 1", key="p1"),
        "P2": st.text_input("P2 label", value="Party 2", key="p2"),
        "P3": st.text_input("P3 label", value="Party 3", key="p3"),
        "P4": st.text_input("P4 label", value="Party 4", key="p4"),
    }
    # Analyst's focus party (for "your party" calculations)
    focus_party = st.selectbox("Analysis focus party", ["P1","P2","P3","P4"],
                               format_func=lambda x: p_labels[x])

    st.markdown("---")
    district = st.selectbox("District (deep dive)", ALL_DISTRICTS)

    df_raw = load_classified(district)
    if df_raw.empty:
        st.warning(f"No data for {district}")
        if st.button(f"⚡ Generate data for {district}", use_container_width=True):
            with st.spinner(f"Generating data for {district}... (~20 sec)"):
                result = subprocess.run(
                    ["python", "pipeline/00_generate_demo_data.py", "--district", district],
                    capture_output=True, text=True, cwd=Path(".").resolve()
                )
            if result.returncode == 0:
                st.success("Done!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Error: {result.stderr[-300:]}")
        if st.button("⚡⚡ Generate ALL 23 districts", use_container_width=True):
            with st.spinner("Generating all 23 districts... (~3 min)"):
                try:
                    run_generator()
                    st.success("All 23 districts ready!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.success(f"✓ {len(df_raw):,} booths · {df_raw['total'].sum():,} electors")

    # AC filter
    ac_names_map = {}
    if not df_raw.empty:
        ac_names_map = df_raw.drop_duplicates("ac_code").set_index("ac_code")["ac_name"].to_dict()
    ac_options = ["All ACs"] + [f"{c} — {n}" for c,n in sorted(ac_names_map.items())]
    ac_filter  = st.selectbox("Filter by AC", ac_options)
    ac_code_filter = None
    if ac_filter != "All ACs":
        ac_code_filter = int(ac_filter.split(" — ")[0])

    cat_filter = st.multiselect("Booth categories", ["A","B","C","D"], default=["A","B","C","D"])

    # Apply filters — only if data is loaded
    df = df_raw.copy()
    if not df.empty:
        if ac_code_filter:
            df = df[df["ac_code"] == ac_code_filter]
        if cat_filter and "booth_category" in df.columns:
            df = df[df["booth_category"].isin(cat_filter)]

    st.markdown("---")
    el_day   = datetime.date(2026, 4, 23)
    days_left = (el_day - datetime.date.today()).days
    st.metric("Days to election (Ph 1)", f"D-{max(0,days_left)}")
    st.caption("Phase 1: Apr 23 | Phase 2: Apr 29, 2026")


def plabel(code: str) -> str:
    return p_labels.get(code, code)

def pcolor(code: str) -> str:
    cols = {"P1":"#1D9E75","P2":"#E07B39","P3":"#7F77DD","P4":"#D85A30","?":"#888780"}
    return cols.get(code, "#888780")


# ── MAIN TABS ─────────────────────────────────────────────────────────────────
tab_state, tab_dist, tab_booth, tab_sir, tab_swing, tab_ops, tab_pipe = st.tabs([
    "🗺️ State overview",
    "📊 District deep dive",
    "🏫 Booth intelligence",
    "⚠️ SIR adjudication",
    "⚖️ Swing & decision",
    "📋 Campaign ops",
    "⚙️ Pipeline",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — STATE OVERVIEW (all 23 districts)
# ════════════════════════════════════════════════════════════════════════════════
with tab_state:
    st.subheader("West Bengal 2026 — state-level decision view")
    ss = load_state_summary()
    if ss.empty:
        st.info("No state data yet. Click below to generate all 23 districts at once.")
        col_a, col_b = st.columns([1, 2])
        with col_a:
            if st.button("⚡ Generate all 23 districts", use_container_width=True, type="primary", key="gen_all_state"):
                with st.spinner("Generating all 23 districts... (~60 sec)"):
                    result = subprocess.run(
                        ["python", "pipeline/00_generate_demo_data.py", "--all"],
                        capture_output=True, text=True, cwd=Path(".").resolve()
                    )
                if result.returncode == 0:
                    st.success("All 23 districts ready!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Error: {result.stderr[-400:]}")
        with col_b:
            st.markdown("Generates realistic demo data: ~3,100 booths per district, SIR 2026 elector counts, 2021+2019 results, booth A/B/C/D classification. Takes ~60 seconds.")
        st.stop()

    # State KPIs
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total districts",       "23")
    c2.metric("Total assembly seats",  f"{ss['seats'].sum()}")
    c3.metric("Total SIR electors",    f"{ss['sir_el'].sum()/1e7:.2f} Cr")
    c4.metric("Total adjudicated",     f"{ss['sir_adj'].sum()/1e5:.1f}L",
              f"{ss['sir_adj'].sum()/ss['sir_el'].sum()*100:.1f}% of roll",
              delta_color="inverse")
    c5.metric("Electors deleted (SIR)", f"{(ss['pre_sir_el'].sum()-ss['sir_el'].sum())/1e5:.0f}L",
              f"from {ss['pre_sir_el'].sum()/1e7:.2f}Cr pre-SIR", delta_color="inverse")

    st.markdown("---")
    col_l, col_r = st.columns([3,2])

    with col_l:
        st.markdown("**Elector change: pre-SIR → SIR 2026 (all districts)**")
        ss_sorted = ss.sort_values("sir_el", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Pre-SIR electors", y=ss_sorted["district"],
            x=ss_sorted["pre_sir_el"]/1e5, orientation="h",
            marker_color="#D3D1C7", opacity=0.7,
        ))
        fig.add_trace(go.Bar(
            name="SIR 2026 electors", y=ss_sorted["district"],
            x=ss_sorted["sir_el"]/1e5, orientation="h",
            marker_color="#1D9E75",
        ))
        fig.update_layout(barmode="overlay", height=560,
                          xaxis_title="Electors (Lakhs)",
                          margin=dict(t=10,b=10), legend=dict(y=1.02,orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("**Adjudication crisis — district-wise**")
        ss_adj = ss.sort_values("sir_adj", ascending=False)
        fig2 = px.bar(ss_adj, x="sir_adj", y="district", orientation="h",
                      color="adj_pct", color_continuous_scale="RdYlGn_r",
                      text=ss_adj["sir_adj"].apply(lambda x: f"{x/1e5:.1f}L"),
                      height=560, labels={"sir_adj":"Adjudicated","adj_pct":"Adj %"})
        fig2.update_traces(textposition="outside")
        fig2.update_layout(coloraxis_colorbar=dict(title="Adj %"),
                           margin=dict(t=10,b=10))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # Full state comparison table
    st.markdown("**Full district comparison table**")
    view_cols = st.multiselect("Show columns", [
        "seats","pop2011","pre_sir_el","sir_el","sir_adj","adj_pct",
        "muslim_pct","sc_pct","st_pct","literacy","female_ratio",
        "turnout_asm","turnout_ls","p1_base","p2_base",
        "total_booths","cat_A","cat_B","cat_C","cat_D"],
        default=["seats","sir_el","sir_adj","adj_pct","muslim_pct","turnout_asm","cat_B","cat_D"])

    ss_display = ss[["district"] + view_cols].sort_values("sir_adj" if "sir_adj" in view_cols else "seats", ascending=False)
    st.dataframe(ss_display, use_container_width=True, height=460,
        column_config={
            "sir_el":       st.column_config.NumberColumn("SIR electors", format="%d"),
            "pre_sir_el":   st.column_config.NumberColumn("Pre-SIR", format="%d"),
            "sir_adj":      st.column_config.NumberColumn("Adjudicated", format="%d"),
            "adj_pct":      st.column_config.ProgressColumn("Adj %", min_value=0, max_value=60, format="%.1f%%"),
            "muslim_pct":   st.column_config.ProgressColumn("Muslim %", min_value=0, max_value=70, format="%d%%"),
            "turnout_asm":  st.column_config.ProgressColumn("Turnout (Asm)", min_value=70, max_value=92, format="%.1f%%"),
            "p1_base":      st.column_config.ProgressColumn(f"{plabel('P1')} base %", min_value=35, max_value=70, format="%.1f%%"),
        })

    # Scatter: contestability map
    st.markdown("**District contestability map** — elector base vs swing booth count")
    fig3 = px.scatter(ss, x="cat_B", y="sir_adj",
                      size="seats", color="adj_pct",
                      color_continuous_scale="RdYlGn_r",
                      hover_name="district",
                      hover_data={"seats":True,"sir_el":True,"adj_pct":True},
                      labels={"cat_B":"Swing booths (Cat B)",
                              "sir_adj":"Adjudicated voters",
                              "adj_pct":"Adj %"},
                      height=400)
    fig3.update_traces(marker=dict(line=dict(width=1,color="#fff")))
    fig3.update_layout(margin=dict(t=20,b=10))
    st.plotly_chart(fig3, use_container_width=True)
    st.caption("Bubble size = seats. Top-right = most contested + SIR-impacted districts.")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — DISTRICT DEEP DIVE
# ════════════════════════════════════════════════════════════════════════════════
with tab_dist:
    if df.empty:
        st.info(f"No data for {district}. Click to generate.")
        if st.button(f"⚡ Generate {district} data", type="primary", key="gen_dist_tab"):
            with st.spinner(f"Generating {district}..."):
                try:
                    run_generator(district=district)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        st.stop()

    st.subheader(f"{district} — district deep dive")
    ss = load_state_summary()
    dist_meta = ss[ss["district"] == district].iloc[0] if not ss.empty and district in ss["district"].values else None

    total_el  = df["total"].sum()
    fem_el    = df["female"].sum()
    adj_total = df["adj_count"].sum()

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("SIR 2026 electors",    f"{total_el:,}")
    c2.metric("Female electors",       f"{fem_el:,}", f"{fem_el/total_el*100:.1f}%")
    c3.metric("Under adjudication",    f"{adj_total:,}",
              f"{adj_total/total_el*100:.1f}%", delta_color="inverse")
    c4.metric("Booths (filtered)",     f"{len(df):,}")
    c5.metric("Swing + SIR booths",   f"{(df['booth_category'].isin(['B','D'])).sum():,}")

    if dist_meta is not None:
        st.markdown("---")
        info_cols = st.columns(6)
        info_cols[0].metric("Assembly seats",  int(dist_meta["seats"]))
        info_cols[1].metric("Population 2011", f"{dist_meta['pop2011']/1e5:.1f}L")
        info_cols[2].metric("Muslim %",        f"{dist_meta['muslim_pct']}%")
        info_cols[3].metric("SC %",            f"{dist_meta['sc_pct']}%")
        info_cols[4].metric("Literacy",        f"{dist_meta['literacy']}%")
        info_cols[5].metric("Turnout (Asm avg)",f"{dist_meta['turnout_asm']}%")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("**Booth category breakdown**")
        cats = df["booth_category"].value_counts().reset_index()
        cats.columns = ["cat","count"]
        cats["label"] = cats["cat"].map(CAT_LABELS)
        fig = px.bar(cats, x="label", y="count", color="cat",
                     color_discrete_map=CAT_COLORS, text="count", height=300)
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, margin=dict(t=10,b=10),
                          xaxis_title="", yaxis_title="Booths")
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("**Electors by booth category**")
        cat_el = df.groupby("booth_category")["total"].sum().reset_index()
        cat_el["label"] = cat_el["booth_category"].map(CAT_LABELS)
        fig2 = px.pie(cat_el, names="label", values="total",
                      color="booth_category", color_discrete_map=CAT_COLORS,
                      hole=0.45, height=300)
        fig2.update_layout(margin=dict(t=10,b=10), legend=dict(font_size=10))
        st.plotly_chart(fig2, use_container_width=True)

    # AC summary table
    st.markdown("**AC-level breakdown**")
    ac_sum = df.groupby(["ac_code","ac_name"]).agg(
        booths=("part_no","count"), electors=("total","sum"),
        female=("female","sum"), adj=("adj_count","sum"),
        A=("booth_category",lambda x:(x=="A").sum()),
        B=("booth_category",lambda x:(x=="B").sum()),
        C=("booth_category",lambda x:(x=="C").sum()),
        D=("booth_category",lambda x:(x=="D").sum()),
    ).reset_index()
    ac_sum["female_pct"] = (ac_sum["female"]/ac_sum["electors"]*100).round(1)
    ac_sum["adj_pct"]    = (ac_sum["adj"]/ac_sum["electors"]*100).round(1)
    ac_sum["votes_to_win"] = (ac_sum["electors"] * (dist_meta["turnout_asm"]/100 if dist_meta is not None else 0.84) * 0.501).round(0).astype(int)
    ac_sum = ac_sum.sort_values("adj_pct", ascending=False)

    st.dataframe(ac_sum[["ac_code","ac_name","booths","electors","female_pct",
                          "adj","adj_pct","A","B","C","D","votes_to_win"]],
        use_container_width=True, height=380,
        column_config={
            "ac_code":      st.column_config.NumberColumn("AC", width=65),
            "ac_name":      st.column_config.TextColumn("Name", width=150),
            "electors":     st.column_config.NumberColumn("Electors", format="%d"),
            "female_pct":   st.column_config.ProgressColumn("Female %",min_value=44,max_value=54,format="%.1f%%"),
            "adj_pct":      st.column_config.ProgressColumn("Adj %",   min_value=0, max_value=65,format="%.1f%%"),
            "votes_to_win": st.column_config.NumberColumn("Votes to win", format="%d"),
        })

    # Elector trend
    st.markdown("**Elector trend 2016 → SIR 2026**")
    if dist_meta is not None:
        trend_df = pd.DataFrame({"Year":["2016 Asm","2019 LS","2021 Asm","2024 LS","2026 SIR"],
            "Electors":[dist_meta["pre_sir_el"]*0.90, dist_meta["pre_sir_el"]*0.955,
                        dist_meta["pre_sir_el"]*0.93,  dist_meta["pre_sir_el"],
                        dist_meta["sir_el"]]})
        fig3 = px.line(trend_df, x="Year", y="Electors", markers=True,
                       color_discrete_sequence=["#1D9E75"], height=240)
        fig3.update_traces(line_width=2.5, marker_size=8)
        fig3.update_layout(yaxis_tickformat=",", margin=dict(t=10,b=10))
        st.plotly_chart(fig3, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — BOOTH INTELLIGENCE
# ════════════════════════════════════════════════════════════════════════════════
with tab_booth:
    if df.empty:
        st.info(f"No booth data for {district}. Generate it in the sidebar."); st.stop()

    st.subheader(f"Booth intelligence — {district}")

    col_l,col_r = st.columns([3,1])
    with col_l:
        search = st.text_input("Search booth name", placeholder="Type booth name or AC…")
    with col_r:
        sort_by = st.selectbox("Sort by",
            ["priority_score","adj_pct","total","P1_share_2021","P2_share_2021","margin_2021"])

    disp = df.copy()
    if search:
        mask = (disp["booth_name"].str.contains(search, case=False, na=False) |
                disp["ac_name"].str.contains(search, case=False, na=False))
        disp = disp[mask]
    disp = disp.sort_values(sort_by, ascending=False)

    # Rename P1/P2 columns for display
    disp_show = disp.rename(columns={
        "P1_share_2021": f"{plabel('P1')} % 2021",
        "P2_share_2021": f"{plabel('P2')} % 2021",
        "winner_2021":   "Winner 2021",
        "winner_2019":   "Winner 2019",
    })

    st.caption(f"Showing {len(disp_show):,} booths")
    st.dataframe(
        disp_show[["ac_name","part_no","booth_name","total","female","female_pct",
                   "adj_count","adj_pct",
                   f"{plabel('P1')} % 2021",f"{plabel('P2')} % 2021",
                   "Winner 2021","margin_2021","Winner 2019","flipped_19_21",
                   "booth_category","votes_to_win_est","worker_assigned"]],
        use_container_width=True, height=500,
        column_config={
            "ac_name":    st.column_config.TextColumn("AC",       width=130),
            "part_no":    st.column_config.NumberColumn("Part",   width=55),
            "booth_name": st.column_config.TextColumn("Booth",    width=200),
            "female_pct": st.column_config.ProgressColumn("Female %",min_value=44,max_value=54,format="%.1f%%"),
            "adj_pct":    st.column_config.ProgressColumn("Adj %",  min_value=0, max_value=65,format="%.1f%%"),
            f"{plabel('P1')} % 2021": st.column_config.ProgressColumn(f"{plabel('P1')} %",min_value=0,max_value=100,format="%.1f%%"),
            f"{plabel('P2')} % 2021": st.column_config.ProgressColumn(f"{plabel('P2')} %",min_value=0,max_value=100,format="%.1f%%"),
            "flipped_19_21": st.column_config.CheckboxColumn("Flipped"),
            "booth_category": st.column_config.SelectboxColumn("Cat", options=["A","B","C","D"], width=60),
        })

    cc1,cc2 = st.columns(2)
    with cc1:
        st.download_button("⬇️ Download filtered booths (CSV)",
            disp.to_csv(index=False).encode(), "booths_filtered.csv", "text/csv")
    with cc2:
        st.download_button("⬇️ Download priority booths (B+D only)",
            df[df["booth_category"].isin(["B","D"])].to_csv(index=False).encode(),
            "priority_booths.csv", "text/csv", key="dl_priority")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — SIR ADJUDICATION
# ════════════════════════════════════════════════════════════════════════════════
with tab_sir:
    if df.empty:
        st.info(f"No data for {district}. Use the sidebar button to generate."); st.stop()

    st.subheader(f"SIR 2026 adjudication crisis — {district}")
    st.error(
        f"**{df['adj_count'].sum():,} electors ({df['adj_count'].sum()/df['total'].sum()*100:.1f}%)** "
        "are on the roll but **cannot vote** until judicial clearance. "
        "Restoring these voters via Form 6 is the highest-ROI campaign action available right now."
    )

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Cat D booths (>10% adj)", f"{(df['booth_category']=='D').sum():,}")
    c2.metric("Total adjudicated",       f"{df['adj_count'].sum():,}")
    c3.metric("Highest adj% booth",      f"{df['adj_pct'].max():.1f}%")
    c4.metric("ACs avg adj > 15%",       f"{(df.groupby('ac_code')['adj_pct'].mean() > 15).sum()}")

    col_l,col_r = st.columns(2)
    with col_l:
        ac_adj = df.groupby(["ac_code","ac_name"]).agg(
            adj=("adj_count","sum"), el=("total","sum")).reset_index()
        ac_adj["adj_pct"] = (ac_adj["adj"]/ac_adj["el"]*100).round(1)
        ac_adj = ac_adj.sort_values("adj_pct",ascending=True)
        fig = px.bar(ac_adj, x="adj_pct", y="ac_name", orientation="h",
                     color="adj_pct", color_continuous_scale="RdYlGn_r",
                     text="adj_pct", height=max(300,len(ac_adj)*22),
                     labels={"adj_pct":"Adj %","ac_name":""})
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(coloraxis_showscale=False, margin=dict(t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("**Adj % histogram across booths**")
        fig2 = px.histogram(df, x="adj_pct", nbins=35,
                            color_discrete_sequence=["#7F77DD"], height=240)
        fig2.add_vline(x=10, line_dash="dash", line_color="red",
                       annotation_text="10% threshold (Cat D)")
        fig2.update_layout(margin=dict(t=20,b=10), xaxis_title="Adj %")
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("**What to do now**")
        st.info("""
**Form 6 restoration campaign:**
1. Identify all booths where adj_pct > 10% (Category D)
2. Assign a party worker to each affected household
3. Help voters file Form 6 at their ERO office (deadline varies — check CEO WB)
4. Document each case via RTI (rtionline.gov.in) if rejected
5. Track using the Campaign Ops tab below

Every voter restored here is ~95% probability of voting for their original party choice.
""")

    st.markdown("**Top 50 booths by adjudication count**")
    top = df.nlargest(50,"adj_count")[
        ["ac_name","part_no","booth_name","total","adj_count","adj_pct",
         "P1_share_2021","winner_2021"]
    ].rename(columns={"P1_share_2021":f"{plabel('P1')} % 2021","winner_2021":"Winner 2021"})
    st.dataframe(top, use_container_width=True, height=360,
        column_config={
            "adj_pct": st.column_config.ProgressColumn("Adj %", min_value=0, max_value=65, format="%.1f%%"),
        })
    st.download_button("⬇️ Download adjudicated booth list",
        top.to_csv(index=False).encode(), "adjudicated_booths.csv", "text/csv")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — SWING & DECISION
# ════════════════════════════════════════════════════════════════════════════════
with tab_swing:
    if df.empty:
        st.info(f"No data for {district}. Use the sidebar button to generate."); st.stop()

    st.subheader(f"Swing analysis & decision calculator — {district}")

    ss = load_state_summary()
    dist_meta = ss[ss["district"]==district].iloc[0] if not ss.empty and district in ss["district"].values else None

    swing_b = df[df["booth_category"]=="B"]
    flipped = df[df["flipped_19_21"].fillna(False)==True] if "flipped_19_21" in df.columns else pd.DataFrame()
    tight   = df[df["margin_2021"] < 50] if "margin_2021" in df.columns else pd.DataFrame()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Swing booths (Cat B)",   f"{len(swing_b):,}")
    c2.metric("Booths flipped 19→21",   f"{len(flipped):,}")
    c3.metric("Margin < 50 votes",      f"{len(tight):,}")
    c4.metric("Avg votes to win/booth", f"{int(df['votes_to_win_est'].mean()):,}")

    col_l,col_r = st.columns(2)
    with col_l:
        st.markdown(f"**{plabel('P1')} vote share distribution 2021**")
        if "P1_share_2021" in df.columns:
            fig = px.histogram(df, x="P1_share_2021", nbins=30,
                               color="booth_category", color_discrete_map=CAT_COLORS,
                               height=280, labels={"P1_share_2021":f"{plabel('P1')} share 2021 (%)"})
            fig.add_vline(x=50, line_dash="dash", line_color="gray", annotation_text="50%")
            fig.update_layout(margin=dict(t=20,b=10))
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("**Win margin distribution 2021**")
        if "margin_2021" in df.columns:
            fig2 = px.histogram(df, x="margin_2021", nbins=40,
                                color="winner_2021",
                                color_discrete_sequence=px.colors.qualitative.Set2,
                                height=280, labels={"margin_2021":"Win margin (votes)"})
            fig2.update_layout(margin=dict(t=20,b=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("Votes-to-win calculator")

    col1,col2,col3 = st.columns(3)
    with col1:
        ac_list = ["Whole district"] + [f"{c} — {n}" for c,n in sorted(ac_names_map.items())]
        calc_ac = st.selectbox("Scope", ac_list, key="swing_ac")
    with col2:
        default_t = int(dist_meta["turnout_asm"]) if dist_meta is not None else 84
        tgt_t = st.slider("Expected turnout 2026 (%)", 72, 92, default_t)
    with col3:
        calc_party = st.selectbox("Calculate for", ["P1","P2","P3","P4"],
                                  format_func=lambda x: plabel(x))

    calc_df = df if calc_ac == "Whole district" else df[df["ac_code"] == int(calc_ac.split(" — ")[0])]
    tot_el   = calc_df["total"].sum()
    exp_v    = round(tot_el * tgt_t / 100)
    v2win    = round(exp_v * 0.501)
    fem_v    = round(exp_v * calc_df["female"].sum() / max(calc_df["total"].sum(), 1))
    adj_v    = calc_df["adj_count"].sum()
    swing1pp = round(tot_el * 0.01)

    sc1,sc2,sc3,sc4,sc5 = st.columns(5)
    sc1.metric("Total electors",              f"{tot_el:,}")
    sc2.metric(f"Expected votes @ {tgt_t}%",  f"{exp_v:,}")
    sc3.metric("Votes to win (50%+1)",        f"{v2win:,}")
    sc4.metric("Expected female votes",       f"{fem_v:,}")
    sc5.metric("1pp turnout swing =",         f"+{swing1pp:,} votes")

    pkey = f"votes_{calc_party}_2021"
    if pkey in calc_df.columns:
        avg_share = calc_df[pkey].sum() / max(calc_df["total_votes_2021"].sum(), 1) * 100
        current_proj = round(exp_v * avg_share / 100)
        gap = v2win - current_proj
        if gap > 0:
            st.warning(
                f"**{plabel(calc_party)} 2021 avg share: {avg_share:.1f}%** → projects **{current_proj:,} votes** "
                f"at {tgt_t}% turnout. **Gap to win: {gap:,} votes** "
                f"({gap/swing1pp:.1f}pp turnout swing needed, or {adj_v:,} SIR voters restored)."
            )
        else:
            st.success(
                f"**{plabel(calc_party)} 2021 avg share: {avg_share:.1f}%** → projects **{current_proj:,} votes**, "
                f"which exceeds the win threshold of {v2win:,}. Defend your base and ensure turnout."
            )

    st.info(
        f"**SIR adjudicated in scope: {adj_v:,} voters.** "
        f"If 60% are restored and vote at historical rates → **{round(adj_v*0.6*avg_share/100 if pkey in calc_df.columns else 0):,}** "
        f"additional votes for {plabel(calc_party)}. This is the single highest-leverage action."
    )

    # Micro-swing table
    st.markdown("**Micro-swing booths — margin ≤ 100 votes (2021)**")
    if "margin_2021" in df.columns:
        micro = df[df["margin_2021"] <= 100].sort_values("margin_2021").head(100)
        micro_show = micro.rename(columns={
            "P1_share_2021": f"{plabel('P1')} % 2021",
            "P2_share_2021": f"{plabel('P2')} % 2021",
        })
        st.dataframe(
            micro_show[["ac_name","part_no","booth_name","total",
                        f"{plabel('P1')} % 2021",f"{plabel('P2')} % 2021",
                        "winner_2021","margin_2021","winner_2019","flipped_19_21",
                        "adj_count","booth_category"]],
            use_container_width=True, height=380,
            column_config={
                "margin_2021":    st.column_config.ProgressColumn("Margin", min_value=0, max_value=100, format="%d"),
                "flipped_19_21":  st.column_config.CheckboxColumn("Flipped"),
            })


# ════════════════════════════════════════════════════════════════════════════════
# TAB 6 — CAMPAIGN OPS
# ════════════════════════════════════════════════════════════════════════════════
with tab_ops:
    if df.empty:
        st.info(f"No data for {district}. Use the sidebar button to generate."); st.stop()

    st.subheader(f"Campaign operations — {district}")
    ops1, ops2, ops3 = st.tabs(["Worker assignment","Daily tracking","D-Day targets"])

    # ── Worker assignment ──────────────────────────────────────────────────────
    with ops1:
        workers = load_workers(district)
        if workers.empty:
            st.warning("No workers loaded."); st.stop()

        st.metric("Workers registered", f"{len(workers):,}")
        assigned = (df["worker_assigned"].fillna("")!="").sum()
        prio_total = (df["booth_category"].isin(["B","D"])).sum()
        st.progress(assigned/max(prio_total,1), text=f"Priority booths assigned: {assigned}/{prio_total}")

        col1,col2,col3 = st.columns(3)
        with col1:
            filter_ac = st.selectbox("Filter AC", ["All"]+list(ac_names_map.values()), key="wk_ac")
        with col2:
            filter_cat = st.multiselect("Categories", ["B","D"], default=["B","D"], key="wk_cat")
        with col3:
            show_unassigned = st.checkbox("Unassigned only", value=True)

        assign_df = df.copy()
        if filter_ac != "All":
            assign_df = assign_df[assign_df["ac_name"]==filter_ac]
        assign_df = assign_df[assign_df["booth_category"].isin(filter_cat)]
        if show_unassigned:
            assign_df = assign_df[assign_df["worker_assigned"].fillna("")==""]

        st.caption(f"{len(assign_df):,} booths shown")
        if not assign_df.empty and not workers.empty:
            avail = workers[workers["assigned_booth_part"].isna()]["name"].tolist()
            c1,c2 = st.columns(2)
            with c1:
                sel_b = st.selectbox("Booth to assign",
                    assign_df.apply(lambda r: f"AC {r['ac_code']} | Pt {r['part_no']} | {r['booth_name'][:40]}", axis=1))
            with c2:
                sel_w = st.selectbox("Assign worker", avail[:80])
            if st.button("✅ Assign"):
                pt  = int(sel_b.split("|")[1].replace("Pt","").strip())
                ac  = int(sel_b.split("|")[0].replace("AC","").strip())
                full = load_classified(district)
                full.loc[(full["ac_code"]==ac)&(full["part_no"]==pt),"worker_assigned"] = sel_w
                save_df(full, district, "booths_classified")
                st.success(f"Assigned {sel_w} → Part {pt}")
                st.rerun()

        st.download_button("⬇️ Download unassigned priority booths",
            assign_df[["ac_code","ac_name","part_no","booth_name","booth_category","adj_pct","margin_2021"]].to_csv(index=False).encode(),
            "unassigned.csv")

    # ── Daily tracking ─────────────────────────────────────────────────────────
    with ops2:
        tgt = load_targets(district)
        if tgt.empty:
            st.warning("No targets data."); st.stop()

        t_m = tgt.merge(df[["ac_code","part_no","booth_name","ac_name","booth_category","adj_pct"]],
                        on=["ac_code","part_no"], how="left", suffixes=("","_"))

        tot_t = t_m["target_contacts"].sum()
        tot_d = t_m["contacts_done"].sum()
        pct_d = tot_d/max(tot_t,1)*100

        c1,c2,c3 = st.columns(3)
        c1.metric("Target contacts", f"{tot_t:,}")
        c2.metric("Done",            f"{tot_d:,}", f"{pct_d:.1f}%")
        c3.metric("Remaining",       f"{tot_t-tot_d:,}")
        st.progress(pct_d/100, text=f"Overall: {pct_d:.1f}%")

        ac_prog = t_m.groupby("ac_name").agg(tgt=("target_contacts","sum"),done=("contacts_done","sum")).reset_index()
        ac_prog["pct"] = (ac_prog["done"]/ac_prog["tgt"].clip(1)*100).round(1)
        ac_prog = ac_prog.sort_values("pct")
        fig = px.bar(ac_prog, x="pct", y="ac_name", orientation="h",
                     color="pct", color_continuous_scale="RdYlGn",
                     text="pct", height=max(300,len(ac_prog)*22),
                     labels={"pct":"% complete","ac_name":""})
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(coloraxis_showscale=False, margin=dict(t=10,b=10), xaxis_range=[0,115])
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Update progress**")
        c1,c2,c3 = st.columns(3)
        with c1:
            upd_ac   = st.selectbox("AC", sorted(t_m["ac_name"].dropna().unique()), key="upd_ac")
        with c2:
            parts    = t_m[t_m["ac_name"]==upd_ac]["part_no"].tolist()
            upd_part = st.selectbox("Part", parts, key="upd_pt")
        with c3:
            curr     = int(t_m[(t_m["ac_name"]==upd_ac)&(t_m["part_no"]==upd_part)]["contacts_done"].iloc[0]) if len(t_m[(t_m["ac_name"]==upd_ac)&(t_m["part_no"]==upd_part)])>0 else 0
            new_c    = st.number_input("Contacts done", min_value=0, value=curr, step=5)
        if st.button("✅ Update"):
            ac_u = int(t_m[t_m["ac_name"]==upd_ac]["ac_code"].iloc[0])
            ft   = load_targets(district)
            ft.loc[(ft["ac_code"]==ac_u)&(ft["part_no"]==int(upd_part)),"contacts_done"] = new_c
            ft.loc[(ft["ac_code"]==ac_u)&(ft["part_no"]==int(upd_part)),"last_contact_date"] = str(datetime.date.today())
            save_df(ft, district, "daily_targets")
            st.success("Updated!"); st.rerun()

    # ── D-Day ──────────────────────────────────────────────────────────────────
    with ops3:
        st.markdown("**Election day hourly booth targets**")
        bd = df[df["booth_category"].isin(["B","D"])].copy()
        bd["by_1pm"] = (bd["votes_to_win_est"]*0.42).round(0).astype(int)
        bd["by_3pm"] = (bd["votes_to_win_est"]*0.70).round(0).astype(int)
        bd["by_5pm"] = (bd["votes_to_win_est"]*0.90).round(0).astype(int)
        bd_show = bd[["ac_name","part_no","booth_name","total",
                      "votes_to_win_est","by_1pm","by_3pm","by_5pm",
                      "worker_assigned","booth_category"]].head(150)
        st.dataframe(bd_show, use_container_width=True, height=440,
            column_config={
                "votes_to_win_est": st.column_config.NumberColumn("Win target",format="%d"),
                "by_1pm":           st.column_config.NumberColumn("By 1pm",    format="%d"),
                "by_3pm":           st.column_config.NumberColumn("By 3pm",    format="%d"),
                "by_5pm":           st.column_config.NumberColumn("By 5pm",    format="%d"),
            })
        st.download_button("⬇️ Download D-Day targets",
            bd.to_csv(index=False).encode(), "dday_targets.csv")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 7 — PIPELINE
# ════════════════════════════════════════════════════════════════════════════════
with tab_pipe:
    st.subheader("Data pipeline")

    st.markdown("### Step 0 — Demo data (all 23 districts, no PDFs needed)")
    col1,col2 = st.columns(2)
    with col1:
        run_one = st.selectbox("Generate single district", ["(all)"] + ALL_DISTRICTS)
    with col2:
        if st.button("▶️ Run demo data generator"):
            cmd = ["python","pipeline/00_generate_demo_data.py"]
            if run_one != "(all)":
                cmd += ["--district", run_one]
            else:
                cmd += ["--all"]
            with st.spinner("Generating..."):
                r = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(".").resolve())
            if r.returncode == 0:
                st.success("Done!"); st.code(r.stdout); st.cache_data.clear(); st.rerun()
            else:
                st.error("Error:"); st.code(r.stderr)

    st.markdown("---")

    st.markdown("""
### Production data acquisition (real PDFs)

| Step | Source | Script |
|------|--------|--------|
| 1 | [voters.eci.gov.in](https://voters.eci.gov.in/download-eroll) → SIR FinalRoll-Rev2 2026 | `python pipeline/01_download_sir_rolls.py --district Murshidabad --all_acs` |
| 2 | Extract booth PDFs to CSV | `python pipeline/02_extract_sir_rolls.py --district Murshidabad` |
| 3 | [ceowestbengal.wb.gov.in/SIR](https://ceowestbengal.wb.gov.in/SIR) → Adjudication List 15A | `python pipeline/03_extract_adjudication.py --district Murshidabad` |
| 4 | [results.eci.gov.in](https://results.eci.gov.in) → Form 20, 2021 + 2019 | `python pipeline/04_extract_form20.py --district Murshidabad --merge` |

**Folder structure for downloaded PDFs:**
```
data/raw/sir_rolls/Murshidabad/{ac_code}_{ac_name}/part_001.pdf
data/raw/adjudication/Murshidabad/{ac_code}/adj_latest.pdf
data/raw/form20/Murshidabad/2021/{ac_code}_ACName.pdf
data/raw/form20/Murshidabad/2019/{ac_code}_ACName.pdf
```
    """)

    st.markdown("---")
    st.markdown("### Data status — all districts")

    rows = []
    for dn in ALL_DISTRICTS:
        d = dn.lower().replace(" ","_")
        rows.append({
            "District": dn,
            "SIR rolls": "✅" if (PROCESSED/f"sir_rolls_{d}.csv").exists() else "❌",
            "Form 20":   "✅" if (PROCESSED/f"form20_{d}.csv").exists() else "❌",
            "Classified":"✅" if (PROCESSED/f"booths_classified_{d}.csv").exists() else "❌",
            "Workers":   "✅" if (PROCESSED/f"campaign_workers_{d}.csv").exists() else "❌",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=500)
