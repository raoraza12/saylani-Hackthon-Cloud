# Indus Weave Recruitment Funnel Dashboard (Next.js)

A simple, editable dashboard for the recruitment funnel bonus.

## Run it

```bash
cd bonus/next-dashboard
npm install
npm run dev
```

Open http://localhost:3000 for the dashboard.
Open http://localhost:3000/admin for the admin editor.

## How editing works

Admin edits are saved in the browser (localStorage), so the dashboard
updates immediately without a database. The original data files in
`bonus/*.csv` are not changed by admin edits. To make an edit permanent,
update the CSV files and re-run `python bonus/build_funnel.py`, or use
the Export JSON button in admin and keep that file with your notes.

## Data

Default data comes from `lib/funnelData.js`, which is copied from the
output of `bonus/build_funnel.py`:
- 1,400 applications, 74 hired, 5.3% hire rate
- Median time to hire: 33 days
- Stages: Applied, Screened, Interviewed, Offered, Hired
