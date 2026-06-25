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

            finding = payload.get("finding", {})
            st.subheader("Finding")
            st.write(finding.get("finding_summary", ""))

            st.subheader("Risk Rating")
            st.write(finding.get("risk_rating", ""))

            st.subheader("Evidence Summary")
            st.write(finding.get("evidence_summary", ""))

            st.subheader("Supporting Documents")
            supporting_documents = finding.get("supporting_documents", [])
            if supporting_documents:
                for document in supporting_documents:
                    st.markdown(f"**Document ID:** {document.get('document_id', '')}")
                    st.markdown(f"**Linked Transaction:** {document.get('linked_transaction', '')}")
                    st.markdown(f"**Evidence Snippet:** {document.get('content_snippet', '')}")
                    st.markdown(f"**Reason Selected:** {document.get('reason_selected', '')}")
                    st.divider()
            else:
                st.write("None")

            st.subheader("Recommendation")
            st.write(finding.get("recommendation", ""))

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Sources")
                st.json(payload.get("sources", []))
            with col2:
                st.subheader("Agents Used")
                st.json(payload.get("agents_used", []))

            st.subheader("Reasoning")
            st.json(payload.get("reasoning", []))

            st.subheader("Final Response")
            st.code(payload.get("final_response", ""), language="text")

            with st.expander("Raw Intent", expanded=False):
                st.json(payload.get("intent", {}))

            with st.expander("Structured Evidence", expanded=False):
                st.json(payload.get("structured_evidence", []))

            with st.expander("Document Evidence", expanded=False):
                sanitized_documents = [
                    {
                        "document_id": document.get("document_id"),
                        "linked_transaction": document.get("linked_transaction"),
                        "reason_selected": document.get("reason_selected"),
                        "content_snippet": document.get("content_snippet"),
                    }
                    for document in payload.get("document_evidence", [])
                ]
                st.json(sanitized_documents)

            with st.expander("Traceability", expanded=False):
                st.json(payload.get("traceability", {}))
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
