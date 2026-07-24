import streamlit as st

query = st.text_input("Search literature and governed clinical concepts", placeholder="e.g. interoception and diagnostic masking")
scope = st.pills(
    "Knowledge scope",
    ["Literature", "Clinical aggregates", "Research artifacts"],
    selection_mode="multi",
    default=["Literature"],
)

if query:
    st.info(
        "Hybrid retrieval (metadata filters + full text + pgvector) will return citation-backed passages here. "
        "Clinical results must be aggregate/de-identified and policy-authorized.",
        icon=":material/search:",
    )
else:
    st.caption("Enter a query to explore the governed RAG index.")
