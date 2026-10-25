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
