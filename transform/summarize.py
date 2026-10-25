import sqlite3, pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
conn = sqlite3.connect(BASE / "indus_weave.db")
def q(sql):
    df = pd.read_sql(sql, conn)
    print(df.to_string(index=False))
    print()
    return df

print("=== Headcount total by month (Q1 sum) ===")
q01 = pd.read_csv(BASE / "analytics" / "results" / "q01_headcount.csv")
print(q01.groupby("payroll_month")["headcount"].sum().to_string())
print()
print("=== OT by month (Q5 sum) ===")
q05 = pd.read_csv(BASE / "analytics" / "results" / "q05_overtime_compare.csv")
print(q05.groupby("payroll_month")[["computed_hours","approved_hours","paid_hours"]].sum().to_string())
print()
print("=== OT by plant (Q5 sum) ===")
print(q05.groupby("plant")[["computed_hours","approved_hours","paid_hours"]].sum().to_string())
print()
print("=== OT paid cost by month ===")
q("SELECT payroll_month, SUM(amount) AS ot_cost, SUM(units) AS ot_hours_paid FROM fact_payroll_line WHERE component='OVERTIME' GROUP BY payroll_month ORDER BY payroll_month")
print("=== Total payroll EARNING by month ===")
q("SELECT payroll_month, SUM(amount) AS earning_cost FROM fact_payroll_line WHERE component_type='EARNING' GROUP BY payroll_month ORDER BY payroll_month")
print("=== Q6 count by month ===")
q06 = pd.read_csv(BASE / "analytics" / "results" / "q06_paid_exceeds_computed.csv")
print(q06.groupby("payroll_month").size().to_string())
print("Q6 total excess hours:", q06["excess_hours"].sum())
print()
print("=== Q8 distinct employees ===")
q08 = pd.read_csv(BASE / "analytics" / "results" / "q08_paid_after_separation.csv")
print("rows:", len(q08), "distinct emp:", q08.emp_id.nunique())
print(q08.groupby("emp_id")["total_amount_in_month"].sum().sort_values(ascending=False).head(20).to_string())
print("Q8 total amount:", q08.total_amount_in_month.sum())
print()
print("=== Q7 ===")
print(pd.read_csv(BASE / "analytics" / "results" / "q07_paid_zero_attendance.csv").to_string(index=False))
print()
print("=== Approved OT with zero computed OT that day ===")
q("""
SELECT COUNT(*) AS approved_requests,
       SUM(CASE WHEN COALESCE(a.overtime_hours,0)=0 THEN 1 ELSE 0 END) AS approved_with_zero_computed,
       SUM(CASE WHEN a.status IS NULL THEN 1 ELSE 0 END) AS approved_with_no_attendance_row,
       SUM(CASE WHEN a.status='Present' AND COALESCE(a.overtime_hours,0)=0 THEN 1 ELSE 0 END) AS present_but_zero_ot
FROM fact_overtime_approved o
LEFT JOIN fact_attendance_daily a ON a.emp_id=o.emp_id AND a.work_date=o.ot_date
""")
print("=== Approved OT by month vs computed ===")
q("""
SELECT substr(o.ot_date,1,7) AS month, COUNT(*) AS n_approved, SUM(o.approved_hours) AS approved_hours,
       COALESCE(SUM(a.overtime_hours),0) AS computed_ot_on_those_days
FROM fact_overtime_approved o
LEFT JOIN fact_attendance_daily a ON a.emp_id=o.emp_id AND a.work_date=o.ot_date
GROUP BY month ORDER BY month
""")
print("=== Attendance status by month ===")
q("SELECT substr(work_date,1,7) AS month, status, COUNT(*) AS days FROM fact_attendance_daily GROUP BY month, status ORDER BY month, status")
print("=== Late arrivals by plant/month ===")
q("SELECT substr(work_date,1,7) AS month, plant, SUM(is_late) AS late_days FROM fact_attendance_daily GROUP BY month, plant ORDER BY month, plant")
print("=== Missing punch by plant ===")
q("SELECT plant, COUNT(*) AS missing_days FROM fact_attendance_daily WHERE status='Missing Punch' GROUP BY plant")
print("=== SITE late before/after correction check: late days Jul-Sep by plant ===")
q("SELECT plant, SUM(is_late) AS late_days, COUNT(*) AS present_days FROM fact_attendance_daily WHERE status='Present' AND work_date>='2026-07-01' GROUP BY plant")
