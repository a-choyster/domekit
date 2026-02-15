#!/usr/bin/env python3
"""Set up sample data for the file-analyst demo app.

Creates sample report files and a SQLite index database that the
file-analyst agent can query through DomeKit's policy-controlled tools.
"""

import os
import sqlite3
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPORTS_DIR = APP_DIR / "data" / "reports"
DB_PATH = APP_DIR / "data" / "index.db"

SAMPLE_REPORTS: dict[str, dict] = {
    "q4-2025-revenue.txt": {
        "description": "Q4 2025 quarterly revenue report",
        "category": "financial",
        "date_added": "2026-01-15",
        "content": """\
Q4 2025 Revenue Report
======================
Period: October 1 - December 31, 2025

Summary
-------
Total revenue: $4.2M (up 18% QoQ)
Recurring revenue: $3.1M (74% of total)
New customer revenue: $680K
Expansion revenue: $420K

Segment Breakdown
-----------------
Enterprise: $2.8M (67%) - 12 new contracts signed
Mid-market: $980K (23%) - 34 new accounts
Self-serve: $420K (10%) - steady growth from PLG motion

Key Highlights
--------------
- Enterprise deal size averaged $233K, up from $195K in Q3.
- Churn rate dropped to 2.1%, lowest in company history.
- APAC region contributed $610K, a 42% increase over Q3.
""",
    },
    "q3-2025-revenue.txt": {
        "description": "Q3 2025 quarterly revenue report",
        "category": "financial",
        "date_added": "2025-10-12",
        "content": """\
Q3 2025 Revenue Report
======================
Period: July 1 - September 30, 2025

Summary
-------
Total revenue: $3.56M (up 11% QoQ)
Recurring revenue: $2.6M (73% of total)
New customer revenue: $540K
Expansion revenue: $380K

Segment Breakdown
-----------------
Enterprise: $2.3M (65%) - 9 new contracts signed
Mid-market: $840K (24%) - 28 new accounts
Self-serve: $420K (12%) - consistent quarter

Key Highlights
--------------
- Launched APAC sales team; region brought in $430K.
- Average enterprise deal size: $195K.
- Churn rate: 2.8%, down from 3.4% in Q2.
""",
    },
    "project-atlas-summary.txt": {
        "description": "Project Atlas migration initiative status summary",
        "category": "engineering",
        "date_added": "2026-01-28",
        "content": """\
Project Atlas - Migration Summary
=================================
Last updated: January 28, 2026

Objective
---------
Migrate core platform from monolithic architecture to a service-oriented
design with independently deployable components.

Status: ON TRACK (Phase 2 of 3)

Completed (Phase 1)
--------------------
- Extracted authentication service (shipped Oct 2025)
- Extracted notification service (shipped Nov 2025)
- API gateway deployed with traffic splitting at 80/20

In Progress (Phase 2)
---------------------
- Billing service extraction: 70% complete, ETA Feb 2026
- Data pipeline decoupling: 45% complete, ETA Mar 2026
- Legacy database read-replica cutover: scheduled for Feb 15

Risks
-----
- Billing service has undocumented coupling to the reporting module.
- Two senior engineers on the data pipeline team are on leave in March.
""",
    },
    "security-audit-jan2026.txt": {
        "description": "January 2026 security audit findings",
        "category": "security",
        "date_added": "2026-02-03",
        "content": """\
Security Audit Report - January 2026
=====================================
Auditor: Internal AppSec Team
Scope: Production infrastructure and application layer

Executive Summary
-----------------
Overall risk posture: MODERATE
Critical findings: 0
High findings: 1
Medium findings: 3
Low findings: 7

High-Severity Finding
---------------------
H-1: API rate limiting not enforced on /api/v2/export endpoint.
     Impact: Potential data exfiltration at scale.
     Remediation: Deploy rate limiter; patch shipped Jan 22.
     Status: RESOLVED

Medium-Severity Findings
-------------------------
M-1: TLS 1.0 still accepted on internal load balancer.
M-2: Service account keys not rotated in 180+ days.
M-3: Container images using outdated base (ubuntu:22.04 vs 24.04).

Recommendations
---------------
- Enforce 90-day key rotation policy.
- Upgrade base images across all services by end of Q1.
- Schedule external penetration test for Q2 2026.
""",
    },
    "hiring-plan-2026.txt": {
        "description": "2026 headcount and hiring plan",
        "category": "operations",
        "date_added": "2026-01-20",
        "content": """\
2026 Hiring Plan
================
Approved by: VP of People, January 20, 2026

Headcount Targets
-----------------
Current headcount: 142
Target EOY headcount: 185
Net new hires planned: 48 (accounting for ~5 attrition)

Breakdown by Department
-----------------------
Engineering: +22 (8 backend, 6 frontend, 4 infra, 2 ML, 2 QA)
Sales: +12 (6 AE, 4 SDR, 2 SE)
Product: +5 (3 PM, 2 designer)
Customer Success: +6 (4 CSM, 2 support)
G&A: +3 (1 finance, 1 legal, 1 recruiting)

Timeline
--------
Q1: 14 hires (focus on engineering backfill + sales)
Q2: 16 hires (ML team buildout + APAC sales)
Q3: 10 hires (product + CS scaling)
Q4: 8 hires (remaining roles, backfills)

Budget
------
Total recruiting budget: $960K
Average cost-per-hire target: $20K
Relocation budget: $150K (6 relo packages estimated)
""",
    },
}


def main() -> None:
    # Create reports directory
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created directory: {REPORTS_DIR}")

    # Write sample report files
    for filename, info in SAMPLE_REPORTS.items():
        filepath = REPORTS_DIR / filename
        filepath.write_text(info["content"])
        print(f"  Wrote: {filepath.name}")

    # Create SQLite index database
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            date_added TEXT NOT NULL
        )
    """)

    for filename, info in SAMPLE_REPORTS.items():
        cursor.execute(
            "INSERT INTO files (filename, description, category, date_added) VALUES (?, ?, ?, ?)",
            (filename, info["description"], info["category"], info["date_added"]),
        )

    conn.commit()
    conn.close()
    print(f"\nCreated database: {DB_PATH}")
    print(f"  Indexed {len(SAMPLE_REPORTS)} files in 'files' table")
    print("\nSetup complete.")


if __name__ == "__main__":
    main()
