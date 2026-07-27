from __future__ import annotations
import base64
import inspect
import re
import tempfile
from datetime import datetime
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
    "valentine.patterson@evoralis.com",
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


def claim_is_true(value) -> bool:
    """Convert a Google/OIDC boolean claim safely."""
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def get_logo_html() -> str:
    app_directory = Path(__file__).resolve().parent

    possible_logos = [
        app_directory / "EvoralisLogo.png",
        app_directory / "cropped-cropped-0_Evoralis_logo_for-emails_final_v2.png",
    ]

    for logo_path in possible_logos:
        if logo_path.exists():
            encoded_logo = base64.b64encode(
                logo_path.read_bytes()
            ).decode("ascii")

            return (
                f'<img class="evoralis-logo" '
                f'src="data:image/png;base64,{encoded_logo}" '
                f'alt="Evoralis">'
            )

    return ""

# --------------------------------------------------
# Authentication
# --------------------------------------------------
logo_html = get_logo_html()
if not st.user.is_logged_in:
    st.markdown(
        """
        <style>
          .stApp { background: #e8f7f5; }
          .block-container { max-width: 900px; padding-top: 3rem; }
    .hero {
      display: flex;
      align-items: center;
      gap: 1.4rem;
      background: white;
      border: 1px solid #b9dfd8;
      border-radius: 18px;
      padding: 1.4rem 1.6rem;
      margin-bottom: 1.2rem;
    }
    
    .hero-text {
      flex: 1;
    }
    
    .hero h1 {
      margin: 0;
    }
    
    .hero p {
      margin: .4rem 0 0 0;
    }
    
    .evoralis-logo {
      width: auto;
      height: 40px;
      max-width: 220px;
      object-fit: contain;
    }
          .hero h1 { margin: 0; }
          .hero p { margin: .4rem 0 0 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="hero">
          {logo_html}
          <div class="hero-text">
            <h1>96-Well Plate QC</h1>
            <p>This private tool is available to authorised users.</p>
          </div>
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
            display: flex;
            align-items: center;
            gap: 1rem;
            background: white;
            border: 1px solid #b9dfd8;
            border-radius: 18px;
            padding: 1.2rem 1.6rem;
            margin-bottom: 1.5rem;
        }
        
        .hero-text {
            flex: 1;
        }
        
        .hero h1 {
            margin: 0;
            font-size: 2.2rem;
            font-weight: 700;
        }
        
        .hero p {
            margin: 0.35rem 0 0 0;
            font-size: 1.05rem;
            color: #555;
        }
        
        .evoralis-logo {
            height: 48px;
            width: auto;
            flex-shrink: 0;
        }
      .hero h1 { margin: 0; }
      .hero p { margin: .4rem 0 0 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="hero">
      {logo_html}
      <div class="hero-text">
        <h1>96-Well Plate QC</h1>
        <p>
          Upload a plate CSV, generate the QC report, and download the results.
          Upload the finished report to
          <a href="https://drive.google.com/drive/folders/10qL_JRWw_tyJOTAfTY__K-m2x9NE6ALR?usp=sharing" target="_blank" rel="noopener noreferrer">Google Drive</a>.
        </p>
      </div>
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
    
    user_name = st.text_input(
        "User",
        value="",
        key="user_name_input",
    )
    
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
        "Statistics and hit tables are not shown when Z′ is below zero "
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
            | E12–H12 | Buffer |
            """
        )

        all_wells = [f"{row}{column}" for row in "ABCDEFGH" for column in range(1, 13)]

        enzyme_film_wells = st.multiselect(
            "Enzyme + Film wells",
            options=all_wells,
            default=["A1", "B1", "C1", "D1"],
            key="enzyme_film_wells",
        )

        film_wells = st.multiselect(
            "Film wells",
            options=all_wells,
            default=["E1", "F1", "G1", "H1"],
            key="film_wells",
        )

        lysate_wells = st.multiselect(
            "Lysate wells",
            options=all_wells,
            default=["A12", "B12", "C12", "D12"],
            key="lysate_wells",
        )

        buffer_wells = st.multiselect(
            "Buffer wells",
            options=all_wells,
            default=["E12", "F12", "G12", "H12"],
            key="buffer_wells",
        )

    with st.expander("Hit criteria"):
        st.markdown(
            """
            **Standard hits:** raw signal ≥ mean of Film controls A1:D1.

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
        selected_control_wells = (
            enzyme_film_wells
            + film_wells
            + lysate_wells
            + buffer_wells
        )

        if any(
            not wells
            for wells in (
                enzyme_film_wells,
                film_wells,
                lysate_wells,
                buffer_wells,
            )
        ):
            raise ValueError("Each control group must contain at least one well.")

        if len(selected_control_wells) != len(set(selected_control_wells)):
            raise ValueError("A well cannot be selected in more than one group.")

        sample_wells = [
            well for well in all_wells
            if well not in set(selected_control_wells)
        ]

        def convert_wells(wells: list[str]) -> list[tuple[str, str]]:
            return [(well[0], well[1:]) for well in wells]

        plate_groups = {
            "Enzyme + Film": convert_wells(enzyme_film_wells),
            "Film": convert_wells(film_wells),
            "Samples": convert_wells(sample_wells),
            "Lysate": convert_wells(lysate_wells),
            "Buffer": convert_wells(buffer_wells),
        }

        with st.spinner("Generating report..."):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)
                csv_path = temp / Path(uploaded.name).name
                csv_path.write_bytes(uploaded.getvalue())

                html_path = temp / "plate_report.html"

                report_kwargs = {
                    "csv_path": csv_path,
                    "output_path": html_path,
                    "title": report_title,
                    "sample_name": sample_name,
                    "zscore_threshold": None,
                    "plate_groups": plate_groups,
                }

                # Pass the user name when the installed report engine supports it.
                # This keeps the app compatible with older report_engine versions.
                if "user_name" in inspect.signature(generate_html).parameters:
                    report_kwargs["user_name"] = user_name.strip()

                generate_html(**report_kwargs)

                if not html_path.exists():
                    raise FileNotFoundError("The HTML report was not created.")

                report_html = html_path.read_text(encoding="utf-8", errors="replace")

                # Add the user name to the report even when using an older engine
                # that does not yet accept a user_name argument.
                clean_user_name = user_name.strip()
                if clean_user_name and "user_name" not in inspect.signature(generate_html).parameters:
                    user_line = (
                        '<p class="report-user"><strong>Prepared by:</strong> '
                        + clean_user_name.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        + "</p>"
                    )
                    body_match = re.search(r"<body[^>]*>", report_html, flags=re.IGNORECASE)
                    if body_match:
                        insert_at = body_match.end()
                        report_html = report_html[:insert_at] + user_line + report_html[insert_at:]
                    else:
                        report_html = user_line + report_html

                results = {
                    "source_name": uploaded.name,
                    "sample_name": sample_name,
                    "generated_date": datetime.now().strftime("%Y-%m-%d"),
                    "html": report_html.encode("utf-8"),
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

    def safe_filename_part(value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
        cleaned = cleaned.strip("._-")
        return cleaned or fallback

    safe_sample = safe_filename_part(results.get("sample_name", ""), "sample")
    report_date = results.get("generated_date", datetime.now().strftime("%Y-%m-%d"))
    report_prefix = f"{report_date}_{safe_sample}"

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
            file_name=f"{report_prefix}_plate_report.html",
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
                file_name=f"{report_prefix}_statistics.csv",
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
                file_name=f"{report_prefix}_standard_hits.csv",
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
                file_name=f"{report_prefix}_high_hits.csv",
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
