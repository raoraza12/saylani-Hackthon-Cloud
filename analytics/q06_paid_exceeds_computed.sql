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
