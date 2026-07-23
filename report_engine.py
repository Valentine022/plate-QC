#!/usr/bin/env python3
"""
Generate a 96-well plate HTML report from a CSV file.

Plate map:
- PurUC5 Lysate: A1-D1
- NPs: E1-H1
- C: A2-H11
- B: A12-D12
- PurUC5 + NPs: E12-H12

Usage:
    python plate_report.py test.csv -o plate_report.html
"""

from __future__ import annotations

import argparse
import base64
import io
import html
from pathlib import Path
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROWS = list("ABCDEFGH")
COLS = [str(i) for i in range(1, 13)]

PLATE_GROUPS = {
    "PurUC5 Lysate": [(r, "1") for r in "ABCD"],
    "NPs": [(r, "1") for r in "EFGH"],
    "C": [(r, str(c)) for r in ROWS for c in range(2, 12)],
    "B": [(r, "12") for r in "ABCD"],
    "PurUC5 + NPs": [(r, "12") for r in "EFGH"],
}

# Edit these two names to change the Z' comparison.
Z_PRIME_NEGATIVE = "NPs"
Z_PRIME_POSITIVE = "PurUC5 + NPs"


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
                "CV %": (stdev / mean * 100) if mean != 0 else np.nan,
                "Min": values.min(),
                "Max": values.max(),
            }
        )
    return pd.DataFrame(records).set_index("Group")


def calculate_z_prime(stats: pd.DataFrame, negative: str, positive: str) -> float:
    neg_mean = stats.loc[negative, "Average"]
    neg_sd = stats.loc[negative, "StDev"]
    pos_mean = stats.loc[positive, "Average"]
    pos_sd = stats.loc[positive, "StDev"]
    difference = abs(pos_mean - neg_mean)
    if difference == 0 or np.isnan(difference):
        return np.nan
    return 1 - (3 * (neg_sd + pos_sd) / difference)


def calculate_control_zscores(
    plate: pd.DataFrame,
    threshold: float | None = None,
) -> tuple[pd.DataFrame, float, float, float]:
    """Calculate Z-scores relative to all valid wells on the plate.

    E12:H12 are used only to derive the default candidate-hit threshold:
    the highest plate Z-score among those four control wells.
    """
    plate_mean = float(np.nanmean(plate.values))
    plate_sd = float(np.nanstd(plate.values, ddof=1))
    control_wells = [(row, "12") for row in "EFGH"]

    if plate_sd == 0 or pd.isna(plate_sd):
        z_plate = plate * np.nan
        applied_threshold = np.nan if threshold is None else float(threshold)
    else:
        z_plate = (plate - plate_mean) / plate_sd
        control_zscores = pd.Series(
            [z_plate.loc[row, col] for row, col in control_wells],
            index=[f"{row}{col}" for row, col in control_wells],
            dtype="float64",
        )
        applied_threshold = (
            float(control_zscores.max()) if threshold is None else float(threshold)
        )

    records = []
    for row in ROWS:
        for col in COLS:
            value = plate.loc[row, col]
            z_score = z_plate.loc[row, col]
            if pd.notna(value) and pd.notna(z_score) and z_score > applied_threshold:
                records.append(
                    {
                        "Well": f"{row}{col}",
                        "Raw value": value,
                        "Plate Z-score": z_score,
                        "Result": "PASS",
                    }
                )

    passing = pd.DataFrame(
        records,
        columns=["Well", "Raw value", "Plate Z-score", "Result"],
    )
    if not passing.empty:
        passing = passing.sort_values(
            "Plate Z-score", ascending=False
        ).reset_index(drop=True)

    return passing, plate_mean, plate_sd, applied_threshold


def figure_to_data_uri(fig) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


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
    if np.isnan(z_prime):
        return "Unavailable", "The selected groups could not be compared."
    if z_prime >= 0.5:
        return "Excellent", "The assay shows strong separation and low variability."
    if z_prime >= 0:
        return "Marginal", "The assay has limited separation or substantial variability."
    return "Poor", "The group distributions overlap strongly relative to their variability."


from datetime import datetime

def generate_html(csv_path: Path, output_path: Path, title: str, sample_name: str, zscore_threshold: float | None) -> None:
    plate = load_plate(csv_path)
    stats = calculate_statistics(plate)
    z_prime = calculate_z_prime(stats, Z_PRIME_NEGATIVE, Z_PRIME_POSITIVE)
    qc_label, qc_message = qc_interpretation(z_prime)
    passing_wells, control_mean, control_sd, applied_zscore_threshold = calculate_control_zscores(
        plate, zscore_threshold
    )

    stats_display = stats.copy()
    for column in ["Average", "StDev", "Min", "Max"]:
        stats_display[column] = stats_display[column].map(lambda x: "—" if pd.isna(x) else f"{x:.6f}")
    stats_display["CV %"] = stats_display["CV %"].map(lambda x: "—" if pd.isna(x) else f"{x:.2f}%")

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

    if passing_wells.empty:
        passing_wells_table = (
            '<p class="note">No wells exceeded the selected control-relative '
            'Z-score threshold.</p>'
        )
    else:
        passing_display = passing_wells.copy()
        passing_display["Raw value"] = passing_display["Raw value"].map(
            lambda x: f"{x:.6f}"
        )
        passing_display["Plate Z-score"] = passing_display["Plate Z-score"].map(
            lambda x: f"{x:.3f}"
        )
        passing_wells_table = passing_display.to_html(
            index=False,
            classes="report-table passing-table",
            border=0,
            escape=True,
        )

    raw_heatmap = make_raw_heatmap(plate)
    z_heatmap = make_zscore_heatmap(plate)
    group_chart = make_group_chart(stats)

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
  border-left: 5px solid {"var(--good)" if z_prime >= .5 else "var(--warn)" if z_prime >= 0 else "var(--bad)"};
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
  <a href="#statistics">Statistics</a>
  <a href="#raw-heatmap">Raw Heatmap</a>
  <a href="#z-heatmap">Z-score Heatmap</a>
  <a href="#passing-wells">Candidate Hits</a>
  <a href="#averages">Group Averages</a>
</nav>
<main>
  <h1>{html.escape(title)}</h1>
  <div class="subtitle">
<strong>Sample:</strong> {html.escape(sample_name)}<br>
<strong>Source:</strong> {html.escape(csv_path.name)}<br>
<strong>Report generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
</div>

  <div class="cards">
    <div class="card"><div class="label">Valid wells</div><div class="value">{int(plate.count().sum())}</div></div>
    <div class="card"><div class="label">Plate average</div><div class="value">{np.nanmean(plate.values):.5f}</div></div>
    <div class="card"><div class="label">Plate StDev</div><div class="value">{np.nanstd(plate.values, ddof=1):.5f}</div></div>
    <div class="card"><div class="label">Z' factor</div><div class="value">{z_prime:.4f}</div></div>
  </div>

  <section class="qc">
    <h2>QC assessment: {qc_label}</h2>
    <p>{qc_message}</p>
    <p class="note">
      Z' comparison: <strong>{html.escape(Z_PRIME_NEGATIVE)}</strong> versus
      <strong>{html.escape(Z_PRIME_POSITIVE)}</strong>.
      Formula: 1 − 3(σ₁ + σ₂) / |μ₁ − μ₂|.
    </p>
  </section>

  <div id="overview"></div>

  <details id="plate" open>
    <summary>Raw plate values</summary>
    <div class="content table-wrap">{plate_table}</div>
  </details>

  <details id="statistics" open>
    <summary>Group statistics</summary>
    <div class="content table-wrap">{stats_table}</div>
  </details><details id="raw-heatmap" open>
    <summary>Raw measurement heatmap</summary>
    <div class="content"><img src="{raw_heatmap}" alt="Raw plate measurement heatmap"></div>
  </details>

  <details id="z-heatmap">
    <summary>Plate Z-score heatmap</summary>
    <div class="content"><img src="{z_heatmap}" alt="Plate Z-score heatmap"></div>
  </details>

  <details id="passing-wells" open>
    <summary>Candidate hit wells</summary>
    <div class="content">
      <div class="threshold-note">
        Controls: <strong>E12, F12, G12 and H12</strong><br>
        Plate mean: <strong>{control_mean:.6f}</strong><br>
        Plate StDev: <strong>{control_sd:.6f}</strong><br>
        Hit rule: plate Z-score &gt; <strong>{applied_zscore_threshold:.3f}</strong>
        {" (highest plate Z-score among controls E12:H12)" if zscore_threshold is None else " (user-supplied threshold)"}
      </div>
      <div class="table-wrap">{passing_wells_table}</div>
    </div>
  </details>

  

  <details id="averages">
    <summary>Group averages</summary>
    <div class="content"><img src="{group_chart}" alt="Group average bar chart"></div>
  </details>

  <footer>
    To change the Z' comparison, edit <code>Z_PRIME_NEGATIVE</code> and
    <code>Z_PRIME_POSITIVE</code> near the top of the script.
  </footer>
</main>
</body>
</html>"""

    output_path.write_text(html_doc, encoding="utf-8")

    stats_export = stats.reset_index()
    stats_export.loc[len(stats_export)] = {
        "Group": f"Z' ({Z_PRIME_NEGATIVE} vs {Z_PRIME_POSITIVE})",
        "Average": z_prime,
    }
    stats_export.to_csv(output_path.with_name(output_path.stem + "_statistics.csv"), index=False)
    passing_wells.to_csv(
        output_path.with_name(output_path.stem + "_passing_wells.csv"),
        index=False,
    )

    print(f"HTML report: {output_path.resolve()}")
    print(f"Statistics: {output_path.with_name(output_path.stem + '_statistics.csv').resolve()}")
    print(stats)
    print(f"Z' ({Z_PRIME_NEGATIVE} vs {Z_PRIME_POSITIVE}): {z_prime:.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a 96-well plate HTML QC report.")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("plate_report.html"))
    parser.add_argument("--title", default="96-Well Plate QC Report")
    parser.add_argument("--sample-name", default="Unknown Sample",
                        help="Sample name displayed in the report")
    parser.add_argument(
        "--zscore-threshold",
        type=float,
        default=None,
        help=(
            "Plate Z-score required to pass. "
            "Default: highest plate Z-score among control wells E12:H12."
        ),
    )
    args = parser.parse_args()

    if not args.csv_file.exists():
        parser.error(f"CSV file not found: {args.csv_file}")

    generate_html(args.csv_file, args.output, args.title, args.sample_name, args.zscore_threshold)


if __name__ == "__main__":
    main()
