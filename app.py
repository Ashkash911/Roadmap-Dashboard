
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Roadmap Dashboard", layout="wide")
st.title("📊 Product Roadmap Dashboard (Internal)")
st.caption("Upload Excel/CSV → auto KPIs + charts")

REQUIRED_COLUMNS = [
    "Initiative","Category","Track","Quarter","PlannedStart","PlannedEnd",
    "ActualStart","ActualEnd","Status","Revenue","Effort","BreakEvenMonths","Module"
]

# Sidebar: help + download template link
with st.sidebar:
    st.header("How to use")
    st.write("""
    1. Prepare your Excel/CSV with these columns:
    - Initiative, Category (Enhancement/New Feature/Algorithm/Feature), Track (AI/Automation or DDE), Module
    - Quarter (e.g., 2025-Q3)
    - PlannedStart, PlannedEnd, ActualStart, ActualEnd (YYYY-MM-DD)
    - Status (Planned/In Progress/Completed/Delayed/Blocked)
    - Revenue (numeric), Effort (hours or person-days), BreakEvenMonths (numeric)
    2. Upload file → dashboard updates automatically.
    """)
    st.markdown("**Template columns** are listed above.")

uploaded = st.file_uploader("Upload roadmap file (CSV or XLSX)", type=["csv", "xlsx"])

if not uploaded:
    st.info("Upload a CSV/XLSX to continue. You can start from the sample included in the repo.")
    st.stop()

# Read input
try:
    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

# Validate columns
missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
if missing:
    st.error(f"Your file is missing required columns: {missing}")
    st.stop()

# Parse dates safely
for c in ["PlannedStart","PlannedEnd","ActualStart","ActualEnd"]:
    df[c] = pd.to_datetime(df[c], errors="coerce")

# Derive helpers
df["Completed"] = df["Status"].str.lower().eq("completed")
df["OnTime"] = df["Completed"] & (df["ActualEnd"] <= df["PlannedEnd"])

# Filters
with st.expander("🔎 Filters", expanded=False):
    cols = st.columns(5)
    track_f = cols[0].multiselect("Track", sorted(df["Track"].dropna().unique().tolist()))
    cat_f = cols[1].multiselect("Category", sorted(df["Category"].dropna().unique().tolist()))
    mod_f = cols[2].multiselect("Module", sorted(df["Module"].dropna().unique().tolist()))
    qtr_f = cols[3].multiselect("Quarter", sorted(df["Quarter"].dropna().unique().tolist()))
    status_f = cols[4].multiselect("Status", sorted(df["Status"].dropna().unique().tolist()))

mask = pd.Series(True, index=df.index)
if track_f: mask &= df["Track"].isin(track_f)
if cat_f: mask &= df["Category"].isin(cat_f)
if mod_f: mask &= df["Module"].isin(mod_f)
if qtr_f: mask &= df["Quarter"].isin(qtr_f)
if status_f: mask &= df["Status"].isin(status_f)
fdf = df[mask].copy()

# KPIs
total = len(fdf)
completed = int(fdf["Completed"].sum())
planned_vs_completed = f"{completed}/{total}" if total else "0/0"

total_rev = float(fdf["Revenue"].sum()) if total else 0.0
total_effort = float(fdf["Effort"].sum()) if total else 0.0
avg_breakeven = float(fdf["BreakEvenMonths"].mean()) if total else 0.0

if fdf["OnTime"].notna().any():
    ontime = round(100 * fdf["OnTime"].mean(), 1)
else:
    ontime = None

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Initiatives Completed / Total", planned_vs_completed)
k2.metric("Total Revenue Opportunity", f"${total_rev:,.1f}M")
k3.metric("On-Time Delivery %", f"{ontime}%" if ontime is not None else "N/A")
k4.metric("Total Effort", f"{int(total_effort):,}")
k5.metric("Avg Break-Even (mo)", f"{avg_breakeven:.1f}" if total else "N/A")

# Table
st.subheader("📋 Initiatives")
st.dataframe(
    fdf.sort_values(["Quarter","Status","Initiative"]).reset_index(drop=True),
    use_container_width=True
)

# Charts row 1
c1, c2 = st.columns(2)

with c1:
    # Revenue by Quarter (stacked by Track)
    rev = fdf.groupby(["Quarter","Track"], as_index=False)["Revenue"].sum()
    if not rev.empty:
        fig = px.bar(rev, x="Quarter", y="Revenue", color="Track", title="Revenue Opportunity by Quarter (stacked)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Revenue chart: no data after filters.")

with c2:
    # On-time delivery trend (by Quarter based on PlannedEnd)
    tmp = fdf.dropna(subset=["PlannedEnd"]).copy()
    if not tmp.empty:
        tmp["QKey"] = tmp["PlannedEnd"].dt.to_period("Q").astype(str)
        trend = tmp.groupby("QKey", as_index=False)["OnTime"].mean()
        trend["OnTimePct"] = (trend["OnTime"]*100).round(1)
        fig = px.line(trend, x="QKey", y="OnTimePct", markers=True, title="On-Time Delivery Trend (%)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("On-time trend: need PlannedEnd dates.")

# Charts row 2
c3, c4 = st.columns(2)

with c3:
    # Completed by Category
    comp = fdf[fdf["Completed"]].groupby("Category", as_index=False).size()
    if not comp.empty:
        fig = px.bar(comp, x="Category", y="size", title="Initiatives Completed by Category")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Completed-by-Category chart: no completed items after filters.")

with c4:
    # Effort vs Revenue bubble
    bub = fdf.dropna(subset=["Effort","Revenue"]).copy()
    if not bub.empty:
        fig = px.scatter(
            bub, x="Effort", y="Revenue", size="BreakEvenMonths", color="Category",
            hover_name="Initiative", title="Effort vs Revenue (bubble = BreakEven months)"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Effort vs Revenue: need Effort & Revenue values.")

# Timeline (Planned vs Actual)
st.subheader("🗓️ Timeline (Gantt)")
opt = st.radio("Show timeline for:", ["Planned", "Actual"], horizontal=True)
if opt == "Planned":
    tl = fdf.dropna(subset=["PlannedStart","PlannedEnd"]).copy()
    if not tl.empty:
        fig = px.timeline(
            tl, x_start="PlannedStart", x_end="PlannedEnd",
            y="Initiative", color="Status", hover_data=["Quarter","Category","Track"]
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No Planned dates available for timeline.")
else:
    tl = fdf.dropna(subset=["ActualStart","ActualEnd"]).copy()
    if not tl.empty:
        fig = px.timeline(
            tl, x_start="ActualStart", x_end="ActualEnd",
            y="Initiative", color="Status", hover_data=["Quarter","Category","Track"]
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No Actual dates available for timeline.")

st.caption("Tip: Use the Filters section to slice by Track (AI/Automation vs DDE), Category, Module, Quarter or Status.")
