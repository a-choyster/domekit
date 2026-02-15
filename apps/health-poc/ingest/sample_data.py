"""Generate ~90 days of realistic sample health data as CSV files."""

from __future__ import annotations

import csv
import os
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ACTIVITY_TYPES = ["running", "cycling", "walking", "swimming"]

# Rough per-activity parameter ranges
ACTIVITY_PARAMS: dict[str, dict] = {
    "running": {
        "duration": (20, 60),
        "distance": (3.0, 12.0),
        "hr": (130, 175),
        "cal_per_min": (10, 14),
    },
    "cycling": {
        "duration": (30, 90),
        "distance": (10.0, 40.0),
        "hr": (110, 160),
        "cal_per_min": (8, 12),
    },
    "walking": {
        "duration": (20, 60),
        "distance": (1.5, 5.0),
        "hr": (85, 120),
        "cal_per_min": (4, 6),
    },
    "swimming": {
        "duration": (20, 50),
        "distance": (0.5, 2.5),
        "hr": (120, 165),
        "cal_per_min": (9, 13),
    },
}


def _rand(low: float, high: float) -> float:
    return round(random.uniform(low, high), 2)


def generate_activities(start: date, days: int) -> list[dict]:
    """Generate activity records.  ~4-6 activities per week."""
    rows: list[dict] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        # Randomly decide how many activities today (0-2, weighted toward 1)
        count = random.choices([0, 1, 2], weights=[0.3, 0.55, 0.15])[0]
        for _ in range(count):
            atype = random.choice(ACTIVITY_TYPES)
            p = ACTIVITY_PARAMS[atype]
            duration = round(_rand(*p["duration"]))
            distance = _rand(*p["distance"])
            avg_hr = round(_rand(*p["hr"]))
            calories = round(duration * _rand(*p["cal_per_min"]))
            rows.append(
                {
                    "date": day.isoformat(),
                    "type": atype,
                    "duration_min": duration,
                    "distance_km": distance,
                    "avg_hr": avg_hr,
                    "calories": calories,
                }
            )
    return rows


def generate_daily_metrics(start: date, days: int) -> list[dict]:
    """Generate one row per day of daily health metrics."""
    rows: list[dict] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        rows.append(
            {
                "date": day.isoformat(),
                "steps": random.randint(3000, 15000),
                "resting_hr": random.randint(55, 75),
                "sleep_hours": round(_rand(5.0, 9.5), 1),
                "active_minutes": random.randint(15, 120),
                "stress_score": random.randint(1, 10),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def main() -> None:
    random.seed(42)
    end = date.today()
    start = end - timedelta(days=90)

    activities = generate_activities(start, 90)
    daily = generate_daily_metrics(start, 90)

    write_csv(DATA_DIR / "activities.csv", activities)
    write_csv(DATA_DIR / "daily_metrics.csv", daily)
    print("Sample data generation complete.")


if __name__ == "__main__":
    main()
