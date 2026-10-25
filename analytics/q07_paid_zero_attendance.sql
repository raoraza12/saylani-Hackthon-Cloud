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
