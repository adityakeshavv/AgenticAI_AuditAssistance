from __future__ import annotations

import os

import requests
import streamlit as st


API_BASE_URL = os.getenv("AUDIT_API_BASE_URL", "http://localhost:8000")


st.set_page_config(page_title="Audit Assistant Demo", layout="wide")
st.title("Audit Assistant Demo")

with st.sidebar:
    st.header("Demo Controls")
    api_base_url = st.text_input("API Base URL", value=API_BASE_URL)
    page = st.number_input("Page", min_value=1, value=1, step=1)
    page_size = st.number_input("Page Size", min_value=1, max_value=500, value=10, step=1)

query = st.text_area("User Query", height=120, placeholder="e.g. show flagged transactions and related documents")

if st.button("Run Audit Query", type="primary"):
    if not query.strip():
        st.warning("Please enter a query.")
    else:
        try:
            response = requests.post(
                f"{api_base_url.rstrip('/')}/audit/query",
                json={"query": query, "page": int(page), "page_size": int(page_size)},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()

            st.subheader("Final Response")
            st.write(payload.get("final_response", ""))

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Extracted Intent")
                st.json(payload.get("intent", {}))
            with col2:
                st.subheader("Agents Invoked")
                st.json(payload.get("agents_used", []))

            st.subheader("Structured Evidence")
            st.json(payload.get("structured_evidence", []))

            st.subheader("Document Evidence")
            st.json(payload.get("document_evidence", []))

            st.subheader("Sources Used")
            st.json(payload.get("sources", []))

            st.subheader("Reasoning Path")
            st.json(payload.get("reasoning", []))

            st.subheader("Traceability")
            st.json(payload.get("traceability", {}))
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
