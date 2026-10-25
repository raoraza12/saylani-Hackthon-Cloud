import json, pandas as pd, numpy as np
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "data"
def show(df, name):
    print(f"\n=== {name} {df.shape} ===")
    print(df.head(3).to_string())
    print("nulls:", df.isna().sum().to_dict())

emp = pd.read_csv(D/"employees.csv", dtype=str, keep_default_na=False)
show(emp, "employees")
print("emp_id duplicates:", emp.duplicated("emp_id").sum(), "unique:", emp.emp_id.nunique())
print("plant:", emp.plant.value_counts().to_dict())
print("department raw:", emp.department.value_counts().head(30).to_dict())
print("status:", emp.status.value_counts().to_dict())
print("employment_type:", emp.employment_type.value_counts().to_dict())
print("hire sample:", emp.hire_date.head(20).tolist())
print("updated_at sample:", emp.updated_at.head(5).tolist())

dept = pd.read_csv(D/"departments.csv", dtype=str, keep_default_na=False)
show(dept, "departments")
print(dept.to_string())

hist = pd.read_csv(D/"employment_history.csv", dtype=str, keep_default_na=False)
show(hist, "employment_history")
print("change_reason:", hist.change_reason.value_counts().to_dict())
print("dept_id:", hist.dept_id.value_counts().to_dict())

shifts = json.load(open(D/"shifts.json"))
print("\nshifts:", shifts)

roster = pd.read_csv(D/"shift_roster.csv", dtype=str, keep_default_na=False)
show(roster, "roster")
print("shift_code:", roster.shift_code.value_counts().to_dict())
print("week_start range:", roster.week_start.min(), roster.week_start.max())

dm = pd.read_csv(D/"device_mapping.csv", dtype=str, keep_default_na=False)
show(dm, "device_mapping")
print("device_id:", dm.device_id.value_counts().to_dict())
print("dup device+user:", dm.duplicated(["device_id","device_user_id"]).sum())

hol = pd.read_csv(D/"holidays.csv", dtype=str, keep_default_na=False)
show(hol, "holidays")

ot = pd.read_csv(D/"overtime_requests.csv", dtype=str, keep_default_na=False)
show(ot, "overtime")
print("ot status:", ot.status.value_counts().to_dict())

pay = pd.read_csv(D/"payroll_lines.csv", dtype=str, keep_default_na=False)
show(pay, "payroll")
print("component:", pay.component.value_counts().to_dict())
print("component_type:", pay.component_type.value_counts().to_dict())
print("payroll_month:", sorted(pay.payroll_month.unique()))

leave = json.load(open(D/"leave_requests.json"))
print(f"\nleave_requests: {len(leave)} sample:", json.dumps(leave[0], indent=2)[:2000])
from collections import Counter
print("leave types:", Counter(r["leave"]["type"] for r in leave))
print("cancelled:", sum(1 for r in leave if r.get("cancelled_at")))
# approval actions
acts = Counter()
for r in leave:
    for a in r.get("approvals", []):
        acts[(a.get("step"), a.get("action"))] += 1
print("approvals:", acts)

# Punches: device-level check-in deviation probe
pun = pd.read_csv(D/"biometric_punches.csv", dtype=str, keep_default_na=False)
show(pun, "punches")
print("punches per device:", pun.device_id.value_counts().to_dict())
pun["punch_time"] = pd.to_datetime(pun["punch_time"])
# Map to employee, then for each device, look at earliest punch per employee per day, time of day
mp = dm.set_index(["device_id","device_user_id"])["emp_id"].to_dict()
pun["emp_id"] = [mp.get((d,u)) for d,u in zip(pun.device_id, pun.device_user_id)]
print("unmapped punches:", pun.emp_id.isna().sum())
mapped = pun.dropna(subset=["emp_id"]).copy()
mapped["date"] = mapped.punch_time.dt.date
first = mapped.sort_values("punch_time").groupby(["emp_id","date"]).first().reset_index()
first["tod_minutes"] = first.punch_time.dt.hour*60 + first.punch_time.dt.minute
print("\nFirst punch time-of-day mean/median by device:")
print(first.groupby("device_id")["tod_minutes"].agg(["count","mean","median"]).to_string())
print("\nFirst punch hour distribution by device:")
print(pd.crosstab(first.device_id, first.punch_time.dt.hour))
