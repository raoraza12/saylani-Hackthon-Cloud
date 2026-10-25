import sqlite3, csv
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
DB = BASE / "indus_weave.db"
AQ = BASE / "analytics"
OUT = AQ / "results"
OUT.mkdir(parents=True, exist_ok=True)

QUERIES = {}

QUERIES["q01_headcount"] = """
-- Q1: Month-end headcount by plant and department, all six months.
-- Department is the department on the last day of the month, or on the
-- last working day (separation date) if the employee left during that month.
WITH months(month_end) AS (
  SELECT '2026-04-30' UNION ALL SELECT '2026-05-31' UNION ALL SELECT '2026-06-30'
  UNION ALL SELECT '2026-07-31' UNION ALL SELECT '2026-08-31' UNION ALL SELECT '2026-09-30'
)
SELECT
  m.month_end,
  substr(m.month_end, 1, 7) AS payroll_month,
  d.plant,
  d.dept_id,
  d.dept_name,
  COUNT(DISTINCT e.emp_id) AS headcount
FROM months m
JOIN dim_employee e
  ON e.hire_date <= m.month_end
  AND (e.separation_date IS NULL OR e.separation_date > m.month_end)
  AND e.valid_from <= CASE WHEN e.separation_date IS NOT NULL AND e.separation_date < m.month_end
                           THEN e.separation_date ELSE m.month_end END
  AND e.valid_to >= CASE WHEN e.separation_date IS NOT NULL AND e.separation_date < m.month_end
                         THEN e.separation_date ELSE m.month_end END
JOIN dim_department d ON d.dept_id = e.dept_id
GROUP BY m.month_end, d.plant, d.dept_id, d.dept_name
ORDER BY m.month_end, d.plant, d.dept_name;
"""

QUERIES["q02_attrition"] = """
-- Q2: Monthly attrition rate by department (separations / average headcount).
-- Average headcount = (headcount at start of month + headcount at end of month) / 2.
WITH month_ends(month_end) AS (
  SELECT '2026-03-31' UNION ALL SELECT '2026-04-30' UNION ALL SELECT '2026-05-31'
  UNION ALL SELECT '2026-06-30' UNION ALL SELECT '2026-07-31' UNION ALL SELECT '2026-08-31'
  UNION ALL SELECT '2026-09-30'
),
headcount AS (
  SELECT m.month_end, e.dept_id, COUNT(DISTINCT e.emp_id) AS hc
  FROM month_ends m
  JOIN dim_employee e
    ON e.hire_date <= m.month_end
    AND (e.separation_date IS NULL OR e.separation_date > m.month_end)
    AND e.valid_from <= CASE WHEN e.separation_date IS NOT NULL AND e.separation_date < m.month_end
                             THEN e.separation_date ELSE m.month_end END
    AND e.valid_to >= CASE WHEN e.separation_date IS NOT NULL AND e.separation_date < m.month_end
                           THEN e.separation_date ELSE m.month_end END
  GROUP BY m.month_end, e.dept_id
),
headcount_lag AS (
  SELECT month_end, dept_id, hc,
         LAG(hc) OVER (PARTITION BY dept_id ORDER BY month_end) AS prev_hc
  FROM headcount
),
separations AS (
  SELECT substr(e.separation_date, 1, 7) AS sep_month, e.dept_id, COUNT(DISTINCT e.emp_id) AS separations
  FROM (SELECT DISTINCT emp_id, separation_date, dept_id FROM dim_employee WHERE separation_date IS NOT NULL) e
  WHERE e.separation_date BETWEEN '2026-04-01' AND '2026-09-30'
    AND EXISTS (
      SELECT 1 FROM dim_employee x
      WHERE x.emp_id = e.emp_id AND x.valid_from <= e.separation_date AND x.valid_to >= e.separation_date
        AND x.dept_id = e.dept_id
    )
  GROUP BY sep_month, e.dept_id
)
SELECT
  substr(h.month_end, 1, 7) AS payroll_month,
  d.plant, d.dept_id, d.dept_name,
  h.hc AS month_end_headcount,
  h.prev_hc AS month_start_headcount,
  COALESCE(s.separations, 0) AS separations,
  CASE WHEN (h.hc + h.prev_hc) > 0
       THEN COALESCE(s.separations, 0) * 1.0 / ((h.hc + h.prev_hc) / 2.0)
       ELSE NULL END AS attrition_rate
FROM headcount_lag h
JOIN dim_department d ON d.dept_id = h.dept_id
LEFT JOIN separations s ON s.sep_month = substr(h.month_end, 1, 7) AND s.dept_id = h.dept_id
WHERE h.month_end >= '2026-04-30'
ORDER BY payroll_month, d.plant, d.dept_name;
"""

QUERIES["q03_absenteeism"] = """
-- Q3: Absenteeism rate by plant and month, excluding approved leave.
-- Denominator: Present + Absent + Missing Punch (On Leave, Holiday, Weekly Off excluded).
SELECT
  substr(work_date, 1, 7) AS payroll_month,
  plant,
  SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_days,
  SUM(CASE WHEN status IN ('Present', 'Absent', 'Missing Punch') THEN 1 ELSE 0 END) AS scheduled_days,
  CASE WHEN SUM(CASE WHEN status IN ('Present', 'Absent', 'Missing Punch') THEN 1 ELSE 0 END) > 0
       THEN SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) * 1.0
            / SUM(CASE WHEN status IN ('Present', 'Absent', 'Missing Punch') THEN 1 ELSE 0 END)
       ELSE NULL END AS absenteeism_rate
FROM fact_attendance_daily
GROUP BY payroll_month, plant
ORDER BY payroll_month, plant;
"""

QUERIES["q04_late_arrivals"] = """
-- Q4: 10 employees with the most late arrivals, and their department.
-- Late = check-in more than 10 minutes after shift start, Present working days only.
SELECT
  a.emp_id,
  MAX(e.full_name) AS full_name,
  a.dept_id,
  d.dept_name,
  d.plant,
  COUNT(*) AS late_days,
  SUM(a.late_minutes) AS total_late_minutes
FROM fact_attendance_daily a
JOIN dim_department d ON d.dept_id = a.dept_id
JOIN (SELECT DISTINCT emp_id, full_name FROM dim_employee) e ON e.emp_id = a.emp_id
WHERE a.is_late = 1
GROUP BY a.emp_id, a.dept_id, d.dept_name, d.plant
ORDER BY late_days DESC, total_late_minutes DESC
LIMIT 10;
"""

QUERIES["q05_overtime_compare"] = """
-- Q5: Overtime hours computed from punches vs approved vs paid, by department and month.
-- Computed: fact_attendance_daily.overtime_hours (Present only).
-- Approved: fact_overtime_approved.approved_hours, department via SCD on ot_date.
-- Paid: fact_payroll_line units where component = 'OVERTIME' (rule 20).
WITH computed AS (
  SELECT dept_id, substr(work_date, 1, 7) AS month, SUM(overtime_hours) AS computed_hours
  FROM fact_attendance_daily GROUP BY dept_id, month
),
approved AS (
  SELECT e.dept_id, substr(o.ot_date, 1, 7) AS month, SUM(o.approved_hours) AS approved_hours
  FROM fact_overtime_approved o
  JOIN dim_employee e ON e.emp_id = o.emp_id AND e.valid_from <= o.ot_date AND e.valid_to >= o.ot_date
  GROUP BY e.dept_id, month
),
paid AS (
  SELECT dept_id, payroll_month AS month, SUM(units) AS paid_hours
  FROM fact_payroll_line WHERE component = 'OVERTIME' GROUP BY dept_id, month
),
keys AS (
  SELECT dept_id, month FROM computed UNION
  SELECT dept_id, month FROM approved UNION
  SELECT dept_id, month FROM paid
)
SELECT
  k.month AS payroll_month,
  d.plant, k.dept_id, d.dept_name,
  COALESCE(c.computed_hours, 0) AS computed_hours,
  COALESCE(a.approved_hours, 0) AS approved_hours,
  COALESCE(p.paid_hours, 0) AS paid_hours,
  COALESCE(p.paid_hours, 0) - COALESCE(c.computed_hours, 0) AS paid_minus_computed_hours
FROM keys k
JOIN dim_department d ON d.dept_id = k.dept_id
LEFT JOIN computed c ON c.dept_id = k.dept_id AND c.month = k.month
LEFT JOIN approved a ON a.dept_id = k.dept_id AND a.month = k.month
LEFT JOIN paid p ON p.dept_id = k.dept_id AND p.month = k.month
ORDER BY k.month, d.plant, d.dept_name;
"""

QUERIES["q06_paid_exceeds_computed"] = """
-- Q6: Departments where paid overtime exceeds computed overtime by more than 15%.
WITH computed AS (
  SELECT dept_id, substr(work_date, 1, 7) AS month, SUM(overtime_hours) AS computed_hours
  FROM fact_attendance_daily GROUP BY dept_id, month
),
paid AS (
  SELECT dept_id, payroll_month AS month, SUM(units) AS paid_hours
  FROM fact_payroll_line WHERE component = 'OVERTIME' GROUP BY dept_id, month
)
SELECT
  p.month AS payroll_month,
  d.plant, p.dept_id, d.dept_name,
  COALESCE(c.computed_hours, 0) AS computed_hours,
  p.paid_hours,
  p.paid_hours - COALESCE(c.computed_hours, 0) AS excess_hours,
  CASE WHEN COALESCE(c.computed_hours, 0) > 0
       THEN (p.paid_hours - c.computed_hours) * 1.0 / c.computed_hours
       ELSE NULL END AS excess_ratio
FROM paid p
LEFT JOIN computed c ON c.dept_id = p.dept_id AND c.month = p.month
JOIN dim_department d ON d.dept_id = p.dept_id
WHERE (COALESCE(c.computed_hours, 0) > 0 AND p.paid_hours > c.computed_hours * 1.15)
   OR (COALESCE(c.computed_hours, 0) = 0 AND p.paid_hours > 0)
ORDER BY payroll_month, excess_hours DESC;
"""

QUERIES["q07_paid_zero_attendance"] = """
-- Q7: Employees paid in a month with zero attendance in that month.
-- Zero attendance = no Present days in that month.
WITH paid_months AS (
  SELECT DISTINCT emp_id, payroll_month FROM fact_payroll_line
),
present_days AS (
  SELECT emp_id, substr(work_date, 1, 7) AS month,
         SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_days
  FROM fact_attendance_daily GROUP BY emp_id, month
)
SELECT
  p.emp_id,
  MAX(e.full_name) AS full_name,
  p.payroll_month,
  COALESCE(a.present_days, 0) AS present_days
FROM paid_months p
LEFT JOIN present_days a ON a.emp_id = p.emp_id AND a.month = p.payroll_month
JOIN (SELECT DISTINCT emp_id, full_name FROM dim_employee) e ON e.emp_id = p.emp_id
WHERE COALESCE(a.present_days, 0) = 0
ORDER BY p.payroll_month, p.emp_id;
"""

QUERIES["q08_paid_after_separation"] = """
-- Q8: Employees still receiving pay after their separation date.
-- Separation date is the last day worked, so pay in a later month is after separation.
WITH emp_sep AS (
  SELECT DISTINCT emp_id, full_name, separation_date FROM dim_employee WHERE separation_date IS NOT NULL
)
SELECT
  p.emp_id,
  s.full_name,
  s.separation_date,
  p.payroll_month,
  SUM(p.amount) AS total_amount_in_month,
  COUNT(*) AS payroll_lines
FROM fact_payroll_line p
JOIN emp_sep s ON s.emp_id = p.emp_id
WHERE p.payroll_month > substr(s.separation_date, 1, 7)
GROUP BY p.emp_id, s.full_name, s.separation_date, p.payroll_month
ORDER BY p.payroll_month, p.emp_id;
"""

QUERIES["q09_payroll_cost_per_employee"] = """
-- Q9: Payroll cost per employee by department, with month-over-month change.
-- Cost = sum of EARNING lines. Employees paid = distinct employees with payroll in that dept/month.
WITH monthly AS (
  SELECT dept_id, payroll_month AS month,
         SUM(CASE WHEN component_type = 'EARNING' THEN amount ELSE 0 END) AS total_cost,
         COUNT(DISTINCT emp_id) AS employees_paid
  FROM fact_payroll_line GROUP BY dept_id, month
)
SELECT
  month AS payroll_month,
  d.plant, m.dept_id, d.dept_name,
  total_cost,
  employees_paid,
  CASE WHEN employees_paid > 0 THEN total_cost * 1.0 / employees_paid ELSE NULL END AS cost_per_employee,
  LAG(CASE WHEN employees_paid > 0 THEN total_cost * 1.0 / employees_paid ELSE NULL END)
    OVER (PARTITION BY m.dept_id ORDER BY month) AS prev_cost_per_employee,
  CASE WHEN employees_paid > 0 THEN total_cost * 1.0 / employees_paid ELSE NULL END
    - LAG(CASE WHEN employees_paid > 0 THEN total_cost * 1.0 / employees_paid ELSE NULL END)
      OVER (PARTITION BY m.dept_id ORDER BY month) AS mom_change,
  CASE WHEN LAG(CASE WHEN employees_paid > 0 THEN total_cost * 1.0 / employees_paid ELSE NULL END)
             OVER (PARTITION BY m.dept_id ORDER BY month) > 0
       THEN (CASE WHEN employees_paid > 0 THEN total_cost * 1.0 / employees_paid ELSE NULL END
             - LAG(CASE WHEN employees_paid > 0 THEN total_cost * 1.0 / employees_paid ELSE NULL END)
               OVER (PARTITION BY m.dept_id ORDER BY month))
            / LAG(CASE WHEN employees_paid > 0 THEN total_cost * 1.0 / employees_paid ELSE NULL END)
              OVER (PARTITION BY m.dept_id ORDER BY month)
       ELSE NULL END AS mom_change_pct
FROM monthly m
JOIN dim_department d ON d.dept_id = m.dept_id
ORDER BY month, d.plant, d.dept_name;
"""

QUERIES["q10_leave_overuse"] = """
-- Q10: Employees whose approved Annual leave days in these six months
-- already exceed their full-year entitlement.
-- Leave days exclude Sundays and plant holidays (fact_leave_day already excludes them).
SELECT
  l.emp_id,
  MAX(e.full_name) AS full_name,
  COUNT(*) AS annual_leave_days_apr_sep,
  MAX(s.annual_leave_entitlement) AS annual_leave_entitlement,
  COUNT(*) - MAX(s.annual_leave_entitlement) AS excess_days
FROM fact_leave_day l
JOIN (SELECT DISTINCT emp_id, full_name FROM dim_employee) e ON e.emp_id = l.emp_id
JOIN stg_employees s ON s.emp_id = l.emp_id
WHERE l.leave_type = 'Annual'
  AND l.leave_date BETWEEN '2026-04-01' AND '2026-09-30'
GROUP BY l.emp_id
HAVING COUNT(*) > MAX(s.annual_leave_entitlement)
ORDER BY excess_days DESC, l.emp_id;
"""

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for name, sql in QUERIES.items():
        (AQ / f"{name}.sql").write_text(sql.strip() + "\n")
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        out = OUT / f"{name}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"{name}: {len(rows)} rows -> {out}")
        for r in rows[:5]:
            print("  ", r)
    conn.close()

if __name__ == "__main__":
    main()
