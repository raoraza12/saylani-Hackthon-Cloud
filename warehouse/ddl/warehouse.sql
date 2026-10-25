-- Stage 4: Star schema (PostgreSQL / SQLite compatible, see README note on SQLite indexes).
-- Attendance belongs to Workforce; Payroll consumes attendance results.

CREATE TABLE dim_department (
  dept_id TEXT PRIMARY KEY,
  dept_name TEXT NOT NULL,
  plant TEXT NOT NULL,
  cost_center TEXT,
  previous_name TEXT,
  renamed_on TEXT
);

CREATE TABLE dim_shift (
  shift_code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  crosses_midnight INTEGER NOT NULL,
  grace_minutes INTEGER NOT NULL
);

CREATE TABLE dim_date (
  date TEXT PRIMARY KEY,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  day INTEGER NOT NULL,
  day_of_week TEXT NOT NULL,
  is_weekend INTEGER NOT NULL,
  is_sunday INTEGER NOT NULL
);

CREATE TABLE dim_employee (
  employee_key INTEGER PRIMARY KEY,
  emp_id TEXT NOT NULL,
  full_name TEXT,
  gender TEXT,
  hire_date TEXT,
  separation_date TEXT,
  dept_id TEXT NOT NULL REFERENCES dim_department(dept_id),
  designation TEXT,
  grade TEXT,
  basic_salary REAL,
  change_reason TEXT,
  valid_from TEXT NOT NULL,
  valid_to TEXT NOT NULL,
  is_current INTEGER NOT NULL
  -- SCD Type 2: valid_to = day before next record starts; last record valid_to = 2262-01-01 (open-ended in SQLite/pandas range).
  -- SCD join: fact.work_date BETWEEN dim.valid_from AND dim.valid_to
);

CREATE TABLE fact_attendance_daily (
  emp_id TEXT NOT NULL,
  work_date TEXT NOT NULL,
  employee_key INTEGER REFERENCES dim_employee(employee_key),
  dept_id TEXT REFERENCES dim_department(dept_id),
  plant TEXT,
  shift_code TEXT REFERENCES dim_shift(shift_code),
  status TEXT NOT NULL CHECK (status IN ('Present','Absent','On Leave','Holiday','Weekly Off','Missing Punch')),
  check_in TEXT,
  check_out TEXT,
  worked_hours REAL NOT NULL DEFAULT 0,
  late_minutes INTEGER NOT NULL DEFAULT 0,
  early_minutes INTEGER NOT NULL DEFAULT 0,
  is_late INTEGER NOT NULL DEFAULT 0,
  is_early INTEGER NOT NULL DEFAULT 0,
  overtime_hours REAL NOT NULL DEFAULT 0,
  is_sunday INTEGER NOT NULL DEFAULT 0,
  is_holiday INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (emp_id, work_date)
);

CREATE TABLE fact_leave_day (
  emp_id TEXT NOT NULL,
  leave_date TEXT NOT NULL,
  leave_type TEXT NOT NULL,
  request_id TEXT,
  plant TEXT,
  dept_id TEXT REFERENCES dim_department(dept_id),
  PRIMARY KEY (emp_id, leave_date, leave_type)
);

CREATE TABLE fact_overtime_approved (
  request_id TEXT PRIMARY KEY,
  emp_id TEXT NOT NULL,
  ot_date TEXT NOT NULL,
  requested_hours REAL,
  approved_hours REAL,
  status TEXT,
  approver_id TEXT,
  requested_at TEXT
);

CREATE TABLE fact_payroll_line (
  line_id TEXT PRIMARY KEY,
  payroll_month TEXT NOT NULL,
  emp_id TEXT NOT NULL,
  component TEXT NOT NULL,
  component_type TEXT NOT NULL,
  units REAL,
  amount REAL,
  dept_id TEXT REFERENCES dim_department(dept_id),
  plant TEXT
);
