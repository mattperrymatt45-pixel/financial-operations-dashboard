"""
Phase 6: AI Assistant
Financial Operations KPI Dashboard

Workflow: User Question -> LLM -> SQL Query -> PostgreSQL -> Data -> AI Summary

Run with:  streamlit run ai_assistant/app.py
"""

import sys
from pathlib import Path

# Allow `from common.db import ...` when running this file directly
sys.path.append(str(Path(__file__).resolve().parents[1]))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# On Streamlit Community Cloud there's no .env file - secrets are set via the
# app's Settings > Secrets UI instead, exposed through st.secrets. Bridge them
# into os.environ so common/db.py and common/llm.py (which read os.getenv)
# work identically whether running locally or deployed.
import os
try:
    for key, value in st.secrets.items():
        os.environ.setdefault(key, str(value))
except Exception:
    pass  # no secrets.toml present (e.g. running locally with just .env) - fine

from common.db import run_readonly_query
from common.llm import question_to_sql, summarize_results

st.set_page_config(page_title="Financial Ops AI Assistant", layout="wide")
st.title("💬 Financial Operations AI Assistant")
st.caption(
    "Ask a business question in plain English. The assistant translates it "
    "to SQL, runs it read-only against PostgreSQL, and summarizes the result."
)

EXAMPLE_QUESTIONS = [
    "Why did settlement failures increase this week?",
    "Show APAC revenue trends over the last 6 months",
    "Which counterparty caused the most failures?",
    "Compare today's KPIs with yesterday",
    "Why did SLA adherence drop?",
    "Which region has the highest profit margin?",
    "Who are the top 5 counterparties by revenue?",
]

if "question" not in st.session_state:
    st.session_state.question = ""

with st.sidebar:
    st.subheader("Example questions")
    for q in EXAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True):
            st.session_state.question = q
    st.divider()
    st.caption(
        "Connects using the read-only `readonly_user` PostgreSQL role - this "
        "assistant can never write, update, or delete data, no matter what "
        "SQL the model generates. Run `ai_assistant/setup_readonly_role.sql` "
        "once if you haven't already."
    )

question = st.text_input(
    "Ask a question about the business",
    value=st.session_state.question,
    placeholder="e.g. Which region has the highest failure rate?",
)

ask = st.button("Ask", type="primary")

if ask and question.strip():
    try:
        with st.spinner("Translating your question to SQL..."):
            sql = question_to_sql(question)
    except Exception as e:
        st.error(f"Couldn't reach the LLM: {e}")
        st.stop()

    st.markdown("**Generated SQL**")
    st.code(sql, language="sql")

    try:
        with st.spinner("Running query..."):
            df = run_readonly_query(sql)
    except Exception as e:
        st.error(f"Query failed or was blocked: {e}")
        st.stop()

    if df.empty:
        st.warning("The query ran successfully but returned no rows.")
    else:
        st.markdown("**Results**")
        st.dataframe(df, use_container_width=True)

        # Auto-chart: line chart if there's a date-like column, else bar chart
        # if there's one categorical + one numeric column.
        date_cols = [c for c in df.columns if "date" in c.lower() or "month" in c.lower()]
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if date_cols and numeric_cols:
            chart_df = df.set_index(date_cols[0])[numeric_cols]
            st.line_chart(chart_df)
        elif len(df.columns) >= 2 and numeric_cols:
            label_col = next((c for c in df.columns if c not in numeric_cols), None)
            if label_col:
                st.bar_chart(df.set_index(label_col)[numeric_cols])

        try:
            with st.spinner("Generating summary..."):
                summary = summarize_results(question, df)
            st.markdown("### AI Summary")
            st.write(summary)
        except Exception as e:
            st.warning(f"Got results, but summary generation failed: {e}")

elif ask:
    st.warning("Type a question first.")
