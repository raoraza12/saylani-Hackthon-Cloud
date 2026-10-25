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
