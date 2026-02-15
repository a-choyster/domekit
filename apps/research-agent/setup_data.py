"""Bootstrap sample data for the research-agent demo.

Creates:
  - data/research.db   with `projects` and `findings` tables
  - data/*.md          sample project brief documents

Run from the repo root:
    python apps/research-agent/setup_data.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "research.db"


def create_database() -> None:
    """Create research.db with sample projects and findings."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            status      TEXT NOT NULL,
            lead        TEXT NOT NULL,
            budget      REAL NOT NULL,
            start_date  TEXT NOT NULL,
            description TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id            INTEGER PRIMARY KEY,
            project_id    INTEGER NOT NULL REFERENCES projects(id),
            date          TEXT NOT NULL,
            summary       TEXT NOT NULL,
            confidential  INTEGER NOT NULL DEFAULT 0
        )
    """)

    projects = [
        (1, "Project Aurora", "active", "Dr. Elena Vasquez", 420000,
         "2025-01-15", "On-device federated learning for medical imaging without transmitting patient data."),
        (2, "Project Basalt", "active", "Dr. James Okonkwo", 310000,
         "2025-03-01", "Low-power edge inference chips designed for always-on sensor arrays."),
        (3, "Project Caldera", "completed", "Dr. Mei Zhang", 185000,
         "2024-06-10", "Homomorphic encryption benchmarks for real-time analytics workloads."),
        (4, "Project Drift", "active", "Dr. Raj Patel", 540000,
         "2025-05-20", "Privacy-preserving synthetic data generation for drug-interaction research."),
        (5, "Project Echo", "on-hold", "Dr. Sara Lindqvist", 270000,
         "2025-02-28", "Acoustic anomaly detection in industrial equipment using local models."),
        (6, "Project Fathom", "active", "Dr. Kofi Mensah", 390000,
         "2025-07-01", "Submarine cable sensor network with air-gapped analysis pipeline."),
        (7, "Project Granite", "planning", "Dr. Yuki Tanaka", 150000,
         "2026-01-10", "On-device large-language-model distillation for embedded robotics."),
    ]
    cur.executemany(
        "INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)", projects
    )

    findings = [
        (1, 1, "2025-04-12", "Federated round convergence improved 18% with gradient compression.", 0),
        (2, 1, "2025-06-03", "Patient cohort #7 shows anomalous tumor markers in retrained model.", 1),
        (3, 2, "2025-05-15", "RISC-V prototype achieves 4.2 TOPS/W on INT8 workloads.", 0),
        (4, 2, "2025-07-20", "Thermal throttling observed above 38C ambient in fanless config.", 0),
        (5, 3, "2024-09-05", "HE overhead reduced to 12x vs plaintext for aggregation queries.", 0),
        (6, 3, "2024-11-18", "Identified side-channel leak in vendor library v2.3 — patch pending.", 1),
        (7, 4, "2025-08-02", "Synthetic dataset passes KS-test parity with real clinical trial data.", 0),
        (8, 4, "2025-09-14", "FDA pre-submission feedback: need provenance chain for generated records.", 1),
        (9, 5, "2025-04-30", "Baseline model detects bearing faults with 94.7% recall on test rig.", 0),
        (10, 6, "2025-09-01", "Air-gapped transfer protocol validated at 2.4 Gbps over fiber.", 0),
        (11, 6, "2025-10-10", "Sensor node firmware vulnerability disclosed to vendor under NDA.", 1),
        (12, 7, "2026-01-25", "Initial distillation run: 3B-param model fits in 1.8 GB quantised.", 0),
    ]
    cur.executemany(
        "INSERT OR REPLACE INTO findings VALUES (?, ?, ?, ?, ?)", findings
    )

    conn.commit()
    conn.close()
    print(f"  Created {DB_PATH}  (7 projects, 12 findings)")


def create_markdown_files() -> None:
    """Write sample project-brief markdown documents into data/."""
    briefs = {
        "aurora-brief.md": """\
# Project Aurora — Brief

**Lead:** Dr. Elena Vasquez
**Status:** Active | **Budget:** $420,000

## Objective
Develop a federated-learning pipeline that trains medical-imaging models
across hospital sites *without* transmitting raw patient data.

## Key Constraints
- All gradient aggregation must happen on-device.
- No image pixels may leave the originating node.
- Model updates are differentially private (epsilon < 2.0).

## Milestones
| Quarter | Target |
|---------|--------|
| Q1 2025 | Prototype round-trip on 3 simulated sites |
| Q2 2025 | Gradient compression integration |
| Q3 2025 | Clinical partner onboarding (2 hospitals) |
""",
        "basalt-brief.md": """\
# Project Basalt — Brief

**Lead:** Dr. James Okonkwo
**Status:** Active | **Budget:** $310,000

## Objective
Design a low-power RISC-V inference accelerator targeting always-on
sensor arrays in industrial IoT environments.

## Key Constraints
- Peak power envelope: 500 mW.
- Must sustain INT8 throughput of 4 TOPS/W.
- Fanless operation up to 45 C ambient.

## Milestones
| Quarter | Target |
|---------|--------|
| Q1 2025 | RTL simulation complete |
| Q2 2025 | FPGA prototype on Xilinx Zynq |
| Q3 2025 | Tape-out decision |
""",
        "drift-brief.md": """\
# Project Drift — Brief

**Lead:** Dr. Raj Patel
**Status:** Active | **Budget:** $540,000

## Objective
Build a privacy-preserving synthetic-data generator that produces
realistic drug-interaction datasets without exposing real patient records.

## Key Constraints
- Output must pass two-sample Kolmogorov-Smirnov test vs real data.
- Full provenance chain required for FDA pre-submission.
- Generation runs entirely on local GPU cluster — no cloud.

## Milestones
| Quarter | Target |
|---------|--------|
| Q2 2025 | Generator v1 on internal cluster |
| Q3 2025 | Statistical parity validation |
| Q4 2025 | FDA pre-submission package |
""",
    }

    for filename, content in briefs.items():
        path = DATA_DIR / filename
        path.write_text(content)
        print(f"  Created {path}")


def main() -> None:
    print("Setting up research-agent demo data ...\n")
    create_database()
    create_markdown_files()
    print("\nDone. Run 'domekit run apps/research-agent' to start the agent.")


if __name__ == "__main__":
    main()
