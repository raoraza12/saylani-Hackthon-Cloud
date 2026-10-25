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
