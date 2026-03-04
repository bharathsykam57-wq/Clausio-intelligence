"""
eval/dashboard.py
Streamlit dashboard for visualizing RAGAS evaluation history.

RUN: streamlit run backend/eval/dashboard.py

Shows:
  - Metric evolution across all eval runs (line chart)
  - Best and worst performing questions per run
  - Score comparison table
"""
import json
import glob
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="LexIA Eval Dashboard", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0a0a0f; color: #e2e8f0; }
    h1, h2, h3 { color: #e2e8f0; }
</style>
""", unsafe_allow_html=True)

st.title("📊 LexIA — Evaluation Dashboard")
st.caption("RAGAS metric evolution across pipeline improvements")

# Load summary history
summary_path = Path("eval/results/summary.json")
if not summary_path.exists():
    st.warning("No evaluation results yet. Run: `python -m eval.evaluate --tag baseline`")
    st.stop()

with open(summary_path) as f:
    history = json.load(f)

df_summary = pd.DataFrame(history)

# ── Metric Evolution Chart ──
st.subheader("Metric Evolution by Run")

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
COLORS = {"faithfulness": "#7c3aed", "answer_relevancy": "#10b981", "context_precision": "#f59e0b", "context_recall": "#3b82f6"}

fig = go.Figure()
for metric in METRICS:
    if metric in df_summary.columns:
        fig.add_trace(go.Scatter(
            x=df_summary["tag"],
            y=df_summary[metric],
            mode="lines+markers",
            name=metric,
            line=dict(color=COLORS[metric], width=2),
            marker=dict(size=8),
        ))

fig.update_layout(
    plot_bgcolor="#0f0f1a",
    paper_bgcolor="#0f0f1a",
    font=dict(color="#e2e8f0"),
    xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.1)", range=[0, 1]),
    height=400,
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig, use_container_width=True)

# ── Summary Table ──
st.subheader("All Runs")
display_cols = ["tag", "timestamp", "n_questions"] + [m for m in METRICS if m in df_summary.columns]
st.dataframe(
    df_summary[display_cols].sort_values("timestamp", ascending=False),
    use_container_width=True,
    hide_index=True,
)

# ── Per-run detailed results ──
st.subheader("Detailed Results")
csv_files = sorted(glob.glob("eval/results/*.csv"))

if csv_files:
    selected = st.selectbox("Select run:", options=csv_files, index=len(csv_files) - 1)
    df_detail = pd.read_csv(selected)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Best performing questions**")
        if "faithfulness" in df_detail.columns:
            st.dataframe(
                df_detail.nlargest(3, "faithfulness")[["question", "faithfulness", "answer_relevancy"]],
                use_container_width=True, hide_index=True
            )
    with col2:
        st.markdown("**Worst performing questions** — investigate these")
        if "faithfulness" in df_detail.columns:
            st.dataframe(
                df_detail.nsmallest(3, "faithfulness")[["question", "faithfulness", "answer_relevancy"]],
                use_container_width=True, hide_index=True
            )
else:
    st.info("Run evaluations to see detailed results.")

# ── Improvement Tips ──
st.subheader("What to improve next")
if len(df_summary) >= 2:
    latest = df_summary.iloc[-1]
    worst_metric = min(METRICS, key=lambda m: latest.get(m, 1.0))
    tips = {
        "context_recall": "Low recall → try HyDE retrieval or increase top_k",
        "context_precision": "Low precision → improve reranker or reduce top_k",
        "faithfulness": "Low faithfulness → tighten system prompt, add 'only from context' constraint",
        "answer_relevancy": "Low relevancy → improve query router, check OOS handling",
    }
    st.info(f"📍 Lowest metric: **{worst_metric}** ({latest.get(worst_metric, 0):.3f})\n\n💡 Suggestion: {tips.get(worst_metric, 'Investigate the worst-performing questions above.')}")
