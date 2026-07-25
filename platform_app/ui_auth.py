import streamlit as st

from platform_app.auth import Principal, local_principal, roles_for_email
from platform_app.settings import get_settings


def require_user() -> Principal:
    settings = get_settings()
    is_logged_in = bool(getattr(st.user, "is_logged_in", False))
    if settings.oidc_required and not is_logged_in:
        st.info("Sign in to access research and approval workflows.", icon=":material/lock:")
        if st.button("Sign in", type="primary", icon=":material/login:"):
            st.login()
        st.stop()
    if is_logged_in:
        email = str(st.user.get("email") or st.user.get("preferred_username") or "")
        if not email:
            st.error("The identity provider did not return an email claim.")
            st.stop()
        return Principal(email, roles_for_email(email, settings))
    return local_principal(settings)
