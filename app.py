
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from report_engine import generate_html


st.set_page_config(
    page_title="96-Well Plate QC",
    page_icon="🧪",
    layout="wide",
)

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
      <h1>96-Well Plate QC Report Generator</h1>
      <p>Upload a plate CSV, generate the QC report, and download the results.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Report settings")
    sample_name = st.text_input("Sample name", value="Unknown Sample")
    report_title = st.text_input("Report title", value="PurUC5 Plate QC")

    custom_threshold = st.checkbox("Use custom plate Z-score threshold")
    threshold = None
    if custom_threshold:
        threshold = st.number_input(
            "Plate Z-score threshold",
            value=2.000,
            step=0.100,
            format="%.3f",
        )

    st.caption(
        "Default hit threshold: the highest whole-plate Z-score among E12:H12."
    )

uploaded = st.file_uploader(
    "Upload 96-well plate CSV",
    type=["csv"],
    help="The file should contain rows A–H and columns 1–12.",
)

if uploaded is None:
    st.info("Upload a CSV file to begin.")
    st.stop()

st.write(f"**Selected file:** {uploaded.name}")

if st.button("Generate QC report", type="primary", use_container_width=True):
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
                    zscore_threshold=threshold,
                )

                html_bytes = html_path.read_bytes()
                statistics_bytes = html_path.with_name(
                    "plate_report_statistics.csv"
                ).read_bytes()
                hits_bytes = html_path.with_name(
                    "plate_report_passing_wells.csv"
                ).read_bytes()

        st.success("Report generated successfully.")

        base_name = Path(uploaded.name).stem
        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                "Download HTML report",
                data=html_bytes,
                file_name=f"{base_name}_plate_report.html",
                mime="text/html",
                use_container_width=True,
            )

        with col2:
            st.download_button(
                "Download statistics",
                data=statistics_bytes,
                file_name=f"{base_name}_statistics.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col3:
            st.download_button(
                "Download candidate hits",
                data=hits_bytes,
                file_name=f"{base_name}_candidate_hits.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.subheader("Report preview")
        st.components.v1.html(
            html_bytes.decode("utf-8"),
            height=1100,
            scrolling=True,
        )

    except Exception as exc:
        st.error(f"Report generation failed: {exc}")
