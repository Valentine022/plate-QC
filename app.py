from __future__ import annotations
import base64
import csv
import inspect
import io
import html as html_lib
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
          Upload one or more stacked plate files, generate the QC analysis, and download one combined report.
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
    "Upload plate CSV or TSV file(s)",
    type=["csv", "tsv", "txt"],
    accept_multiple_files=True,
    help=(
        "A file may contain one plate or several 8×12 plates stacked vertically. "
        "Each stacked plate must repeat the 1–12 header row before rows A–H."
    ),
    key="plate_csv_uploader",
)

if not uploaded_files:
    st.info("Upload one or more plate files to begin.")
    st.stop()

st.write(f"**Selected files:** {len(uploaded_files)}")
st.caption(", ".join(uploaded.name for uploaded in uploaded_files))


def split_stacked_plates(file_bytes: bytes, source_name: str) -> list[dict]:
    """Split a CSV/TSV containing repeated 1–12 headers into 8×12 plates."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    nonempty_lines = [line for line in text.splitlines() if line.strip()]
    if not nonempty_lines:
        raise ValueError("The uploaded file is empty.")

    sample = "\n".join(nonempty_lines[:20])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = "\t" if "\t" in nonempty_lines[0] else ","

    rows = []
    for row in csv.reader(nonempty_lines, delimiter=delimiter):
        cleaned = [cell.strip() for cell in row]
        while cleaned and cleaned[-1] == "":
            cleaned.pop()
        rows.append(cleaned)

    expected_header = [str(number) for number in range(1, 13)]

    def is_header(row: list[str]) -> bool:
        return len(row) >= 12 and row[-12:] == expected_header

    header_positions = [index for index, row in enumerate(rows) if is_header(row)]
    if not header_positions:
        raise ValueError(
            "No plate header was found. Expected a row containing columns 1 through 12."
        )

    plates = []
    source_stem = Path(source_name).stem
    for plate_number, header_index in enumerate(header_positions, start=1):
        data_rows = rows[header_index + 1:header_index + 9]
        if len(data_rows) != 8:
            raise ValueError(
                f"Plate {plate_number} is incomplete: expected rows A–H after its header."
            )

        normalised_rows = []
        for expected_row, row in zip("ABCDEFGH", data_rows):
            if len(row) < 13:
                raise ValueError(
                    f"Plate {plate_number}, row {expected_row} has fewer than 12 values."
                )
            row_label = row[0].upper()
            values = row[1:13]
            if row_label != expected_row:
                raise ValueError(
                    f"Plate {plate_number}: expected row {expected_row}, found {row_label or 'blank'}."
                )
            normalised_rows.append([row_label, *values])

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["", *expected_header])
        writer.writerows(normalised_rows)
        plates.append(
            {
                "source_name": source_name,
                "plate_name": f"{source_stem}_plate_{plate_number}",
                "csv_bytes": output.getvalue().encode("utf-8"),
            }
        )

    return plates


plate_inputs = []
input_errors = []
for uploaded in uploaded_files:
    try:
        plate_inputs.extend(split_stacked_plates(uploaded.getvalue(), uploaded.name))
    except Exception as exc:
        input_errors.append({"source_name": uploaded.name, "error": str(exc)})

if input_errors:
    for item in input_errors:
        st.error(f"{item['source_name']}: {item['error']}")

if not plate_inputs:
    st.stop()

st.success(f"Detected {len(plate_inputs)} plate(s) across the uploaded file(s).")


def extract_report_section(report_html: str, section_id: str) -> str:
    """Extract one complete <section> or <details> block by its HTML id."""
    pattern = re.compile(
        rf'<(?P<tag>section|details)\b[^>]*\bid=["\']{re.escape(section_id)}["\'][^>]*>'
        rf'.*?</(?P=tag)>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(report_html)
    return match.group(0) if match else ""


def extract_qc_summary(report_html: str) -> str:
    pattern = re.compile(
        r'<section\b[^>]*class=["\'][^"\']*\bqc\b[^"\']*["\'][^>]*>'
        r'.*?</section>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(report_html)
    return match.group(0) if match else ""


def build_combined_report(all_results: list[dict], title: str, user_name: str) -> bytes:
    """Create one report grouped by analysis section across all plates."""
    section_specs = [
        ("qc-results", "QC and Z′ results", "qc"),
        ("hit-wells", "Hit wells", "hits"),
        ("zscore-plots", "Z-score heatmaps", "z-heatmap"),
        ("raw-plots", "Raw measurement heatmaps", "raw-heatmap"),
        ("statistics", "Group statistics", "statistics"),
        ("averages", "Group-average plots", "averages"),
    ]

    grouped_html = []
    for anchor, heading, source_id in section_specs:
        plate_blocks = []
        for index, result in enumerate(all_results, start=1):
            report_html = result["html"].decode("utf-8", errors="replace")
            content = (
                extract_qc_summary(report_html)
                if source_id == "qc"
                else extract_report_section(report_html, source_id)
            )
            if not content:
                content = '<p class="note">This section was not generated for this plate.</p>'
            plate_name = html_lib.escape(result["source_name"])
            plate_blocks.append(
                f'<article class="plate-block"><h3>Plate {index}: {plate_name}</h3>{content}</article>'
            )
        grouped_html.append(
            f'<section id="{anchor}" class="analysis-group"><h2>{heading}</h2>'
            + "".join(plate_blocks)
            + "</section>"
        )

    nav = "".join(
        f'<a href="#{anchor}">{heading}</a>' for anchor, heading, _ in section_specs
    )
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_lib.escape(title)}</title>
<style>
:root{{--bg:#e8f7f5;--panel:#fff;--border:#b9dfd8;--text:#1c2434;--muted:#667085;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:19px/1.6 system-ui,sans-serif}}
nav{{position:sticky;top:0;z-index:10;display:flex;gap:8px;flex-wrap:wrap;padding:12px 20px;background:#f0e8f7;border-bottom:1px solid var(--border)}}
nav a{{text-decoration:none;background:#9370DB;color:white;padding:7px 11px;border-radius:999px;font-weight:650}}
main{{max-width:1280px;margin:auto;padding:28px 20px 60px}}
h1{{margin:0 0 8px;font-size:48px;line-height:1.1}}
.subtitle{{color:var(--muted);margin-bottom:30px;font-size:21px;line-height:1.55}}
.analysis-group{{margin-top:28px}}
.analysis-group>h2{{border-bottom:4px solid #9370DB;padding-bottom:10px;font-size:34px;line-height:1.2}}
.plate-block{{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:18px;margin:16px 0;box-shadow:0 7px 22px rgba(31,42,68,.06)}}
.plate-block h3{{margin:0 0 16px;font-size:30px;line-height:1.2}}
.plate-block section,.plate-block details{{box-shadow:none;margin:0;border:0;padding:0;background:transparent}}
.plate-block summary{{font-size:26px;font-weight:750;padding:10px 0}}
.plate-block .content{{padding:0}}
.report-table{{border-collapse:collapse;width:100%;font-size:18px}}
.report-table th,.report-table td{{border-bottom:1px solid var(--border);padding:11px 13px;text-align:right}}
.report-table th{{font-size:19px;font-weight:750}}
.report-table th:first-child,.report-table td:first-child{{text-align:left}}
.table-wrap{{overflow-x:auto}} img{{max-width:100%;height:auto;display:block}}
.note{{color:var(--muted);font-size:19px}}
.qc-summary{{display:grid!important;grid-template-columns:minmax(0,1fr) minmax(280px,360px)!important;align-items:center!important;gap:32px!important}}
.qc-copy h2{{font-size:38px!important;line-height:1.15!important;margin:0 0 12px!important}}
.qc-copy p{{font-size:24px!important;line-height:1.5!important;margin:0!important}}
.zscore-block{{min-width:280px!important;padding:26px!important;border-radius:20px!important;background:#f0e8f7!important;border:3px solid #9370DB!important;text-align:center!important}}
.zscore-label{{font-size:30px!important;font-weight:800!important;letter-spacing:.02em!important}}
.zscore-value{{font-size:104px!important;line-height:.95!important;font-weight:900!important;margin-top:12px!important}}
@media(max-width:760px){{.qc-summary{{grid-template-columns:1fr!important}}.zscore-block{{min-width:0!important}}.zscore-value{{font-size:82px!important}}}}
@media print{{nav{{display:none}}main{{padding-top:10px}}.plate-block{{break-inside:avoid}}}}
</style>
</head>
<body>
<nav>{nav}</nav>
<main>
<h1>{html_lib.escape(title)}</h1>
<div class="subtitle"><strong>Prepared by:</strong> {html_lib.escape(user_name)}<br>
<strong>Plates:</strong> {len(all_results)}<br><strong>Generated:</strong> {generated}</div>
{''.join(grouped_html)}
</main>
</body>
</html>"""
    return document.encode("utf-8")

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

            for index, plate_input in enumerate(plate_inputs, start=1):
                progress.progress(
                    (index - 1) / len(plate_inputs),
                    text=(
                        f"Analysing {plate_input['plate_name']} "
                        f"({index}/{len(plate_inputs)})..."
                    ),
                )

                try:
                    plate_stem = safe_filename_part(
                        plate_input["plate_name"], f"plate_{index}"
                    )
                    plate_dir = temp / f"{index:03d}_{plate_stem}"
                    plate_dir.mkdir(parents=True, exist_ok=True)

                    csv_path = plate_dir / f"{plate_stem}.csv"
                    csv_path.write_bytes(plate_input["csv_bytes"])
                    html_path = plate_dir / "plate_report.html"

                    display_sample_name = sample_name.strip()
                    if len(plate_inputs) > 1:
                        display_sample_name = (
                            f"{display_sample_name} – {plate_input['plate_name']}"
                            if display_sample_name
                            else plate_input["plate_name"]
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
                        "source_name": plate_input["plate_name"],
                        "source_file": plate_input["source_name"],
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
                        {
                            "source_name": plate_input["plate_name"],
                            "error": str(plate_exc),
                        }
                    )

            progress.progress(1.0, text="Plate analysis complete.")

        if not all_results:
            error_details = "; ".join(
                f"{item['source_name']}: {item['error']}" for item in generation_errors
            )
            raise RuntimeError(f"No reports were generated. {error_details}")

        combined_title = (sample_name.strip() or "Multi-plate QC") + " – Combined report"
        combined_report = build_combined_report(
            all_results, combined_title, user_name.strip()
        )

        st.session_state["plate_report_results"] = all_results
        st.session_state["plate_combined_report"] = combined_report
        st.session_state["plate_report_errors"] = generation_errors

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
        "Download complete combined report",
        data=st.session_state["plate_combined_report"],
        file_name=(
            f"{datetime.now().strftime('%Y-%m-%d')}_"
            f"{safe_filename_part(sample_name, 'plates')}_combined_report.html"
        ),
        mime="text/html",
        key="download_combined_report_button",
        use_container_width=True,
    )

    st.subheader("Combined report preview")
    st.caption(
        "Results are grouped by section: all QC/Z′ results, then hit wells, "
        "then heatmaps, statistics, and plots."
    )
    st.components.v1.html(
        st.session_state["plate_combined_report"].decode("utf-8", errors="replace"),
        height=1200,
        scrolling=True,
    )

