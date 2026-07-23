from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="NC63 + Film Plate QC",
    page_icon="🧪",
    layout="wide",
)


# --------------------------------------------------
# Access settings
# --------------------------------------------------

ALLOWED_DOMAIN = "evoralis.com"

# Add manually approved email addresses here.
# These can be Evoralis accounts or approved external accounts.
ALLOWED_EMAILS = {
    "valentine.patterson@evoralis.com",
    "asha.webb@evoralis.com",
    # "external.user@gmail.com",
}


def get_user_value(name: str, default=None):
    """Read a claim from st.user safely."""
    try:
        value = getattr(st.user, name)
        if value is not None:
            return value
    except Exception:
        pass

    try:
        return st.user.get(name, default)
    except Exception:
        return default


# --------------------------------------------------
# Authentication
# --------------------------------------------------

if not st.user.is_logged_in:
    st.markdown(
        """
        <style>
          .stApp {
            background: #e8f7f5;
          }

          .block-container {
            max-width: 900px;
            padding-top: 3rem;
          }

          .hero {
            background: white;
            border: 1px solid #b9dfd8;
            border-radius: 18px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1.2rem;
          }

          .hero h1 {
            margin: 0;
          }

          .hero p {
            margin: .4rem 0 0 0;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="hero">
          <h1>NC63 + Film 96-Well Plate QC</h1>
          <p>
            This private tool is available to authorised users.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info("Sign in with Google to continue.")

    if st.button(
        "Sign in with Google",
        key="google_login_button",
        type="primary",
        use_container_width=True,
    ):
        st.login()

    st.stop()


# --------------------------------------------------
# Read user details
# --------------------------------------------------

email = str(
    get_user_value("email", "") or ""
).strip().lower()

email_verified_value = get_user_value(
    "email_verified",
    False,
)

# Google may return this as a boolean or a string.
if isinstance(email_verified_value, str):
    email_verified = (
        email_verified_value.strip().lower() == "true"
    )
else:
    email_verified = bool(email_verified_value)


# --------------------------------------------------
# Authorisation
# --------------------------------------------------

is_organisation_user = email.endswith(
    f"@{ALLOWED_DOMAIN}"
)

is_manually_approved = email in {
    allowed_email.strip().lower()
    for allowed_email in ALLOWED_EMAILS
}

is_authorised = (
    email_verified
    and (
        is_organisation_user
        or is_manually_approved
    )
)

if not is_authorised:
    st.error(
        "Access denied. Your Google account is not "
        "authorised to use this application."
    )

    if email:
        st.write(f"Signed-in email: **{email}**")

    st.caption(
        "Ask the app administrator to add your email "
        "address to the approved-user list."
    )

    if st.button(
        "Sign out",
        key="unauthorised_logout_button",
        use_container_width=True,
    ):
        st.logout()

    st.stop()


# Import the report engine only after authentication succeeds.
from report_engine import generate_html


# --------------------------------------------------
# Main application styling
# --------------------------------------------------

st.markdown(
    """
    <style>
      .stApp {
        background: #e8f7f5;
      }

      .block-container {
        max-width: 1200px;
        padding-top: 2rem;
      }

      .hero {
        background: white;
        border: 1px solid #b9dfd8;
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
      }

      .hero h1 {
        margin: 0;
      }

      .hero p {
        margin: .4rem 0 0 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="hero">
      <h1>NC63 + Film 96-Well Plate QC</h1>
      <p>
        Upload a plate CSV, generate the QC report,
        and download the results.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# Sidebar
# --------------------------------------------------

with st.sidebar:
    st.success(f"Signed in as {email}")

    if st.button(
        "Sign out",
        key="authorised_logout_button",
        use_container_width=True,
    ):
        st.logout()

    st.divider()
    st.header("Report settings")

    sample_name = st.text_input(
        "Sample name",
        value="Unknown Sample",
        key="sample_name_input",
    )

    report_title = st.text_input(
        "Report title",
        value="NC63 + Film Plate QC",
        key="report_title_input",
    )

    custom_threshold = st.checkbox(
        "Use custom plate Z-score threshold",
        key="custom_threshold_checkbox",
    )

    threshold = None

    if custom_threshold:
        threshold = st.number_input(
            "Plate Z-score threshold",
            value=2.000,
            step=0.100,
            format="%.3f",
            key="threshold_input",
        )

    st.caption(
        "Default hit threshold: the highest whole-plate "
        "Z-score among the B control wells E12:H12."
    )

    with st.expander("Plate map"):
        st.markdown(
            """
            | Wells | Group |
            |---|---|
            | A1–D1 | NC63 + Film |
            | E1–H1 | Film |
            | A2–H11 | C |
            | A12–D12 | NC63 Lysate |
            | E12–H12 | B |
            """
        )

    st.caption(
        "Z′ comparison: Film versus NC63 + Film."
    )


# --------------------------------------------------
# File upload
# --------------------------------------------------

uploaded = st.file_uploader(
    "Upload 96-well plate CSV",
    type=["csv"],
    help=(
        "The file should contain rows A–H "
        "and columns 1–12."
    ),
    key="plate_csv_uploader",
)

if uploaded is None:
    st.info("Upload a CSV file to begin.")
    st.stop()


st.write(f"**Selected file:** {uploaded.name}")


# --------------------------------------------------
# Generate report
# --------------------------------------------------

if st.button(
    "Generate QC report",
    key="generate_report_button",
    type="primary",
    use_container_width=True,
):
    try:
        with st.spinner("Generating report..."):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)

                safe_filename = Path(
                    uploaded.name
                ).name

                csv_path = temp / safe_filename
                csv_path.write_bytes(
                    uploaded.getvalue()
                )

                html_path = (
                    temp / "plate_report.html"
                )

                generate_html(
                    csv_path=csv_path,
                    output_path=html_path,
                    title=report_title,
                    sample_name=sample_name,
                    zscore_threshold=threshold,
                )

                statistics_path = (
                    html_path.with_name(
                        "plate_report_statistics.csv"
                    )
                )

                hits_path = (
                    html_path.with_name(
                        "plate_report_passing_wells.csv"
                    )
                )

                if not html_path.exists():
                    raise FileNotFoundError(
                        "The HTML report was not created."
                    )

                if not statistics_path.exists():
                    raise FileNotFoundError(
                        "The statistics CSV was not created."
                    )

                if not hits_path.exists():
                    raise FileNotFoundError(
                        "The candidate-hits CSV "
                        "was not created."
                    )

                html_bytes = html_path.read_bytes()
                statistics_bytes = (
                    statistics_path.read_bytes()
                )
                hits_bytes = hits_path.read_bytes()

        st.session_state["plate_report_results"] = {
            "source_name": uploaded.name,
            "html": html_bytes,
            "statistics": statistics_bytes,
            "hits": hits_bytes,
        }

    except Exception as exc:
        st.error(
            f"Report generation failed: {exc}"
        )


# --------------------------------------------------
# Display stored results
# --------------------------------------------------

if "plate_report_results" in st.session_state:
    results = st.session_state[
        "plate_report_results"
    ]

    st.success(
        "Report generated successfully."
    )

    base_name = Path(
        results["source_name"]
    ).stem

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "Download HTML report",
            data=results["html"],
            file_name=(
                f"{base_name}_plate_report.html"
            ),
            mime="text/html",
            key="download_html_button",
            use_container_width=True,
        )

    with col2:
        st.download_button(
            "Download statistics",
            data=results["statistics"],
            file_name=(
                f"{base_name}_statistics.csv"
            ),
            mime="text/csv",
            key="download_statistics_button",
            use_container_width=True,
        )

    with col3:
        st.download_button(
            "Download candidate hits",
            data=results["hits"],
            file_name=(
                f"{base_name}_candidate_hits.csv"
            ),
            mime="text/csv",
            key="download_hits_button",
            use_container_width=True,
        )

    st.subheader("Report preview")

    st.components.v1.html(
        results["html"].decode(
            "utf-8",
            errors="replace",
        ),
        height=1100,
        scrolling=True,
    )
