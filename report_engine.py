#!/usr/bin/env python3
"""
Generate a 96-well plate HTML report from a CSV file.

Plate map:
- Enzyme + Film: A1-D1
- Film: E1-H1
- Samples: A2-H11
- Lysate: A12-D12
- Blank: E12-H12

Usage:
    python report_engine.py test.csv -o plate_report.html
"""

from __future__ import annotations

import argparse
import base64
import io
import html
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


ROWS = list("ABCDEFGH")
COLS = [str(i) for i in range(1, 13)]

PLATE_GROUPS = {
    "Enzyme + Film": [(r, "1") for r in "ABCD"],
    "Film": [(r, "1") for r in "EFGH"],
    "Samples": [(r, str(c)) for r in ROWS for c in range(2, 12)],
    "Lysate": [(r, "12") for r in "ABCD"],
    "Blank": [(r, "12") for r in "EFGH"],
}

# Z' comparison for this plate layout.
Z_PRIME_NEGATIVE = "Lysate"
Z_PRIME_POSITIVE = "Enzyme + Film"


def load_plate(csv_path: Path) -> pd.DataFrame:
    plate = pd.read_csv(csv_path, index_col=0)
    plate.index = plate.index.astype(str).str.upper().str.strip()
    plate.columns = plate.columns.astype(str).str.strip()
    plate = plate.reindex(index=ROWS, columns=COLS)
    return plate.apply(pd.to_numeric, errors="coerce")


def group_values(plate: pd.DataFrame, wells: list[tuple[str, str]]) -> pd.Series:
    return pd.Series(
        [plate.loc[row, col] for row, col in wells],
        index=[f"{row}{col}" for row, col in wells],
        dtype="float64",
    ).dropna()


def calculate_statistics(plate: pd.DataFrame) -> pd.DataFrame:
    records = []
    for group, wells in PLATE_GROUPS.items():
        values = group_values(plate, wells)
        mean = values.mean()
        stdev = values.std(ddof=1)
        records.append(
            {
                "Group": group,
                "N": int(values.count()),
                "Average": mean,
                "StDev": stdev,
                "Min": values.min(),
                "Max": values.max(),
            }
        )
    return pd.DataFrame(records).set_index("Group")


def calculate_z_prime(stats: pd.DataFrame, negative: str, positive: str) -> float:
    """
    Excel equivalent:
    =1-((3*(F13+F14))/ABS(C13-C14))

    F13 = SD of Enzyme + Film
    F14 = SD of Lysate
    C13 = Mean of Enzyme + Film
    C14 = Mean of Lysate
    """

    enzyme_mean = float(stats.loc["Enzyme + Film", "Average"])
    enzyme_sd = float(stats.loc["Enzyme + Film", "StDev"])

    lysate_mean = float(stats.loc["Lysate", "Average"])
    lysate_sd = float(stats.loc["Lysate", "StDev"])

    if any(pd.isna(v) for v in [enzyme_mean, enzyme_sd, lysate_mean, lysate_sd]):
        return np.nan

    denominator = abs(enzyme_mean - lysate_mean)

    if denominator == 0:
        return np.nan

    return 1 - ((3 * (enzyme_sd + lysate_sd)) / denominator)


def calculate_hit_tables(
    plate: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, float, float, float]:
    """Create standard-hit and high-hit tables from Enzyme + Film controls A1:D1.

    Standard hit: raw signal >= mean signal of Enzyme + Film controls.
    High hit: raw signal >= Enzyme + Film-control mean + 3 * Enzyme + Film-control sample SD.
    """
    film_wells = PLATE_GROUPS["Enzyme + Film"]
    film_values = group_values(plate, film_wells)

    film_mean = float(film_values.mean())
    film_sd = float(film_values.std(ddof=1))
    high_threshold = film_mean + (3 * film_sd)

    excluded_controls = {f"{row}{col}" for row, col in film_wells}
    records = []

    for row in ROWS:
        for col in COLS:
            well = f"{row}{col}"
            value = plate.loc[row, col]
            if well in excluded_controls or pd.isna(value):
                continue

            records.append(
                {
                    "Well": well,
                    "Raw value": float(value),
                    "Standard threshold": film_mean,
                    "High threshold": high_threshold,
                }
            )

    all_wells = pd.DataFrame(
        records,
        columns=["Well", "Raw value", "Standard threshold", "High threshold"],
    )

    if pd.isna(film_mean):
        standard_hits = all_wells.iloc[0:0].copy()
    else:
        standard_hits = all_wells[all_wells["Raw value"] >= film_mean].copy()

    if pd.isna(high_threshold):
        high_hits = all_wells.iloc[0:0].copy()
    else:
        high_hits = all_wells[all_wells["Raw value"] >= high_threshold].copy()

    for table, label in ((standard_hits, "STANDARD HIT"), (high_hits, "HIGH HIT")):
        table["Result"] = label
        table.sort_values("Raw value", ascending=False, inplace=True)
        table.reset_index(drop=True, inplace=True)

    return standard_hits, high_hits, film_mean, film_sd, high_threshold


def figure_to_data_uri(fig) -> str:
    buffer = io.BytesIO()
    try:
        fig.savefig(buffer, format="png", dpi=140, bbox_inches="tight")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    finally:
        plt.close(fig)
        buffer.close()


def make_zscore_heatmap(plate: pd.DataFrame) -> str:
    """Create a Z-score heatmap relative to all valid wells on the plate."""
    plate_mean = np.nanmean(plate.values)
    plate_sd = np.nanstd(plate.values, ddof=1)

    if plate_sd == 0 or pd.isna(plate_sd):
        z_plate = plate * np.nan
    else:
        z_plate = (plate - plate_mean) / plate_sd

    fig, ax = plt.subplots(figsize=(12, 6))
    image = ax.imshow(z_plate.values, cmap="coolwarm", aspect="auto")
    ax.set_xticks(np.arange(12), labels=COLS)
    ax.set_yticks(np.arange(8), labels=ROWS)
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    ax.set_title("Plate Z-score Heatmap")

    for i in range(8):
        for j in range(12):
            value = z_plate.iloc[i, j]
            if not np.isnan(value):
                r, g, b, _ = image.cmap(image.norm(value))
                luminance = 0.299 * r + 0.587 * g + 0.114 * b
                text_colour = "white" if luminance < 0.5 else "black"
                ax.text(
                    j,
                    i,
                    f"{value:.1f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=text_colour,
                )

    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("Plate Z-score")
    fig.tight_layout()
    return figure_to_data_uri(fig)


def make_raw_heatmap(plate: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(12, 6))
    image = ax.imshow(plate.values, aspect="auto")
    ax.set_xticks(np.arange(12), labels=COLS)
    ax.set_yticks(np.arange(8), labels=ROWS)
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    ax.set_title("Raw Plate Measurements")

    for i in range(8):
        for j in range(12):
            value = plate.iloc[i, j]
            if not np.isnan(value):
                # Match the text colour to the actual heatmap cell colour.
                r, g, b, _ = image.cmap(image.norm(value))
                luminance = 0.299 * r + 0.587 * g + 0.114 * b
                text_colour = "white" if luminance < 0.5 else "black"

                ax.text(
                    j,
                    i,
                    f"{value:.3f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=text_colour,
                )

    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("Measurement")
    fig.tight_layout()
    return figure_to_data_uri(fig)


def make_group_chart(stats: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(stats))
    ax.bar(x, stats["Average"], yerr=stats["StDev"], capsize=5)
    ax.set_xticks(x, labels=stats.index, rotation=20, ha="right")
    ax.set_ylabel("Average measurement")
    ax.set_title("Group Average ± StDev")
    fig.tight_layout()
    return figure_to_data_uri(fig)


def qc_interpretation(z_prime: float) -> tuple[str, str]:
    """Classify the plate from its Z-prime factor."""
    if np.isnan(z_prime):
        return "Fail", "The control groups could not be compared."
    if z_prime > 0.3:
        return "Pass", "The plate passed QC and shows strong control separation."
    if z_prime >= 0:
        return (
            "Acceptable",
            "The plate is acceptable, but control separation is low.",
        )
    return (
        "Fail",
        "The plate failed QC because the Z-prime factor is below zero. "
        "Statistics and hit calls are not reported.",
    )


from datetime import datetime

def generate_html(csv_path: Path, output_path: Path, title: str, sample_name: str, zscore_threshold: float | None) -> None:
    plate = load_plate(csv_path)
    stats = calculate_statistics(plate)
    z_prime = calculate_z_prime(stats, Z_PRIME_NEGATIVE, Z_PRIME_POSITIVE)
    qc_label, qc_message = qc_interpretation(z_prime)

    # Statistics and hit calls are shown only when Z-prime is zero or higher.
    report_statistics = not pd.isna(z_prime) and z_prime >= 0

    if report_statistics:
        standard_hits, high_hits, film_mean, film_sd, high_threshold = (
            calculate_hit_tables(plate)
        )
    else:
        empty_columns = [
            "Well",
            "Raw value",
            "Standard threshold",
            "High threshold",
            "Result",
        ]
        standard_hits = pd.DataFrame(columns=empty_columns)
        high_hits = pd.DataFrame(columns=empty_columns)
        film_mean = np.nan
        film_sd = np.nan
        high_threshold = np.nan

    stats_display = stats.copy()
    for column in ["Average", "StDev", "Min", "Max"]:
        stats_display[column] = stats_display[column].map(lambda x: "—" if pd.isna(x) else f"{x:.6f}")

    stats_table = stats_display.reset_index().to_html(
        index=False, classes="report-table", border=0, escape=True
    )

    plate_display = plate.copy()
    plate_display.index.name = "Row"
    plate_table = plate_display.to_html(
        classes="report-table plate-table",
        border=0,
        float_format=lambda x: f"{x:.4f}",
        na_rep="—",
    )

    def format_hit_table(table: pd.DataFrame, empty_message: str) -> str:
        if table.empty:
            return f'<p class="note">{html.escape(empty_message)}</p>'

        display = table.copy()
        for column in ["Raw value", "Standard threshold", "High threshold"]:
            display[column] = display[column].map(lambda value: f"{value:.6f}")
        return display.to_html(
            index=False,
            classes="report-table passing-table",
            border=0,
            escape=True,
        )

    standard_hits_table = format_hit_table(
        standard_hits,
        "No wells met the standard-hit threshold.",
    )
    high_hits_table = format_hit_table(
        high_hits,
        "No wells met the high-hit threshold.",
    )

    raw_heatmap = make_raw_heatmap(plate)

    if report_statistics:
        z_heatmap = make_zscore_heatmap(plate)
        group_chart = make_group_chart(stats)

        statistics_nav = '<a href="#statistics">Statistics</a>'
        z_heatmap_nav = '<a href="#z-heatmap">Z-score Heatmap</a>'
        standard_hits_nav = '<a href="#standard-hits">Standard Hits</a>'
        high_hits_nav = '<a href="#high-hits">High Hits</a>'
        averages_nav = '<a href="#averages">Group Averages</a>'

        statistics_section = f"""
  <details id="statistics" open>
    <summary>Group statistics</summary>
    <div class="content table-wrap">{stats_table}</div>
  </details>
"""

        z_heatmap_section = f"""
  <details id="z-heatmap">
    <summary>Plate Z-score heatmap</summary>
    <div class="content"><img src="{z_heatmap}" alt="Plate Z-score heatmap"></div>
  </details>
"""
        high_hits_section = f"""
  <details id="high-hits" open>
    <summary>High-threshold hit wells</summary>
    <div class="content">
      <div class="threshold-note">
        Film controls: <strong>A1, B1, C1 and D1</strong><br>
        Film-control mean: <strong>{film_mean:.6f}</strong><br>
        Film-control StDev: <strong>{film_sd:.6f}</strong><br>
        High-hit rule: raw signal &gt;= mean + 3 x StDev =
        <strong>{high_threshold:.6f}</strong>
      </div>
      <div class="table-wrap">{high_hits_table}</div>
    </div>
  </details>
"""
        standard_hits_section = f"""
  <details id="standard-hits" open>
    <summary>Standard hit wells</summary>
    <div class="content">
      <div class="threshold-note">
        Film controls: <strong>A1, B1, C1 and D1</strong><br>
        Film-control mean: <strong>{film_mean:.6f}</strong><br>
        Standard-hit rule: raw signal &gt;= <strong>{film_mean:.6f}</strong>
      </div>
      <div class="table-wrap">{standard_hits_table}</div>
    </div>
  </details>
"""
        averages_section = f"""
  <details id="averages">
    <summary>Group averages</summary>
    <div class="content"><img src="{group_chart}" alt="Group average bar chart"></div>
  </details>
"""
    else:
        statistics_nav = '<a href="#statistics">Statistics</a>'
        z_heatmap_nav = ""
        standard_hits_nav = ""
        high_hits_nav = ""
        averages_nav = ""

statistics_section = f"""
<details id="statistics" open>
  <summary>Group statistics</summary>
  <div class="content table-wrap">
    {stats_table}
  </div>
</details>

<section class="qc-failure">
  <p>
    Z-prime is below zero, so the Z-score heatmap, hit tables,
    group averages, and CSV hit exports have been suppressed.
  </p>
</section>
"""
        z_heatmap_section = ""
        standard_hits_section = ""
        high_hits_section = ""
        averages_section = ""

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  --bg: #e8f7f5;
  --panel: #f9fffe;
  --text: #1c2434;
  --muted: #667085;
  --border: #b9dfd8;
  --accent: #1b8f84;
  --good: #18794e;
  --warn: #9a6700;
  --bad: #b42318;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: #1c2434;
  font: 15px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
main {{ max-width: 1250px; margin: auto; padding: 90px 20px 60px; }}
.topnav {{
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 20px;
  background: #f0e8f7;
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(8px);
}}
.topnav a {{
  color: var(--text);
  text-decoration: none;
  padding: 8px 12px;
  border-radius: 999px;
  background: #9370DB;
  font-weight: 650;
}}
details {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  margin-top: 18px;
  box-shadow: 0 7px 22px rgba(31, 42, 68, .06);
}}
summary {{
  cursor: pointer;
  padding: 18px 22px;
  font-size: 20px;
  font-weight: 750;
}}
details .content {{ padding: 0 22px 22px; }}
@media print {{
  .topnav {{ display:none; }}
  main {{ padding-top:20px; }}
  details {{ display:block; }}
  details > * {{ display:block; }}
}}
h1 {{ margin: 0 0 5px; font-size: 38px; }}
h2 {{ margin-top: 0; }}
.subtitle {{ color: var(--muted); margin-bottom: 24px; }}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 14px;
}}
.card, section {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: 0 7px 22px rgba(31, 42, 68, .06);
}}
.card {{ padding: 18px; }}
.card .label {{ color: var(--muted); font-size: 13px; }}
.card .value {{ font-size: 27px; font-weight: 750; margin-top: 3px; }}
section {{ margin-top: 18px; padding: 22px; }}
.grid-2 {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(430px, 1fr));
  gap: 18px;
}}
.table-wrap {{ overflow-x: auto; }}
.report-table {{ border-collapse: collapse; width: 100%; }}
.report-table th, .report-table td {{
  border-bottom: 1px solid var(--border);
  padding: 9px 11px;
  text-align: right;
  white-space: nowrap;
}}
.report-table th {{ background: #b9dfd8 !important; color: #1c2434 !important; }}
.report-table th:first-child, .report-table td:first-child {{ text-align: left; }}
.plate-table th, .plate-table td {{ text-align: center; }}
.plate-table tbody th {{
  background: #b9dfd8 !important;
  color: #1c2434 !important;
  font-weight: 750;
}}
img {{ width: 100%; height: auto; display: block; }}
.qc {{
  border-left: 5px solid {"var(--bad)" if np.isnan(z_prime) or z_prime < 0 else "var(--good)" if z_prime > .5 else "var(--warn)"};
}}
.note {{ color: var(--muted); }}
code {{ background: #eef1f7; padding: 2px 5px; border-radius: 4px; }}
footer {{ margin-top: 20px; color: var(--muted); font-size: 13px; }}
</style>
</head>
<body>
<nav class="topnav">
  <a href="#overview">Overview</a>
  <a href="#plate">Raw Plate</a>
  {statistics_nav}
  <a href="#raw-heatmap">Raw Heatmap</a>
  {z_heatmap_nav}
  {standard_hits_nav}
  {high_hits_nav}
  {averages_nav}
</nav>
<main>
  <h1>{html.escape(title)}</h1>
  <div class="subtitle">
<strong>Sample:</strong> {html.escape(sample_name)}<br>
<strong>Source:</strong> {html.escape(csv_path.name)}<br>
<strong>Report generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
</div>

  <div class="cards">
    <div class="card"><div class="label">Z' factor</div><div class="value">{z_prime:.4f}</div></div>
  </div>

  <section class="qc">
    <h2>QC assessment: {qc_label}</h2>
    <p>{qc_message}</p>
  </section>

  <div id="overview"></div>

  <details id="plate" open>
    <summary>Raw plate values</summary>
    <div class="content table-wrap">{plate_table}</div>
  </details>

  {statistics_section}

  <details id="raw-heatmap" open>
    <summary>Raw measurement heatmap</summary>
    <div class="content"><img src="{raw_heatmap}" alt="Raw plate measurement heatmap"></div>
  </details>

  {z_heatmap_section}
  {high_hits_section}
  {standard_hits_section}
  {averages_section}

  <footer>
    To change the Z' comparison, edit <code>Z_PRIME_NEGATIVE</code> and
    <code>Z_PRIME_POSITIVE</code> near the top of the script.
  </footer>
</main>
</body>
</html>"""

    output_path.write_text(html_doc, encoding="utf-8")

    export_paths = [
        output_path.with_name(output_path.stem + "_statistics.csv"),
        output_path.with_name(output_path.stem + "_passing_wells.csv"),
        output_path.with_name(output_path.stem + "_high_hits.csv"),
        output_path.with_name(output_path.stem + "_standard_hits.csv"),
    ]

    if report_statistics:
        stats_export = stats.reset_index()
        stats_export.loc[len(stats_export)] = {
            "Group": f"Z' ({Z_PRIME_NEGATIVE} vs {Z_PRIME_POSITIVE})",
            "Average": z_prime,
        }
        stats_export.to_csv(export_paths[0], index=False)

        # Keep the legacy filename for compatibility with older app versions.
        standard_hits.to_csv(export_paths[1], index=False)
        standard_hits.to_csv(export_paths[2], index=False)
        high_hits.to_csv(export_paths[3], index=False)
    else:
        # Ensure no statistics or hit files remain for a failed plate.
        for export_path in export_paths:
            export_path.unlink(missing_ok=True)

    print(f"HTML report: {output_path.resolve()}")
    if report_statistics:
        print(
            "Statistics: "
            f"{output_path.with_name(output_path.stem + '_statistics.csv').resolve()}"
        )
        print(stats)
    else:
        print("Statistics and hit exports suppressed because Z-prime is below zero.")
    print(f"Z' ({Z_PRIME_NEGATIVE} vs {Z_PRIME_POSITIVE}): {z_prime:.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a 96-well plate HTML QC report.")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("plate_report.html"))
    parser.add_argument("--title", default="Plate QC Report")
    parser.add_argument("--sample-name", default="Sample",
                        help="Sample name displayed in the report")
    parser.add_argument(
        "--zscore-threshold",
        type=float,
        default=None,
        help=(
            "Plate Z-score required to pass. "
            "Default: highest plate Z-score among B control wells E12:H12."
        ),
    )
    args = parser.parse_args()

    if not args.csv_file.exists():
        parser.error(f"CSV file not found: {args.csv_file}")

    generate_html(args.csv_file, args.output, args.title, args.sample_name, args.zscore_threshold)


if __name__ == "__main__":
    main()
