import pandas as pd, json
from pathlib import Path
from collections import defaultdict
D = Path(__file__).resolve().parents[1] / "data"
shifts = {s['shift_code']: s for s in json.load(open(D/"shifts.json"))['shifts']}
dm = pd.read_csv(D/"device_mapping.csv", dtype=str)
mp = {(r.device_id, r.device_user_id): r.emp_id for r in dm.itertuples()}
pun = pd.read_csv(D/"biometric_punches.csv", dtype=str)
pun['punch_time'] = pd.to_datetime(pun['punch_time'])
pun['emp_id'] = [mp.get((d,u)) for d,u in zip(pun.device_id, pun.device_user_id)]
pun = pun.dropna(subset=['emp_id']).sort_values(['emp_id','punch_time'])
pun['prev'] = pun.groupby('emp_id')['punch_time'].shift(1)
pun = pun[~((pun.punch_time - pun.prev).dt.total_seconds().abs() < 120)]
roster = pd.read_csv(D/"shift_roster.csv", dtype=str)
roster['week_start'] = pd.to_datetime(roster['week_start'])
roster = roster.sort_values(['emp_id','week_start'])
emp_weeks = defaultdict(list)
for r in roster.itertuples():
    emp_weeks[r.emp_id].append((r.week_start, r.shift_code))
for k in emp_weeks: emp_weeks[k].sort()
def get_shift(emp, ws):
    chosen=None
    for w,s in emp_weeks.get(emp,[]):
        if w<=ws: chosen=s
        else: break
    return chosen
pun['date'] = pun.punch_time.dt.normalize()
pun['week_start'] = pun['date'] - pd.to_timedelta(pun['date'].dt.weekday, unit='D')
pun['shift_code'] = [get_shift(e,w) for e,w in zip(pun.emp_id, pun.week_start)]
first = pun.sort_values('punch_time').groupby(['emp_id','date']).first().reset_index()
first = first.dropna(subset=['shift_code'])
def start_min(code):
    h,m = map(int, shifts[code]['start_time'].split(':')); return h*60+m
first['start_min'] = first.shift_code.map(start_min)
first['tod'] = first.punch_time.dt.hour*60 + first.punch_time.dt.minute
first['dev'] = first.tod - first.start_min
first['month'] = first.punch_time.dt.to_period('M')
for code in ['DAY']:
    sub = first[first.shift_code==code]
    print(sub.groupby(['month','device_id'])['dev'].agg(['count','mean','median']).to_string())
    print()
# Check SITE employees: are there two groups? Look at emp-level median dev for SITE DAY
sub = first[(first.shift_code=='DAY') & (first.device_id=='DEV-SITE-01')]
emp_med = sub.groupby('emp_id')['dev'].median()
print("SITE DAY emp median dev distribution:")
print(emp_med.describe().to_string())
print(emp_med.value_counts(bins=10).to_string())
# Check if dev correlates with punch_time hour? e.g. clock off only for certain hours?
print("\nSITE DAY first punch tod histogram:")
print(sub.tod.value_counts(bins=12).sort_index().to_string())
