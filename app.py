from __future__ import annotations
import base64
import inspect
import io
import re
import tempfile
import zipfile
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
ALLOWED_EMAILS = {"daniel.kaute@evoralis.com",
                  "mariana.rangel@evoralis.com",
                  "josephin.holstein@evoralis.com",
                  "tom.ogden@evoralis.com",
                  "devanshi.singh@evoralis.com",
                  "simona.pilotto@evoralis.com",
                  "elizabeth.nganga@evoralis.com",
                  "marcus.bage@evoralis.com",
                  "adam.roberts@evoralis.com",
                  "david.miranda@evoralis.com",
                  "elizabeth.nganga@evoralis.com",
                  "dylan.george@evoralis.com",
                  "michaela.buerdsell@evoralis.com",
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
          header[data-testid="stHeader"] { display: none; }
      div[data-testid="stToolbar"] { display: none; }
      .block-container { max-width: 900px; padding-top: 1rem; }
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
      height: 80px;
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
      header[data-testid="stHeader"] { display: none; }
      div[data-testid="stToolbar"] { display: none; }
      .block-container { max-width: 1200px; padding-top: 1rem; }
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
            height: 80px;
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


uploaded_files = st.file_uploader(
    "Upload one or more 96-well plate CSVs",
    type=["csv"],
    accept_multiple_files=True,
    help="Each file should contain rows A–H and columns 1–12.",
    key="plate_csv_uploader",
)

if not uploaded_files:
    st.info("Upload one or more CSV files to begin.")
    st.stop()

st.write(f"**Selected plates:** {len(uploaded_files)}")
st.caption(", ".join(uploaded.name for uploaded in uploaded_files))


def safe_filename_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or fallback


def add_user_to_report(report_html: str, clean_user_name: str) -> str:
    """Add the preparer's name when an older report engine does not print it."""
    if not clean_user_name:
        return report_html

    escaped_user_name = (
        clean_user_name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    if escaped_user_name in report_html:
        return report_html

    user_line = (
        '<p class="report-user"><strong>Prepared by:</strong> '
        + escaped_user_name
        + "</p>"
    )
    heading_match = re.search(r"</h1>", report_html, flags=re.IGNORECASE)
    if heading_match:
        insert_at = heading_match.end()
        return report_html[:insert_at] + user_line + report_html[insert_at:]

    body_match = re.search(r"<body[^>]*>", report_html, flags=re.IGNORECASE)
    if body_match:
        insert_at = body_match.end()
        return report_html[:insert_at] + user_line + report_html[insert_at:]

    return user_line + report_html


if st.button(
    "Generate QC reports",
    key="generate_report_button",
    type="primary",
    use_container_width=True,
):
    try:
        selected_control_wells = (
            enzyme_film_wells + film_wells + lysate_wells + buffer_wells
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

        selected_control_set = set(selected_control_wells)
        sample_wells = [well for well in all_wells if well not in selected_control_set]

        def convert_wells(wells: list[str]) -> list[tuple[str, str]]:
            return [(well[0], well[1:]) for well in wells]

        plate_groups = {
            "Enzyme + Film": convert_wells(enzyme_film_wells),
            "Film": convert_wells(film_wells),
            "Samples": convert_wells(sample_wells),
            "Lysate": convert_wells(lysate_wells),
            "Buffer": convert_wells(buffer_wells),
        }

        engine_parameters = inspect.signature(generate_html).parameters
        generated_date = datetime.now().strftime("%Y-%m-%d")
        all_results = []
        generation_errors = []
        progress = st.progress(0, text="Preparing plate reports...")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)

            for index, uploaded in enumerate(uploaded_files, start=1):
                progress.progress(
                    (index - 1) / len(uploaded_files),
                    text=f"Analysing {uploaded.name} ({index}/{len(uploaded_files)})...",
                )

                try:
                    plate_stem = safe_filename_part(Path(uploaded.name).stem, f"plate_{index}")
                    plate_dir = temp / f"{index:03d}_{plate_stem}"
                    plate_dir.mkdir(parents=True, exist_ok=True)

                    csv_path = plate_dir / Path(uploaded.name).name
                    csv_path.write_bytes(uploaded.getvalue())
                    html_path = plate_dir / "plate_report.html"

                    display_sample_name = sample_name.strip()
                    if len(uploaded_files) > 1:
                        display_sample_name = (
                            f"{display_sample_name} – {Path(uploaded.name).stem}"
                            if display_sample_name
                            else Path(uploaded.name).stem
                        )
                    display_sample_name = display_sample_name or "Sample"

                    report_kwargs = {
                        "csv_path": csv_path,
                        "output_path": html_path,
                        "title": display_sample_name,
                        "sample_name": display_sample_name,
                        "zscore_threshold": None,
                        "plate_groups": plate_groups,
                    }

                    optional_engine_settings = {
                        "user_name": user_name.strip(),
                        "section_order": [
                            "qc_assessment",
                            "zscore",
                            "hits",
                            "zscore_heatmap",
                            "raw_heatmap",
                            "group_statistics",
                            "group_averages",
                        ],
                        "combine_hit_tables": True,
                        "group_average_groups": ["Enzyme + Film", "Lysate"],
                    }
                    for setting_name, setting_value in optional_engine_settings.items():
                        if setting_name in engine_parameters:
                            report_kwargs[setting_name] = setting_value

                    generate_html(**report_kwargs)
                    if not html_path.exists():
                        raise FileNotFoundError("The HTML report was not created.")

                    report_html = add_user_to_report(
                        html_path.read_text(encoding="utf-8", errors="replace"),
                        user_name.strip(),
                    )

                    result = {
                        "source_name": uploaded.name,
                        "sample_name": display_sample_name,
                        "generated_date": generated_date,
                        "html": report_html.encode("utf-8"),
                    }

                    optional_outputs = {
                        "statistics": html_path.with_name("plate_report_statistics.csv"),
                        "standard_hits": html_path.with_name("plate_report_standard_hits.csv"),
                        "high_hits": html_path.with_name("plate_report_high_hits.csv"),
                    }
                    for key, file_path in optional_outputs.items():
                        if file_path.exists():
                            result[key] = file_path.read_bytes()

                    all_results.append(result)
                except Exception as plate_exc:
                    generation_errors.append(
                        {"source_name": uploaded.name, "error": str(plate_exc)}
                    )

            progress.progress(1.0, text="Plate analysis complete.")

        if not all_results:
            error_details = "; ".join(
                f"{item['source_name']}: {item['error']}" for item in generation_errors
            )
            raise RuntimeError(f"No reports were generated. {error_details}")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for result in all_results:
                plate_name = safe_filename_part(
                    Path(result["source_name"]).stem, "plate"
                )
                sample_part = safe_filename_part(result["sample_name"], plate_name)
                prefix = f"{result['generated_date']}_{sample_part}"
                folder = f"{plate_name}/"
                archive.writestr(folder + f"{prefix}_plate_report.html", result["html"])
                for key, suffix in (
                    ("statistics", "statistics.csv"),
                    ("standard_hits", "standard_hits.csv"),
                    ("high_hits", "high_hits.csv"),
                ):
                    if key in result:
                        archive.writestr(folder + f"{prefix}_{suffix}", result[key])

        st.session_state["plate_report_results"] = all_results
        st.session_state["plate_report_errors"] = generation_errors
        st.session_state["plate_report_zip"] = zip_buffer.getvalue()

    except Exception as exc:
        st.error(f"Report generation failed: {exc}")


if "plate_report_results" in st.session_state:
    all_results = st.session_state["plate_report_results"]
    generation_errors = st.session_state.get("plate_report_errors", [])

    st.success(f"Generated {len(all_results)} plate report(s) successfully.")

    if generation_errors:
        st.warning(f"{len(generation_errors)} plate(s) could not be analysed.")
        for item in generation_errors:
            st.error(f"{item['source_name']}: {item['error']}")

    st.download_button(
        "Download all plate results (ZIP)",
        data=st.session_state["plate_report_zip"],
        file_name=(
            f"{datetime.now().strftime('%Y-%m-%d')}_"
            f"{safe_filename_part(sample_name, 'plates')}_plate_reports.zip"
        ),
        mime="application/zip",
        key="download_all_reports_button",
        use_container_width=True,
    )

    st.subheader("Individual plate results")
    for result_index, results in enumerate(all_results):
        plate_label = f"{result_index + 1}. {results['source_name']}"
        with st.expander(plate_label, expanded=(len(all_results) == 1)):
            safe_sample = safe_filename_part(results.get("sample_name", ""), "sample")
            report_date = results.get(
                "generated_date", datetime.now().strftime("%Y-%m-%d")
            )
            report_prefix = f"{report_date}_{safe_sample}"

            available_outputs = [
                key for key in ("statistics", "standard_hits", "high_hits")
                if key in results
            ]
            download_columns = st.columns(1 + len(available_outputs))

            with download_columns[0]:
                st.download_button(
                    "Download HTML",
                    data=results["html"],
                    file_name=f"{report_prefix}_plate_report.html",
                    mime="text/html",
                    key=f"download_html_button_{result_index}",
                    use_container_width=True,
                )

            labels = {
                "statistics": ("Statistics", "statistics.csv"),
                "standard_hits": ("Standard hits", "standard_hits.csv"),
                "high_hits": ("High hits", "high_hits.csv"),
            }
            for column_index, key in enumerate(available_outputs, start=1):
                label, suffix = labels[key]
                with download_columns[column_index]:
                    st.download_button(
                        label,
                        data=results[key],
                        file_name=f"{report_prefix}_{suffix}",
                        mime="text/csv",
                        key=f"download_{key}_button_{result_index}",
                        use_container_width=True,
                    )

            if "standard_hits" not in results and "high_hits" not in results:
                st.warning(
                    "This plate did not produce hit tables, usually because its "
                    "Z′ value was below zero or could not be calculated."
                )

            st.components.v1.html(
                results["html"].decode("utf-8", errors="replace"),
                height=900,
                scrolling=True,
            )
