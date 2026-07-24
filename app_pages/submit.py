import streamlit as st

with st.form("hypothesis_submission", border=True):
    title = st.text_input("Working title", placeholder="A concise research question")
    hypothesis = st.text_area(
        "Raw hypothesis",
        height=220,
        placeholder="Describe the observation, proposed mechanism, population, and expected relationship.",
    )
    data_zone = st.segmented_control(
        "Permitted evidence",
        ["Literature only", "Literature + approved de-identified clinical cohort"],
        default="Literature only",
    )
    submitted = st.form_submit_button("Submit for formalization", type="primary")

if submitted:
    if len(title.strip()) < 3 or len(hypothesis.strip()) < 20:
        st.error("Add a title and a hypothesis of at least 20 characters.")
    else:
        st.success("Submission validated. API persistence and worker dispatch are the next integration step.")
        st.json({"title": title, "hypothesis": hypothesis, "evidence_scope": data_zone})
