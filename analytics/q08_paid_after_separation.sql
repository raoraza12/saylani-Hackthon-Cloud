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
