"""Ingest CSV health data into a SQLite database."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "health.db"


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            duration_min REAL NOT NULL,
            distance_km REAL NOT NULL,
            avg_hr INTEGER NOT NULL,
            calories INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            steps INTEGER NOT NULL,
            resting_hr INTEGER NOT NULL,
            sleep_hours REAL NOT NULL,
            active_minutes INTEGER NOT NULL,
            stress_score INTEGER NOT NULL
        );
        """
    )


def load_csv(conn: sqlite3.Connection, table: str, csv_path: Path) -> int:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return 0
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    col_names = ", ".join(columns)
    conn.executemany(
        f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
        [tuple(row[c] for c in columns) for row in rows],
    )
    conn.commit()
    return len(rows)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Remove existing DB so we start fresh
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    try:
        create_tables(conn)

        activities_csv = DATA_DIR / "activities.csv"
        metrics_csv = DATA_DIR / "daily_metrics.csv"

        if not activities_csv.exists() or not metrics_csv.exists():
            print("CSV files not found. Run sample_data.py first.")
            return

        n = load_csv(conn, "activities", activities_csv)
        print(f"Loaded {n} rows into activities")

        n = load_csv(conn, "daily_metrics", metrics_csv)
        print(f"Loaded {n} rows into daily_metrics")

        print(f"Database ready at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
