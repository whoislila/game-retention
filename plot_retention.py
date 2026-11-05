#!/usr/bin/env python3
"""Plot day-1, day-3, and day-7 retention by cohort date."""

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt


RETENTION_COLUMNS = ("ret1", "ret3", "ret7")
RETENTION_LABELS = {
    "ret1": "Day 1",
    "ret3": "Day 3",
    "ret7": "Day 7",
}


def load_cohorts(csv_path):
    """Load player-level rows and sum their retention flags by cohort date."""
    cohorts = defaultdict(lambda: {"players": 0, **{column: 0 for column in RETENTION_COLUMNS}})

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        required_columns = {"date", *RETENTION_COLUMNS}
        missing_columns = required_columns - set(reader.fieldnames or ())
        if missing_columns:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing_columns))}")

        for line_number, row in enumerate(reader, start=2):
            try:
                cohort_date = datetime.strptime(row["date"], "%Y/%m/%d").date()
                retention = {column: int(row[column]) for column in RETENTION_COLUMNS}
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid date or retention value on line {line_number}") from error

            if any(value not in (0, 1) for value in retention.values()):
                raise ValueError(f"Retention values must be 0 or 1 on line {line_number}")

            cohort = cohorts[cohort_date]
            cohort["players"] += 1
            for column, value in retention.items():
                cohort[column] += value

    if not cohorts:
        raise ValueError(f"No data rows found in {csv_path}")

    return dict(sorted(cohorts.items()))


def plot_retention(cohorts, output_path):
    """Render cohort retention percentages and save the chart."""
    dates = list(cohorts)
    sample_sizes = [cohorts[cohort_date]["players"] for cohort_date in dates]
    # Include each cohort's sample size so small cohorts are visible to chart readers.
    tick_labels = [
        f"{cohort_date.strftime('%b %-d')}\nn={sample_size}"
        for cohort_date, sample_size in zip(dates, sample_sizes)
    ]

    figure, axis = plt.subplots(figsize=(11, 6))
    for column in RETENTION_COLUMNS:
        # Each flag sum is the retained-player count; normalize it by its cohort size.
        rates = [
            cohorts[cohort_date][column] / cohorts[cohort_date]["players"] * 100
            for cohort_date in dates
        ]
        axis.plot(dates, rates, marker="o", linewidth=2, label=RETENTION_LABELS[column])

    axis.set_title("Player Retention by Cohort")
    axis.set_xlabel("Cohort date (number of players)")
    axis.set_ylabel("Retained players (%)")
    axis.set_ylim(0, 100)
    axis.set_xticks(dates, tick_labels)
    axis.grid(axis="y", linestyle="--", alpha=0.4)
    axis.legend(title="Retention")
    figure.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def main():
    """Parse command-line options, load cohort data, and create the retention chart."""
    project_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=project_dir / "data" / "block.csv",
        help="CSV file containing cohort dates and retention flags",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_dir / "retention.png",
        help="path for the generated chart (default: retention.png)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")

    try:
        cohorts = load_cohorts(args.input)
        plot_retention(cohorts, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(f"Saved retention chart to {args.output}")


if __name__ == "__main__":
    main()
