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
