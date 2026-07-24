import streamlit as st
import httpx

from platform_app.settings import get_settings

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
        settings = get_settings()
        headers = {"X-Authenticated-Email": st.session_state["principal_email"]}
        try:
            response = httpx.post(
                f"{settings.api_base_url}/runs",
                json={"title": title, "hypothesis": hypothesis},
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            created = response.json()
            st.session_state["selected_run_id"] = created["id"]
            st.success(f"Research run created: {created['id']}")
            st.caption(f"Evidence scope: {data_zone}")
        except (httpx.HTTPError, KeyError) as error:
            st.error(f"Could not create the research run. Ensure the API and PostgreSQL are running. {error}")
