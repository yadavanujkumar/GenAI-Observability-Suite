import json
from pathlib import Path

import pandas as pd
import streamlit as st

LOG_PATH = Path("data/interactions.jsonl")


def load_records() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    rows = []
    with LOG_PATH.open("r", encoding="utf-8") as fp:
        for line in fp:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="LLM Observability", layout="wide")
    st.title("LLM Observability & Governance Dashboard")

    df = load_records()
    if df.empty:
        st.info("No interaction logs yet. Send a few chat requests to populate data.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Interactions", len(df))
    col2.metric("Avg Latency (ms)", f"{df['latency_ms'].mean():.1f}")
    col3.metric("Error Rate", f"{(1 - df['hallucination_ok'].mean()) * 100:.1f}%")
    feedback = df[df["feedback"].notna()] if "feedback" in df else pd.DataFrame()
    if not feedback.empty:
        col4.metric("Net Feedback", feedback["feedback"].sum())
    else:
        col4.metric("Net Feedback", "0")

    st.subheader("Recent Interactions")
    st.dataframe(df.sort_values("ts", ascending=False).head(50)[[
        "trace_id",
        "user_id",
        "model",
        "latency_ms",
        "cached",
        "hallucination_ok",
        "prompt",
        "response",
    ]])

    st.subheader("Latency Distribution")
    st.bar_chart(df["latency_ms"].clip(upper=df["latency_ms"].quantile(0.95)))

    if "token_usage" in df:
        st.subheader("Token Usage")
        st.area_chart(df["token_usage"])


if __name__ == "__main__":
    main()
