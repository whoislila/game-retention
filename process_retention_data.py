#!/usr/bin/env python3
"""Aggregate player-level retention data into cohort-level metrics."""

import argparse
import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


RETENTION_COLUMNS = ("ret1", "ret3", "ret7")
INPUT_COLUMNS = {"date", "max_level", "total_pay", *RETENTION_COLUMNS}
OUTPUT_COLUMNS = (
    "cohort_date",
    "players",
    "ret1_players",
    "ret1_rate_pct",
    "ret3_players",
    "ret3_rate_pct",
    "ret7_players",
    "ret7_rate_pct",
    "paying_players",
    "payer_rate_pct",
    "total_revenue",
    "arpu",
    "avg_max_level",
)


def _parse_nonnegative_number(value, column, line_number):
    """Parse a numeric CSV field and reject negative or non-finite values."""
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {column} value on line {line_number}") from error

    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{column} must be a finite non-negative number on line {line_number}")
    return number


def aggregate_cohorts(input_path):
    """Read player rows and return metrics grouped by cohort date."""
    # Keep additive totals here; rates and averages are computed once per cohort below.
    cohorts = defaultdict(
        lambda: {
            "players": 0,
            "ret1_players": 0,
            "ret3_players": 0,
            "ret7_players": 0,
            "paying_players": 0,
            "total_revenue": 0.0,
            "total_max_level": 0.0,
        }
    )

    with input_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = INPUT_COLUMNS - set(reader.fieldnames or ())
        if missing_columns:
            raise ValueError(
                f"CSV is missing required columns: {', '.join(sorted(missing_columns))}"
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                cohort_date = datetime.strptime(row["date"], "%Y/%m/%d").date()
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid date on line {line_number}; expected YYYY/M/D") from error

            max_level = _parse_nonnegative_number(row["max_level"], "max_level", line_number)
            total_pay = _parse_nonnegative_number(row["total_pay"], "total_pay", line_number)
            retention = {}
            # Retention flags represent whether each player returned on that specific day.
            for column in RETENTION_COLUMNS:
                try:
                    value = int(row[column])
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid {column} value on line {line_number}; expected 0 or 1"
                    ) from error
                if value not in (0, 1):
                    raise ValueError(f"{column} must be 0 or 1 on line {line_number}")
                retention[column] = value

            cohort = cohorts[cohort_date]
            cohort["players"] += 1
            cohort["total_max_level"] += max_level
            cohort["total_revenue"] += total_pay
            cohort["paying_players"] += total_pay > 0
            for column, value in retention.items():
                cohort[f"{column}_players"] += value

    if not cohorts:
        raise ValueError(f"No data rows found in {input_path}")

    summaries = []
    for cohort_date, cohort in sorted(cohorts.items()):
        players = cohort["players"]
        # Divide by all players in the cohort so rates, ARPU, and level averages share one base.
        summary = {
            "cohort_date": cohort_date.isoformat(),
            "players": players,
            "total_revenue": f"{cohort['total_revenue']:.2f}",
            "arpu": f"{cohort['total_revenue'] / players:.2f}",
            "avg_max_level": f"{cohort['total_max_level'] / players:.2f}",
            "payer_rate_pct": f"{cohort['paying_players'] / players * 100:.2f}",
        }
        summary["paying_players"] = cohort["paying_players"]
        for column in RETENTION_COLUMNS:
            retained = cohort[f"{column}_players"]
            summary[f"{column}_players"] = retained
            summary[f"{column}_rate_pct"] = f"{retained / players * 100:.2f}"
        summaries.append(summary)

    return summaries


def write_cohort_summary(summaries, output_path):
    """Write cohort metrics to a CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        # Explicit field order keeps the generated report stable for downstream consumers.
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(summaries)


def main():
    """Parse command-line options and run the cohort aggregation pipeline."""
    project_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=project_dir / "data" / "block.csv",
        help="CSV file containing player-level retention data",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_dir / "data" / "retention_summary.csv",
        help="path for the generated cohort summary",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")
    # Avoid truncating the source file if the same path is supplied for both arguments.
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output paths must be different")

    try:
        summaries = aggregate_cohorts(args.input)
        write_cohort_summary(summaries, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(f"Saved cohort summary to {args.output}")


if __name__ == "__main__":
    main()
