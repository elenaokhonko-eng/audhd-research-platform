import streamlit as st

st.warning("No artifacts are currently awaiting review.", icon=":material/pending_actions:")

with st.container(border=True):
    st.subheader("Approval policy")
    st.write("Every approval is tied to an immutable artifact hash, reviewer identity, timestamp, and comment.")
    st.write("Publishing cannot begin unless the exact Substack draft and visual set have final approval.")
