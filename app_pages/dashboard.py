import streamlit as st

from platform_app.workflow import HUMAN_GATES, STAGE_ORDER

with st.container(horizontal=True):
    st.metric("Active research runs", "0", border=True)
    st.metric("Awaiting approval", "0", border=True)
    st.metric("Verified sources", "0", border=True)
    st.metric("Published articles", "0", border=True)

with st.container(border=True):
    st.subheader("Workflow readiness")
    rows = [
        {
            "order": index + 1,
            "stage": stage.value.replace("_", " ").capitalize(),
            "human gate": stage in HUMAN_GATES,
        }
        for index, stage in enumerate(STAGE_ORDER)
    ]
    for row in rows:
        gate = "Human approval" if row["human gate"] else "Automated stage"
        st.write(f"{row['order']}. **{row['stage']}** - {gate}")

st.info("Connect PostgreSQL and start the worker to display live runs.", icon=":material/info:")
