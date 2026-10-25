import pandas as pd, numpy as np, json
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "data"
shifts = {s['shift_code']: s for s in json.load(open(D/"shifts.json"))['shifts']}
print(shifts)
dm = pd.read_csv(D/"device_mapping.csv", dtype=str)
mp = {(r.device_id, r.device_user_id): r.emp_id for r in dm.itertuples()}
pun = pd.read_csv(D/"biometric_punches.csv", dtype=str)
pun['punch_time'] = pd.to_datetime(pun['punch_time'])
pun['emp_id'] = [mp.get((d,u)) for d,u in zip(pun.device_id, pun.device_user_id)]
pun = pun.dropna(subset=['emp_id']).sort_values(['emp_id','punch_time'])
# 2-min dedup
pun['prev'] = pun.groupby('emp_id')['punch_time'].shift(1)
pun = pun[~((pun.punch_time - pun.prev).dt.total_seconds().abs() < 120)]
print("after 2min dedup:", len(pun))
# roster expand: for each emp, week_start -> shift, ffill missing weeks
roster = pd.read_csv(D/"shift_roster.csv", dtype=str)
roster['week_start'] = pd.to_datetime(roster['week_start'])
roster = roster.sort_values(['emp_id','week_start'])
# Build lookup: for a given date, week_start = Monday of that week
pun['date'] = pun.punch_time.dt.normalize()
pun['week_start'] = pun['date'] - pd.to_timedelta(pun['date'].dt.weekday, unit='D')
roster_dict = {(r.emp_id, r.week_start): r.shift_code for r in roster.itertuples()}
# For missing weeks, we need ffill per emp: create dict of sorted weeks
from collections import defaultdict
emp_weeks = defaultdict(list)
for r in roster.itertuples():
    emp_weeks[r.emp_id].append((r.week_start, r.shift_code))
for k in emp_weeks:
    emp_weeks[k].sort()
def get_shift(emp, ws):
    weeks = emp_weeks.get(emp, [])
    chosen = None
    for w, s in weeks:
        if w <= ws:
            chosen = s
        else:
            break
    return chosen
pun['shift_code'] = [get_shift(e, w) for e, w in zip(pun.emp_id, pun.week_start)]
first = pun.sort_values('punch_time').groupby(['emp_id','date']).first().reset_index()
first = first.dropna(subset=['shift_code'])
# For non-night shifts, deviation = first punch tod - shift start (minutes, wrap)
def start_min(code):
    t = shifts[code]['start_time']
    h,m = map(int, t.split(':'))
    return h*60+m
first['start_min'] = first.shift_code.map(start_min)
first['tod'] = first.punch_time.dt.hour*60 + first.punch_time.dt.minute
first['dev'] = first.tod - first.start_min
# For DAY (06:00) etc, dev should be -30 to +30 normally; faulty device will be +/-60
for code in ['DAY','EVE','GEN']:
    sub = first[first.shift_code==code]
    print(f"\n--- {code} first-punch deviation by device (minutes) ---")
    print(sub.groupby('device_id')['dev'].agg(['count','mean','median','std']).to_string())
    # histogram of dev rounded to nearest 10?
    print(sub.groupby(['device_id', pd.cut(sub.dev, bins=[-200,-70,-40,-20,0,20,40,70,200])]).size().unstack(fill_value=0).to_string())
# Also check all devices: median dev per shift
print("\nMedian dev by device x shift:")
print(first.groupby(['device_id','shift_code'])['dev'].median().unstack().to_string())
