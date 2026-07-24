import streamlit as st

from platform_app.ui_auth import require_user

st.set_page_config(page_title="AuDHD research platform", page_icon=":material/science:", layout="wide")
st.session_state.setdefault("selected_run_id", None)
principal = require_user()
st.session_state["principal_email"] = principal.email
st.session_state["principal_roles"] = sorted(principal.roles)

pages = {
    "Research": [
        st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:"),
        st.Page("app_pages/submit.py", title="Submit hypothesis", icon=":material/science:"),
        st.Page("app_pages/knowledge.py", title="Knowledge explorer", icon=":material/search:"),
    ],
    "Review": [
        st.Page("app_pages/approvals.py", title="Approvals", icon=":material/approval:"),
        st.Page("app_pages/artifacts.py", title="Reports and visuals", icon=":material/article:"),
    ],
}

navigation = st.navigation(pages, position="sidebar")
with st.sidebar:
    st.caption(f"Signed in as {principal.email}")
st.title(f"{navigation.icon} {navigation.title}")
navigation.run()
