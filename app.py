import streamlit as st



st.set_page_config(

    page_title="96-Well Plate QC",

    page_icon="🧪",

    layout="centered",

)



ALLOWED_DOMAIN = "evoralis.com"





def user_value(name: str, default=None):

    try:

        return getattr(st.user, name)

    except Exception:

        try:

            return st.user.get(name, default)

        except Exception:

            return default





st.title("96-Well Plate QC Report Generator")



if not st.user.is_logged_in:

    st.caption("This private tool is restricted to Evoralis Google accounts.")

    st.info("Sign in with an @evoralis.com Google account to continue.")



    if st.button(

        "Sign in with Google",

        key="google_login_button",

        type="primary",

        use_container_width=True,

    ):

        st.login()

    st.stop()



email = str(user_value("email", "") or "").strip().lower()

hosted_domain = str(user_value("hd", "") or "").strip().lower()

email_verified = user_value("email_verified", False)



if not (

    email.endswith(f"@{ALLOWED_DOMAIN}")

    and hosted_domain == ALLOWED_DOMAIN

    and email_verified is True

):

    st.error("Access denied. Please use a verified @evoralis.com Google account.")

    if st.button(

        "Sign out",

        key="unauthorized_logout_button",

        use_container_width=True,

    ):

        st.logout()

    st.stop()



st.success(f"Signed in successfully as {email}")



if st.button(

    "Sign out",

    key="authorized_logout_button",

    use_container_width=True,

):

    st.logout()



st.info(

    "Authentication is working. The report uploader can now be added back safely."

)
