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
emp_weeks = defaultdict(list)
for r in roster.sort_values(['emp_id','week_start']).itertuples():
    emp_weeks[r.emp_id].append((r.week_start, r.shift_code))
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
first = first[(first.shift_code=='DAY') & (first.device_id=='DEV-SITE-01')]
def start_min(code):
    h,m = map(int, shifts[code]['start_time'].split(':')); return h*60+m
first['dev'] = first.punch_time.dt.hour*60 + first.punch_time.dt.minute - 360
# daily median Jun 20 - Jul 15
sub = first[(first.date>='2026-06-20') & (first.date<='2026-07-15')]
print(sub.groupby('date')['dev'].agg(['count','median','mean']).to_string())
# also check last punch deviation? and check if correction date is 2026-07-01 exactly: punches on Jun 30 vs Jul 1
print("\nJun30 vs Jul1 sample first punches SITE:")
print(first[first.date.isin(pd.to_datetime(['2026-06-30','2026-07-01']))].sort_values('punch_time').head(20).to_string())
