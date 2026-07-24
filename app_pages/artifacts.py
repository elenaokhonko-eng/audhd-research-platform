import streamlit as st

kind = st.segmented_control(
    "Artifact type",
    ["Scientific report", "PDF", "Substack article", "Charts", "Images"],
    default="Scientific report",
)
st.info(f"No {kind.lower()} artifacts have been generated yet.", icon=":material/article:")
