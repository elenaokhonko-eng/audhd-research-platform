import httpx
import streamlit as st

from platform_app.settings import get_settings
from platform_app.workflow import HUMAN_GATES, WorkflowStage

roles = set(st.session_state.get("principal_roles", []))
if not roles.intersection({"reviewer", "admin", "publisher"}):
    st.error("Your account does not have an approval role.")
    st.stop()

settings = get_settings()
headers = {"X-Authenticated-Email": st.session_state["principal_email"]}

try:
    runs_response = httpx.get(f"{settings.api_base_url}/runs", headers=headers, timeout=15)
    runs_response.raise_for_status()
    waiting = [item for item in runs_response.json() if WorkflowStage(item["stage"]) in HUMAN_GATES]
except httpx.HTTPError as error:
    st.error(f"Could not load approvals. Ensure the API is running. {error}")
    st.stop()

if not waiting:
    st.warning("No artifacts are currently awaiting review.", icon=":material/pending_actions:")
    st.stop()

labels = {f"{item['title']} - {item['stage']}": item for item in waiting}
selected_label = st.selectbox("Research run", labels)
selected = labels[selected_label]

artifacts_response = httpx.get(f"{settings.api_base_url}/runs/{selected['id']}/artifacts", headers=headers, timeout=15)
artifacts_response.raise_for_status()
artifacts = artifacts_response.json()
if not artifacts:
    st.warning("This approval gate has no stored artifact.")
    st.stop()

artifact_labels = {f"{item['kind']} ({item['sha256'][:10]})": item for item in artifacts}
artifact_label = st.selectbox("Artifact snapshot", artifact_labels)
artifact = artifact_labels[artifact_label]
content_response = httpx.get(f"{settings.api_base_url}/artifacts/{artifact['id']}/content", headers=headers, timeout=30)
content_response.raise_for_status()
content = content_response.content

if artifact["kind"].endswith(".pdf"):
    st.pdf(content, height=700)
elif artifact["kind"].endswith((".md", ".json")):
    text = content.decode("utf-8")
    st.code(text, language="markdown" if artifact["kind"].endswith(".md") else "json")
else:
    st.download_button("Download artifact", content, file_name=artifact["kind"])

with st.form("approval_decision", border=True):
    comment = st.text_area("Review comment")
    confirm = st.checkbox("I reviewed this exact artifact snapshot and approve it for the next stage.")
    approve = st.form_submit_button("Approve snapshot", type="primary", disabled=not confirm)

if approve:
    gate = selected["stage"]
    response = httpx.post(
        f"{settings.api_base_url}/runs/{selected['id']}/approve/{gate}",
        json={"snapshot": content.decode("utf-8", errors="replace"), "comment": comment or None},
        headers=headers,
        timeout=15,
    )
    if response.is_success:
        st.success(f"Approved immutable snapshot {response.json()['snapshot_hash'][:12]}.")
    else:
        st.error(f"Approval failed: {response.text}")
