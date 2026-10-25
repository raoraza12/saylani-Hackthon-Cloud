"""Indus Weave HR Pipeline — Stages 2-5 + DQ.
SQLite implementation (case study allows SQLite). Tables are prefixed:
raw_* (Stage 1), stg_* (Stage 2-3), dim_*/fact_* (Stage 4), dq_results (Stage 6).
All business rules from data_dictionary.md. See README for assumptions.
Faulty device: DEV-SITE-01, clock 60 minutes fast from 2026-07-01.
Evidence: first-punch median deviation vs shift start, DAY shift:
  Apr-Jun: all devices median -7 min.
  Jul-Sep: DEV-SITE-01 median +53 min, others -7 min.
  Daily: 2026-06-30 median -8 min, 2026-07-01 median +54 min.
Correction: subtract 60 minutes from DEV-SITE-01 punches on/after 2026-07-01.
"""
import json, sqlite3, hashlib
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
DB = BASE / "indus_weave.db"
OUT = BASE / "analytics" / "results"
OUT.mkdir(parents=True, exist_ok=True)
PERIOD_START = pd.Timestamp("2026-04-01")
PERIOD_END = pd.Timestamp("2026-09-30")
PLANT_CODE = {"Head Office": "HO", "Korangi Plant": "KOR", "SITE Plant": "SITE", "Faisalabad Plant": "FSD"}
CODE_PLANT = {v: k for k, v in PLANT_CODE.items()}

def parse_date(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return pd.NaT
    s = str(s).strip()
    if not s:
        return pd.NaT
    return pd.to_datetime(s, format="mixed", dayfirst=True, errors="coerce")

def norm_dept(s):
    return " ".join(str(s).strip().lower().split())

def main():
    conn = sqlite3.connect(DB)
    # ---------- Departments ----------
    dept = pd.read_csv(DATA / "departments.csv", dtype=str, keep_default_na=False)
    dept["dept_name"] = dept["dept_name"].str.strip()
    dept["plant"] = dept["plant"].str.strip()
    dept_map = {}
    for r in dept.itertuples():
        dept_map[norm_dept(r.dept_name)] = r.dept_id
        if r.previous_name.strip():
            dept_map[norm_dept(r.previous_name)] = r.dept_id
    dept.to_sql("dim_department", conn, if_exists="replace", index=False)
    print("dim_department:", len(dept))

    # ---------- Shifts ----------
    shifts_list = json.load(open(DATA / "shifts.json"))["shifts"]
    shifts_df = pd.DataFrame(shifts_list)
    shifts_df.to_sql("dim_shift", conn, if_exists="replace", index=False)
    shifts = {s["shift_code"]: s for s in shifts_list}
    print("dim_shift:", shifts_df.to_dict("records"))

    # ---------- Employees dedup ----------
    emp_raw = pd.read_csv(DATA / "employees.csv", dtype=str, keep_default_na=False)
    emp_raw["updated_at_dt"] = pd.to_datetime(emp_raw["updated_at"], errors="coerce")
    emp_raw = emp_raw.sort_values(["emp_id", "updated_at_dt"])
    dedup_log = []
    for emp_id, g in emp_raw.groupby("emp_id"):
        if len(g) > 1:
            kept = g.iloc[-1]
            for _, r in g.iloc[:-1].iterrows():
                dedup_log.append({"emp_id": emp_id, "merged_emp_id_row": r["emp_id"],
                                  "reason": "duplicate emp_id, kept latest updated_at",
                                  "kept_updated_at": str(kept["updated_at"]), "dropped_updated_at": str(r["updated_at"])})
    emp = emp_raw.drop_duplicates("emp_id", keep="last").copy()
    print(f"employees: raw {len(emp_raw)} -> deduped {len(emp)} (duplicates removed {len(emp_raw)-len(emp)})")
    pd.DataFrame(dedup_log).to_sql("stg_dedup_log", conn, if_exists="replace", index=False)
    for c in ["date_of_birth", "hire_date", "separation_date"]:
        emp[c] = emp[c].apply(parse_date)
    emp["department_clean"] = emp["department"].str.strip()
    emp["dept_id_emp"] = emp["department"].apply(lambda x: dept_map.get(norm_dept(x)))
    emp["plant_clean"] = emp["plant"].str.strip()
    emp["annual_leave_entitlement"] = pd.to_numeric(emp["annual_leave_entitlement"], errors="coerce")
    emp_clean = emp[["emp_id", "full_name", "gender", "date_of_birth", "hire_date", "separation_date",
                     "plant_clean", "department_clean", "dept_id_emp", "designation", "grade",
                     "employment_type", "status", "annual_leave_entitlement", "updated_at"]].copy()
    emp_clean.columns = ["emp_id", "full_name", "gender", "date_of_birth", "hire_date", "separation_date",
                         "plant", "department", "dept_id", "designation", "grade",
                         "employment_type", "status", "annual_leave_entitlement", "updated_at"]
    emp_clean.to_sql("stg_employees", conn, if_exists="replace", index=False)
    print("employees with unmapped dept:", emp_clean["dept_id"].isna().sum())
    if emp_clean["dept_id"].isna().any():
        print(emp_clean[emp_clean["dept_id"].isna()][["emp_id", "department", "plant"]].to_string())

    # ---------- Employment history SCD2 ----------
    hist = pd.read_csv(DATA / "employment_history.csv", dtype=str, keep_default_na=False)
    hist["effective_from"] = pd.to_datetime(hist["effective_from"], errors="coerce")
    hist["effective_to_raw"] = pd.to_datetime(hist["effective_to"], errors="coerce")
    hist = hist.sort_values(["emp_id", "effective_from"])
    hist["valid_to"] = hist.groupby("emp_id")["effective_from"].shift(-1) - pd.Timedelta(days=1)
    hist["valid_to"] = hist["valid_to"].fillna(pd.Timestamp("2262-01-01"))
    hist["valid_from"] = hist["effective_from"]
    hist["is_current"] = (hist["valid_to"] == pd.Timestamp("2262-01-01")).astype(int)
    # Same-day superseded history: e.g. E11259 has Hire and Salary Revision both
    # effective 2026-07-01, so the first record's derived valid_to (day before)
    # is before its valid_from. Drop it, keep the later record for that day.
    superseded = hist[hist["valid_to"] < hist["valid_from"]].copy()
    if len(superseded):
        superseded.to_sql("stg_history_superseded", conn, if_exists="replace", index=False)
        print(f"history same-day superseded rows dropped: {len(superseded)}")
        hist = hist[hist["valid_to"] >= hist["valid_from"]].copy()
    hist["basic_salary"] = pd.to_numeric(hist["basic_salary"], errors="coerce")
    # SCD2 overlaps check: valid_to should be >= valid_from
    print("history rows with valid_to < valid_from:", (hist["valid_to"] < hist["valid_from"]).sum())
    # dim_employee: join name etc from emp_clean
    emp_lookup = emp_clean.set_index("emp_id")
    dim_rows = []
    for r in hist.itertuples():
        e = emp_lookup.loc[r.emp_id] if r.emp_id in emp_lookup.index else None
        dim_rows.append({
            "emp_id": r.emp_id,
            "full_name": e["full_name"] if e is not None else None,
            "gender": e["gender"] if e is not None else None,
            "hire_date": e["hire_date"] if e is not None else None,
            "separation_date": e["separation_date"] if e is not None else None,
            "dept_id": r.dept_id, "designation": r.designation, "grade": r.grade,
            "basic_salary": r.basic_salary, "change_reason": r.change_reason,
            "valid_from": r.valid_from, "valid_to": r.valid_to, "is_current": r.is_current,
        })
    dim_emp = pd.DataFrame(dim_rows)
    dim_emp = dim_emp.sort_values(["emp_id", "valid_from"]).reset_index(drop=True)
    dim_emp.insert(0, "employee_key", range(1, len(dim_emp) + 1))
    # store dates as text YYYY-MM-DD for SQL
    for c in ["hire_date", "separation_date", "valid_from", "valid_to"]:
        dim_emp[c] = pd.to_datetime(dim_emp[c]).dt.strftime("%Y-%m-%d")
        dim_emp.loc[dim_emp[c] == "NaT", c] = None
    dim_emp.to_sql("dim_employee", conn, if_exists="replace", index=False)
    print("dim_employee (SCD2 rows):", len(dim_emp))

    # ---------- Dates ----------
    dates = pd.date_range("2026-04-01", "2026-10-31")
    dim_date = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "year": dates.year, "month": dates.month, "day": dates.day,
        "day_of_week": dates.day_name(), "is_weekend": (dates.weekday >= 5).astype(int),
        "is_sunday": (dates.weekday == 6).astype(int),
    })
    dim_date.to_sql("dim_date", conn, if_exists="replace", index=False)

    # ---------- Holidays ----------
    hol = pd.read_csv(DATA / "holidays.csv", dtype=str, keep_default_na=False)
    hol["holiday_date"] = pd.to_datetime(hol["holiday_date"]).dt.strftime("%Y-%m-%d")
    hol.to_sql("stg_holidays", conn, if_exists="replace", index=False)
    hol_set = set()
    for r in hol.itertuples():
        if r.scope == "ALL":
            for plant in PLANT_CODE:
                hol_set.add((r.holiday_date, plant))
        else:
            plant = CODE_PLANT.get(r.scope, r.scope)
            hol_set.add((r.holiday_date, plant))
    print("holidays:", hol.to_dict("records"))

    # ---------- Roster with missing-week ffill ----------
    roster = pd.read_csv(DATA / "shift_roster.csv", dtype=str, keep_default_na=False)
    roster["week_start"] = pd.to_datetime(roster["week_start"])
    roster = roster.sort_values(["emp_id", "week_start"])
    emp_weeks = defaultdict(list)
    for r in roster.itertuples():
        emp_weeks[r.emp_id].append((r.week_start, r.shift_code))
    roster_filled = {}
    for emp_id, weeks in emp_weeks.items():
        weeks = sorted(weeks)
        # ffill over Monday steps from first to last week
        d = {}
        cur = None
        ws = weeks[0][0]
        last = weeks[-1][0]
        wdict = dict(weeks)
        while ws <= last:
            if ws in wdict:
                cur = wdict[ws]
            if cur is not None:
                d[ws] = cur
            ws += pd.Timedelta(days=7)
        roster_filled[emp_id] = d
    print("roster employees:", len(roster_filled))

    def roster_shift(emp_id, date):
        ws = date - pd.Timedelta(days=date.weekday())
        d = roster_filled.get(emp_id, {})
        if ws in d:
            return d[ws]
        # before first week: use first known shift, after last: use last known
        if d:
            if ws < min(d):
                return d[min(d)]
            return d[max(d)]
        return None

    # ---------- Leave ----------
    leave_raw = json.load(open(DATA / "leave_requests.json"))
    leave_reqs = []
    leave_steps = []
    leave_days = []
    for r in leave_raw:
        emp_id = r["employee"]["emp_id"]
        plant = r["employee"].get("plant")
        cancelled = bool(r.get("cancelled_at"))
        mgr_ok = any(a.get("approver_role") == "Manager" and a.get("action") == "Approved" for a in r.get("approvals", []))
        hr_ok = any(a.get("approver_role") == "HR" and a.get("action") == "Approved" for a in r.get("approvals", []))
        mgr_rej = any(a.get("approver_role") == "Manager" and a.get("action") == "Rejected" for a in r.get("approvals", []))
        hr_rej = any(a.get("approver_role") == "HR" and a.get("action") == "Rejected" for a in r.get("approvals", []))
        is_approved = mgr_ok and hr_ok and not mgr_rej and not hr_rej and not cancelled
        leave_reqs.append({
            "request_id": r["request_id"], "emp_id": emp_id, "plant": plant,
            "leave_type": r["leave"]["type"], "leave_from": r["leave"]["from"], "leave_to": r["leave"]["to"],
            "days_requested": r["leave"]["days_requested"], "submitted_at": r.get("submitted_at"),
            "cancelled_at": r.get("cancelled_at"), "is_approved": int(is_approved),
        })
        for a in r.get("approvals", []):
            leave_steps.append({"request_id": r["request_id"], "step": a.get("step"),
                                "approver_role": a.get("approver_role"), "approver_id": a.get("approver_id"),
                                "action": a.get("action"), "acted_at": a.get("acted_at")})
        if is_approved:
            for d in pd.date_range(r["leave"]["from"], r["leave"]["to"]):
                ds = d.strftime("%Y-%m-%d")
                if d.weekday() == 6:
                    continue
                if (ds, plant) in hol_set:
                    continue
                leave_days.append({"emp_id": emp_id, "leave_date": ds, "leave_type": r["leave"]["type"],
                                   "request_id": r["request_id"], "plant": plant})
    pd.DataFrame(leave_reqs).to_sql("stg_leave_requests", conn, if_exists="replace", index=False)
    pd.DataFrame(leave_steps).to_sql("stg_leave_approvals", conn, if_exists="replace", index=False)
    leave_days_df = pd.DataFrame(leave_days)
    leave_days_df.to_sql("fact_leave_day", conn, if_exists="replace", index=False)
    print(f"leave: requests {len(leave_reqs)}, approved {sum(x['is_approved'] for x in leave_reqs)}, leave_days {len(leave_days_df)}")

    # ---------- Punches: mapping, faulty device correction, dedup ----------
    dm = pd.read_csv(DATA / "device_mapping.csv", dtype=str, keep_default_na=False)
    mp = {(r.device_id, r.device_user_id): r.emp_id for r in dm.itertuples()}
    pun = pd.read_csv(DATA / "biometric_punches.csv", dtype=str, keep_default_na=False)
    pun["punch_time_raw"] = pd.to_datetime(pun["punch_time"])
    pun["emp_id"] = [mp.get((d, u)) for d, u in zip(pun.device_id, pun.device_user_id)]
    rejected = []
    unmapped = pun[pun["emp_id"].isna()].copy()
    for r in unmapped.itertuples():
        rejected.append({"punch_id": r.punch_id, "device_id": r.device_id, "device_user_id": r.device_user_id,
                         "punch_time": str(r.punch_time_raw), "reason": "unmapped_device_user"})
    mapped = pun.dropna(subset=["emp_id"]).copy()
    # Faulty device correction
    cutoff = pd.Timestamp("2026-07-01")
    mask = (mapped["device_id"] == "DEV-SITE-01") & (mapped["punch_time_raw"] >= cutoff)
    mapped.loc[mask, "punch_time"] = mapped.loc[mask, "punch_time_raw"] - pd.Timedelta(minutes=60)
    mapped.loc[~mask, "punch_time"] = mapped.loc[~mask, "punch_time_raw"]
    print(f"faulty device correction: {mask.sum()} DEV-SITE-01 punches from 2026-07-01 shifted -60 min")
    mapped = mapped.sort_values(["emp_id", "punch_time"])
    # 2-minute dedup, kept-first
    deduped_rows = []
    dup_count = 0
    for emp_id, g in mapped.groupby("emp_id", sort=False):
        last_kept = None
        for r in g.itertuples():
            if last_kept is not None and (r.punch_time - last_kept).total_seconds() < 120:
                dup_count += 1
                rejected.append({"punch_id": r.punch_id, "device_id": r.device_id, "device_user_id": r.device_user_id,
                                 "punch_time": str(r.punch_time), "reason": "duplicate_within_2min"})
                continue
            deduped_rows.append({"punch_id": r.punch_id, "device_id": r.device_id, "device_user_id": r.device_user_id,
                                 "emp_id": emp_id, "punch_time": r.punch_time})
            last_kept = r.punch_time
    pun_clean = pd.DataFrame(deduped_rows)
    pun_clean.to_sql("stg_punches", conn, if_exists="replace", index=False)
    pd.DataFrame(rejected).to_sql("stg_rejected_punches", conn, if_exists="replace", index=False)
    print(f"punches: raw {len(pun)} = mapped deduped {len(pun_clean)} + rejected {len(rejected)} (unmapped {len(unmapped)}, duplicates {dup_count})")
    assert len(pun) == len(pun_clean) + len(rejected), "punch reconciliation failed"

    # ---------- Attendance daily ----------
    # History dept/plant lookup per date
    hist_by_emp = defaultdict(list)
    for r in hist.itertuples():
        hist_by_emp[r.emp_id].append((r.valid_from, r.valid_to, r.dept_id))
    for k in hist_by_emp:
        hist_by_emp[k].sort()
    dept_plant = dict(zip(dept.dept_id, dept.plant))
    def dept_on_date(emp_id, date):
        for vf, vt, did in hist_by_emp.get(emp_id, []):
            if vf <= date <= vt:
                return did
        return None
    leave_set = set(zip(leave_days_df["emp_id"], leave_days_df["leave_date"])) if len(leave_days_df) else set()
    # Punches by emp, sorted
    pun_by_emp = {e: g.sort_values("punch_time") for e, g in pun_clean.groupby("emp_id")}
    att_rows = []
    unassigned_total = 0
    missing_roster = 0
    for e in emp_clean.itertuples():
        emp_id = e.emp_id
        hire = e.hire_date
        sep = e.separation_date
        if pd.isna(hire):
            continue
        start = max(hire, PERIOD_START)
        end = min(sep, PERIOD_END) if not pd.isna(sep) else PERIOD_END
        if end < start:
            continue
        emp_punches = pun_by_emp.get(emp_id)
        punch_times = emp_punches["punch_time"].tolist() if emp_punches is not None else []
        p_idx = 0
        for date in pd.date_range(start, end):
            ds = date.strftime("%Y-%m-%d")
            shift_code = roster_shift(emp_id, date)
            if shift_code is None:
                missing_roster += 1
                shift_code = "GEN"
            s = shifts[shift_code]
            sh, sm = map(int, s["start_time"].split(":"))
            eh, em = map(int, s["end_time"].split(":"))
            shift_start = date + pd.Timedelta(hours=sh, minutes=sm)
            shift_end = date + pd.Timedelta(hours=eh, minutes=em)
            if s["crosses_midnight"]:
                shift_end += pd.Timedelta(days=1)
            # collect punches in [start-3h, end+3h]
            while p_idx < len(punch_times) and punch_times[p_idx] < shift_start - pd.Timedelta(hours=3):
                p_idx += 1
                unassigned_total += 1
            day_punches = []
            while p_idx < len(punch_times) and punch_times[p_idx] <= shift_end + pd.Timedelta(hours=3):
                day_punches.append(punch_times[p_idx])
                p_idx += 1
            # Note: punches for a night shift that fall on the next calendar day are consumed here,
            # because the interval extends past midnight. The next day's interval starts later, so no double count.
            is_sunday = date.weekday() == 6
            dept_id = dept_on_date(emp_id, date)
            if dept_id is None:
                dept_id = e.dept_id
            plant = dept_plant.get(dept_id, e.plant)
            is_holiday = (ds, plant) in hol_set
            is_leave = (emp_id, ds) in leave_set
            n = len(day_punches)
            if n == 0 and is_sunday:
                status = "Weekly Off"
            elif n == 0 and is_holiday:
                status = "Holiday"
            elif is_leave:
                status = "On Leave"
            elif n >= 2:
                status = "Present"
            elif n == 1:
                status = "Missing Punch"
            else:
                status = "Absent"
            check_in = day_punches[0] if n >= 1 else None
            check_out = day_punches[-1] if n >= 2 else None
            worked_hours = 0.0
            ot_hours = 0.0
            late_minutes = 0
            early_minutes = 0
            is_late = 0
            is_early = 0
            if status == "Present":
                worked_min = (check_out - check_in).total_seconds() / 60.0
                worked_hours = worked_min / 60.0
                if is_sunday or is_holiday:
                    ot_hours = np.floor(worked_min / 30) * 0.5
                else:
                    after_min = (check_out - shift_end).total_seconds() / 60.0
                    if after_min > 0:
                        ot_hours = np.floor(after_min / 30) * 0.5
                    late = (check_in - shift_start).total_seconds() / 60.0
                    if late > 10:
                        is_late = 1
                        late_minutes = int(late)
                    early = (shift_end - check_out).total_seconds() / 60.0
                    if early > 10:
                        is_early = 1
                        early_minutes = int(early)
            att_rows.append({
                "emp_id": emp_id, "work_date": ds, "dept_id": dept_id, "plant": plant,
                "shift_code": shift_code, "status": status,
                "check_in": check_in.strftime("%Y-%m-%d %H:%M:%S") if check_in is not None else None,
                "check_out": check_out.strftime("%Y-%m-%d %H:%M:%S") if check_out is not None else None,
                "worked_hours": round(float(worked_hours), 4),
                "late_minutes": int(late_minutes), "early_minutes": int(early_minutes),
                "is_late": int(is_late), "is_early": int(is_early),
                "overtime_hours": float(ot_hours),
                "is_sunday": int(is_sunday), "is_holiday": int(is_holiday),
            })
    att = pd.DataFrame(att_rows)
    print(f"attendance_daily: {len(att)} rows, missing_roster_fallback {missing_roster}, unassigned punches skipped {unassigned_total}")
    print(att["status"].value_counts().to_dict())
    # Add employee_key via SCD join in SQL later; for now store with dept, and add key via merge
    # Merge employee_key: valid range contains work_date
    dim_emp_sql = dim_emp.copy()
    # Use pandas merge_asof per emp? Simpler: for each att row, lookup via hist (already dept, but key needed)
    # Build key map: (emp_id, valid_from, valid_to) -> key
    key_lookup = []
    for r in dim_emp.itertuples():
        key_lookup.append((r.emp_id, pd.Timestamp(r.valid_from), pd.Timestamp(r.valid_to), r.employee_key))
    key_by_emp = defaultdict(list)
    for emp_id, vf, vt, k in key_lookup:
        key_by_emp[emp_id].append((vf, vt, k))
    def emp_key(emp_id, ds):
        d = pd.Timestamp(ds)
        for vf, vt, k in key_by_emp.get(emp_id, []):
            if vf <= d <= vt:
                return k
        return None
    att["employee_key"] = [emp_key(e, d) for e, d in zip(att["emp_id"], att["work_date"])]
    att.to_sql("fact_attendance_daily", conn, if_exists="replace", index=False)

    # ---------- Overtime approved fact ----------
    ot = pd.read_csv(DATA / "overtime_requests.csv", dtype=str, keep_default_na=False)
    ot["approved_hours"] = pd.to_numeric(ot["approved_hours"], errors="coerce")
    ot["requested_hours"] = pd.to_numeric(ot["requested_hours"], errors="coerce")
    ot_app = ot[ot["status"] == "Approved"].copy()
    ot_app.to_sql("fact_overtime_approved", conn, if_exists="replace", index=False)
    ot.to_sql("stg_overtime_requests", conn, if_exists="replace", index=False)
    print(f"overtime: total {len(ot)}, approved {len(ot_app)}")

    # ---------- Payroll fact with month-end dept ----------
    pay = pd.read_csv(DATA / "payroll_lines.csv", dtype=str, keep_default_na=False)
    pay["units"] = pd.to_numeric(pay["units"], errors="coerce")
    pay["amount"] = pd.to_numeric(pay["amount"], errors="coerce")
    # month-end dept: for each emp/month, dept on last day of month or separation if earlier
    pay_depts = []
    emp_sep = {r.emp_id: r.separation_date for r in emp_clean.itertuples()}
    for (emp_id, pm), g in pay.groupby(["emp_id", "payroll_month"]):
        y, m = map(int, pm.split("-"))
        month_end = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
        sep = emp_sep.get(emp_id)
        dept_date = month_end
        if sep is not None and not pd.isna(sep) and sep < month_end:
            dept_date = sep
        did = dept_on_date(emp_id, dept_date)
        if did is None:
            # fallback emp dept
            row = emp_clean[emp_clean["emp_id"] == emp_id]
            did = row.iloc[0]["dept_id"] if len(row) else None
        pay_depts.append({"emp_id": emp_id, "payroll_month": pm, "dept_id": did, "plant": dept_plant.get(did)})
    pay_dept_df = pd.DataFrame(pay_depts)
    pay = pay.merge(pay_dept_df, on=["emp_id", "payroll_month"], how="left")
    pay.to_sql("fact_payroll_line", conn, if_exists="replace", index=False)
    print(f"payroll lines: {len(pay)}")

    # ---------- Fact leave dept ----------
    if len(leave_days_df):
        leave_days_df["dept_id"] = [dept_on_date(e, pd.Timestamp(d)) for e, d in zip(leave_days_df["emp_id"], leave_days_df["leave_date"])]
        leave_days_df.to_sql("fact_leave_day", conn, if_exists="replace", index=False)

    # Unique indexes enforcing primary keys in SQLite (DDL file shows full PK/FK).
    cur = conn.cursor()
    for idx_sql in [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_employee_key ON dim_employee(employee_key)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_department_id ON dim_department(dept_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_shift_code ON dim_shift(shift_code)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_date ON dim_date(date)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_attendance_pk ON fact_attendance_daily(emp_id, work_date)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_overtime_pk ON fact_overtime_approved(request_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_payroll_pk ON fact_payroll_line(line_id)",
    ]:
        cur.execute(idx_sql)
    conn.commit()
    conn.close()
    print("DONE staging + warehouse facts")

if __name__ == "__main__":
    main()
