# Indus Weave HR Pipeline

## Team
Solo participant: Talha Khan

## Setup (clean machine)
```bash
pip install -r requirements.txt
# Put the dataset files in data/ (from https://github.com/aiwithqasim/data-hackathon)
# employees.csv, employment_history.csv, departments.csv, shifts.json,
# shift_roster.csv, device_mapping.csv, biometric_punches.csv, holidays.csv,
# leave_requests.json, overtime_requests.csv, payroll_lines.csv, applications.csv
python run_pipeline.py
```
This runs, in order: Stage 1 ingestion, Stages 2-3 cleaning and attendance,
Stage 4 warehouse, Stage 5 queries (Q1-Q10, CSVs in `analytics/results/`),
Stage 6 data-quality checks (`dq_results` table), ERD and slides.

## Stack decision
Python 3 + pandas + SQLite. The case study explicitly allows SQLite if a team
cannot run PostgreSQL, and SQLite avoids a setup failure overnight. SQL is kept
portable, and `warehouse/ddl/warehouse.sql` shows the full PK/FK star schema.
In SQLite, primary keys are enforced with unique indexes created after load;
foreign-key integrity is verified by the Stage 6 checks (22/22 pass).

## Design decisions and assumptions
- Raw: every file loaded exactly as delivered, all columns as TEXT, nothing
  flattened yet. Each raw table gets `_source_file`, `_loaded_at`, `_row_hash`.
  Idempotent: re-running deletes that source file's old raw rows first.
  Total raw rows: 472,907, matching the case study counts.
- Employees: duplicate `emp_id` kept by latest `updated_at` (50 merged, logged
  in `stg_dedup_log`). Dates parsed from YYYY-MM-DD, DD/MM/YYYY and DD-Mon-YYYY.
  Department names normalised (trim, case, spaces) and mapped via
  `departments.csv`, including previous names (Procurement → D04, Processing → D15).
- Employment history is the source of truth for department/grade/salary.
  `valid_to` = day before the next record starts; the last record is open-ended.
  One same-day case (E11259, Hire and Salary Revision both 2026-07-01) is dropped
  as superseded and logged in `stg_history_superseded`, otherwise its derived
  valid range would be empty.
- Roster: missing weeks use the previous week's shift. Roster weeks run Monday-Sunday.
- Punches: mapped by `device_id + device_user_id`. Unmapped punches (6,962)
  go to `stg_rejected_punches`. Duplicates within 2 minutes (16,175) also go there,
  so raw = staging + rejected: 345,280 = 322,143 + 23,137.
- **Faulty device: DEV-SITE-01, clock 60 minutes fast from 2026-07-01.**
  Found by comparing first-punch median deviation from shift start by device
  and month, DAY shift: Apr-Jun all devices median -7 min; Jul-Sep DEV-SITE-01
  median +53 min, others -7 min; daily: 30 Jun median -8 min, 1 Jul median +54 min.
  Correction: subtract 60 minutes from DEV-SITE-01 punches on/after 2026-07-01,
  before shift-date assignment. Without this, SITE late arrivals and overtime
  after shift end would be overstated from July onward.
- Attendance: one row per employee per scheduled day, Apr-Sep 2026.
  Night shifts belong to their start date; check-in = first punch, check-out =
  last punch in the shift interval (buffer ±3 hours). Status priority follows
  data_dictionary.md rule 12. Late/early counted only on Present working days,
  >10 minutes. Overtime = minutes after shift end, rounded down to half-hours;
  Sunday/holiday work = all worked hours, rounded down to half-hours.
  On Leave days with punches are recorded as On Leave (priority order) with
  worked/OT set to 0, to avoid double-counting leave and work.
  Missing Punch days have worked/OT = 0, because check-out is unknown.
- Leave: counts only if Manager and HR both Approved and not cancelled.
  Leave days exclude Sundays and plant holidays. `days_requested` is not trusted.
- Overtime approved: only `status = Approved`. Payroll OVERTIME `units` = hours paid.
  Payroll cost = sum of EARNING lines.
- Q2 average headcount = (headcount at start + headcount at end of month) / 2.
- Q3 absenteeism denominator = Present + Absent + Missing Punch (leave, holiday,
  weekly off excluded).
- Q9 cost per employee = total EARNING cost / distinct employees paid in that
  department and month, with month-over-month change via LAG.
- Q8: pay in a month after the separation month counts as pay after separation;
  pay in the separation month itself is legitimate (last day worked in that month).

## Results (summary)
- Headcount: 1,199 (Apr) → 1,176 (Sep) - falling, so OT rise is not headcount growth.
- Computed OT: 29,116 hours; approved/paid OT: 36,402 hours; gap: 7,286 hours.
- OT bill: PKR 2.81m (Apr) → PKR 3.48m (Sep).
- DQ: 22/22 checks pass, in `dq_results`.
- CFO findings: `presentation/cfo_findings.md`, slides: `presentation/slides.pdf` (6 slides).

## Deliverables in this repo
- `ingestion/load_raw.py` - Stage 1
- `transform/build_pipeline.py` - Stages 2-4
- `transform/profile.py`, `transform/profile_device*.py` - profiling and faulty-device evidence
- `warehouse/ddl/warehouse.sql`, `warehouse/erd.png` - Stage 4
- `analytics/q01_headcount.sql` … `analytics/q10_leave_overuse.sql`, `analytics/results/*.csv` - Stage 5
- `quality/dq_checks.py` - Stage 6 (22/22 automated data quality test suite)
- `run_pipeline.py` - Master orchestrator: one-command end-to-end rebuild
- `presentation/cfo_findings.md`, `presentation/slides.pdf` - CFO executive briefing
- `presentation/cfo_dashboard.html` - Interactive 3D Cyber-Forensic Operations Center (run `powershell -File serve.ps1` to launch on `http://localhost:8080/`)
- `serve.ps1` - Instant zero-dependency local web server for dashboard and telemetry exploration
- Bonus Next.js dashboard: `bonus/next-dashboard/` (run `npm install` then `npm run dev`, dashboard at `/`, admin editor at `/admin`). Build tested with Next 14.2.35.
- Bonus results: 1,400 applications, 74 hired (5.3%), median time to hire 33 days. Biggest drop is Interviewed to Offered (only 34.2% move forward).

## Deadline
Submit repo link before 05:00 AM, 25 Oct 2026. Target submit 04:30.
