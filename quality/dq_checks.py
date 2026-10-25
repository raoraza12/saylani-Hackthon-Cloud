import sqlite3, pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
conn = sqlite3.connect(BASE / "indus_weave.db")
def run(name, sql, expect=0):
    try:
        df = pd.read_sql(sql, conn)
        val = int(df.iloc[0,0]) if len(df) else 0
    except Exception as e:
        print(name, "ERROR", e)
        return (name, None, "ERROR", str(e))
    status = "PASS" if val == expect else "FAIL"
    print(f"{status}: {name} = {val} (expected {expect})")
    return (name, val, status, "")

checks = []
checks.append(run("pk_dim_employee_unique", "SELECT COUNT(*) - COUNT(DISTINCT employee_key) FROM dim_employee"))
checks.append(run("pk_dim_department_unique", "SELECT COUNT(*) - COUNT(DISTINCT dept_id) FROM dim_department"))
checks.append(run("pk_dim_shift_unique", "SELECT COUNT(*) - COUNT(DISTINCT shift_code) FROM dim_shift"))
checks.append(run("pk_fact_attendance_unique", "SELECT COUNT(*) - COUNT(DISTINCT emp_id || '|' || work_date) FROM fact_attendance_daily"))
checks.append(run("fk_attendance_dept", "SELECT COUNT(*) FROM fact_attendance_daily a LEFT JOIN dim_department d ON d.dept_id=a.dept_id WHERE d.dept_id IS NULL"))
checks.append(run("fk_attendance_employee_key", "SELECT COUNT(*) FROM fact_attendance_daily a LEFT JOIN dim_employee e ON e.employee_key=a.employee_key WHERE a.employee_key IS NOT NULL AND e.employee_key IS NULL"))
checks.append(run("fk_payroll_dept", "SELECT COUNT(*) FROM fact_payroll_line p LEFT JOIN dim_department d ON d.dept_id=p.dept_id WHERE d.dept_id IS NULL"))
checks.append(run("notnull_attendance_emp_date", "SELECT COUNT(*) FROM fact_attendance_daily WHERE emp_id IS NULL OR work_date IS NULL"))
checks.append(run("status_accepted_values", "SELECT COUNT(*) FROM fact_attendance_daily WHERE status NOT IN ('Present','Absent','On Leave','Holiday','Weekly Off','Missing Punch')"))
checks.append(run("leave_type_accepted", "SELECT COUNT(*) FROM fact_leave_day WHERE leave_type NOT IN ('Annual','Casual','Sick')"))
checks.append(run("pay_component_accepted", "SELECT COUNT(*) FROM fact_payroll_line WHERE component NOT IN ('BASIC','HOUSE_RENT','MEDICAL','CONVEYANCE','OVERTIME','INCOME_TAX','EOBI','ABSENCE_DEDUCTION','LOAN_INSTALLMENT')"))
checks.append(run("negative_worked_hours", "SELECT COUNT(*) FROM fact_attendance_daily WHERE worked_hours < 0"))
checks.append(run("worked_over_16h", "SELECT COUNT(*) FROM fact_attendance_daily WHERE worked_hours > 16"))
checks.append(run("scd_overlaps", """
SELECT COUNT(*) FROM dim_employee a JOIN dim_employee b
ON a.emp_id=b.emp_id AND a.employee_key < b.employee_key
AND a.valid_from <= b.valid_to AND b.valid_from <= a.valid_to
"""))
checks.append(run("scd_valid_to_before_from", "SELECT COUNT(*) FROM dim_employee WHERE valid_to < valid_from"))
checks.append(run("ot_not_half_hour", "SELECT COUNT(*) FROM fact_attendance_daily WHERE overtime_hours*2 != CAST(overtime_hours*2 AS INTEGER)"))
# Reconciliation checks are computed in Python, not SQL
import sqlite3 as s
cur = conn.cursor()
def cnt(table):
    return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
rec = [
    ("recon_employees", 1316, cnt("stg_employees") + cnt("stg_dedup_log")),
    ("recon_punches", 345280, cnt("stg_punches") + cnt("stg_rejected_punches")),
    ("recon_leave_requests", 5372, cnt("stg_leave_requests")),
    ("recon_departments", 25, cnt("dim_department")),
    ("recon_payroll", 53617, cnt("fact_payroll_line")),
    ("recon_overtime_total", 22098, cnt("stg_overtime_requests")),
]
for name, raw, staged in rec:
    status = "PASS" if raw == staged else "FAIL"
    print(f"{status}: {name} raw={raw} staged+rejected={staged}")
    checks.append((name, staged, status, f"raw={raw}"))

# Save dq_results
rows = []
for name, val, status, note in checks:
    rows.append({"check_name": name, "result_value": val, "status": status, "note": note})
pd.DataFrame(rows).to_sql("dq_results", conn, if_exists="replace", index=False)
conn.close()
print(f"\nDQ: {sum(1 for _,_,s,_ in checks if s=='PASS')}/{len(checks)} PASS")
