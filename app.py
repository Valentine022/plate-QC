from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="Plate QC",
    page_icon="🧪",
    layout="wide",
)


# --------------------------------------------------
# Access settings
# --------------------------------------------------

ALLOWED_DOMAIN = "evoralis.com"

# Add manually approved Google-account email addresses here.
ALLOWED_EMAILS = {
    "asha.webb@evoralis.com",
    "valentine.patterson@evoralis.com"}


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


def claim_is_true(value) -> bool:
    """Convert a Google/OIDC boolean claim safely."""
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


# --------------------------------------------------
# Authentication
# --------------------------------------------------

if not st.user.is_logged_in:
    st.markdown(
        """
        <style>
          .stApp { background: #e8f7f5; }
          .block-container { max-width: 900px; padding-top: 3rem; }
          .hero {
            background: white;
            border: 1px solid #b9dfd8;
            border-radius: 18px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1.2rem;
          }
          .hero h1 { margin: 0; }
          .hero p { margin: .4rem 0 0 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="hero">
          <h1>96-Well Plate QC</h1>
          <p>This private tool is available to authorised users.</p>
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


email = str(get_user_value("email", "") or "").strip().lower()
email_verified = claim_is_true(get_user_value("email_verified", False))

allowed_emails = {
    address.strip().lower()
    for address in ALLOWED_EMAILS
    if address.strip()
}

is_authorised = (
    email_verified
    and (
        email.endswith(f"@{ALLOWED_DOMAIN}")
        or email in allowed_emails
    )
)

if not is_authorised:
    st.error(
        "Access denied. Your Google account is not authorised to use this application."
    )

    if email:
        st.write(f"Signed-in email: **{email}**")

    if st.button(
        "Sign out",
        key="unauthorised_logout_button",
        use_container_width=True,
    ):
        st.logout()

    st.stop()


# Import only after authentication succeeds.
from report_engine import generate_html


# --------------------------------------------------
# Main interface
# --------------------------------------------------

st.markdown(
    """
    <style>
      .stApp { background: #e8f7f5; }
      .block-container { max-width: 1200px; padding-top: 2rem; }
      .hero {
        background: white;
        border: 1px solid #b9dfd8;
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
      }
      .hero h1 { margin: 0; }
      .hero p { margin: .4rem 0 0 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>96-Well Plate QC</h1>
      <p>Upload a plate CSV, generate the QC report, and download the results.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


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
        value="Sample",
        key="sample_name_input",
    )

    report_title = st.text_input(
        "Report title",
        value="Plate QC",
        key="report_title_input",
    )

    st.caption(
        "QC rules: Z′ < 0 = Fail; 0–0.3 = Acceptable; "
        "Z′ > 0.3 = Pass."
    )

    st.caption(
        "Statistics and hit tables are suppressed only when Z′ is below zero "
        "or cannot be calculated."
    )

    with st.expander("Plate map"):
        st.markdown(
            """
            | Wells | Group |
            |---|---|
            | A1–D1 | Enzyme + Film |
            | E1–H1 | Film |
            | A2–H11 | Samples |
            | A12–D12 | Lysate |
            | E12–H12 | Blank |
            """
        )

    with st.expander("Hit criteria"):
        st.markdown(
            """
            **Standard hits:** raw signal ≥ mean of Film controls E1:H1.

            **High-threshold hits:** raw signal ≥ Film-control mean + 3 × StDev.
            """
        )


uploaded = st.file_uploader(
    "Upload 96-well plate CSV",
    type=["csv"],
    help="The file should contain rows A–H and columns 1–12.",
    key="plate_csv_uploader",
)

if uploaded is None:
    st.info("Upload a CSV file to begin.")
    st.stop()

st.write(f"**Selected file:** {uploaded.name}")


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
                csv_path = temp / Path(uploaded.name).name
                csv_path.write_bytes(uploaded.getvalue())

                html_path = temp / "plate_report.html"

                generate_html(
                    csv_path=csv_path,
                    output_path=html_path,
                    title=report_title,
                    sample_name=sample_name,
                    zscore_threshold=None,
                )

                if not html_path.exists():
                    raise FileNotFoundError("The HTML report was not created.")

                results = {
                    "source_name": uploaded.name,
                    "html": html_path.read_bytes(),
                }

                optional_outputs = {
                    "statistics": html_path.with_name(
                        "plate_report_statistics.csv"
                    ),
                    "standard_hits": html_path.with_name(
                        "plate_report_standard_hits.csv"
                    ),
                    "high_hits": html_path.with_name(
                        "plate_report_high_hits.csv"
                    ),
                }

                for key, file_path in optional_outputs.items():
                    if file_path.exists():
                        results[key] = file_path.read_bytes()

        st.session_state["plate_report_results"] = results

    except Exception as exc:
        st.error(f"Report generation failed: {exc}")


if "plate_report_results" in st.session_state:
    results = st.session_state["plate_report_results"]
    base_name = Path(results["source_name"]).stem

    st.success("Report generated successfully.")

    download_columns = st.columns(
        1 + sum(
            key in results
            for key in ("statistics", "standard_hits", "high_hits")
        )
    )

    column_index = 0

    with download_columns[column_index]:
        st.download_button(
            "Download HTML report",
            data=results["html"],
            file_name=f"{base_name}_plate_report.html",
            mime="text/html",
            key="download_html_button",
            use_container_width=True,
        )
    column_index += 1

    if "statistics" in results:
        with download_columns[column_index]:
            st.download_button(
                "Download statistics",
                data=results["statistics"],
                file_name=f"{base_name}_statistics.csv",
                mime="text/csv",
                key="download_statistics_button",
                use_container_width=True,
            )
        column_index += 1

    if "standard_hits" in results:
        with download_columns[column_index]:
            st.download_button(
                "Download standard hits",
                data=results["standard_hits"],
                file_name=f"{base_name}_standard_hits.csv",
                mime="text/csv",
                key="download_standard_hits_button",
                use_container_width=True,
            )
        column_index += 1

    if "high_hits" in results:
        with download_columns[column_index]:
            st.download_button(
                "Download high hits",
                data=results["high_hits"],
                file_name=f"{base_name}_high_hits.csv",
                mime="text/csv",
                key="download_high_hits_button",
                use_container_width=True,
            )

    if "statistics" not in results:
        st.warning(
            "The plate failed QC with Z′ below zero, so statistics and hit "
            "tables were not generated."
        )

    st.subheader("Report preview")
    st.components.v1.html(
        results["html"].decode("utf-8", errors="replace"),
        height=1100,
        scrolling=True,
    )
