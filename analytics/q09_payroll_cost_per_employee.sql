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
