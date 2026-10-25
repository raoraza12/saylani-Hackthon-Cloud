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
