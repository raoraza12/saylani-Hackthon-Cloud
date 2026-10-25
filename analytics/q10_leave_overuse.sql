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
