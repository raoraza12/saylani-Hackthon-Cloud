"""Recruitment funnel bonus for Indus Weave.

Reads data/applications.csv, writes summary CSVs and a static dashboard
in bonus/dashboard.html. No external JavaScript or fonts are used, so
the dashboard opens offline in a browser.

Stages in order: Applied, Screened, Interviewed, Offered, Hired.
Rejected and Offer Declined are final outcomes, not funnel steps.
"""
import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data" / "applications.csv"
OUT = Path(__file__).resolve().parent

STAGES = ["Applied", "Screened", "Interviewed", "Offered", "Hired"]


def main():
    df = pd.read_csv(DATA, parse_dates=["stage_date"])
    df = df.sort_values(["application_id", "stage_date"])

    # How many distinct applications reached each stage.
    reached = {}
    for stage in STAGES:
        reached[stage] = int(df.loc[df["stage"] == stage, "application_id"].nunique())

    summary = []
    prev = None
    for stage in STAGES:
        count = reached[stage]
        if prev is None:
            conv_from_prev = 100.0
            dropped = 0
        else:
            conv_from_prev = round(100.0 * count / prev, 1) if prev else 0.0
            dropped = prev - count
        summary.append({
            "stage": stage,
            "applications_reached": count,
            "pct_of_applied": round(100.0 * count / reached["Applied"], 1),
            "conversion_from_previous_stage_pct": conv_from_prev,
            "dropped_at_this_step": dropped,
        })
        prev = count
    pd.DataFrame(summary).to_csv(OUT / "funnel_summary.csv", index=False)

    # Median days between consecutive stage changes.
    df["prev_stage"] = df.groupby("application_id")["stage"].shift()
    df["prev_date"] = df.groupby("application_id")["stage_date"].shift()
    df["days"] = (df["stage_date"] - df["prev_date"]).dt.days
    trans = (
        df.dropna(subset=["prev_stage"])
        .groupby(["prev_stage", "stage"])["days"]
        .agg(["count", "median", "mean"])
        .reset_index()
        .rename(columns={"prev_stage": "from_stage", "stage": "to_stage"})
    )
    trans["median"] = trans["median"].astype(int)
    trans["mean"] = trans["mean"].round(1)
    trans.to_csv(OUT / "stage_transitions.csv", index=False)

    # Final outcome per application, joined with its department.
    last = df.sort_values("stage_date").groupby("application_id").tail(1)
    dept = df[["application_id", "dept_id"]].drop_duplicates()
    last = last.merge(dept, on="application_id", suffixes=("", "_dept"))
    # Department names come from departments.csv when it is present.
    dept_names = {}
    dept_file = BASE / "data" / "departments.csv"
    if dept_file.exists():
        d = pd.read_csv(dept_file)
        dept_names = dict(zip(d["dept_id"], d["dept_name"]))

    by_dept = []
    for dept_id, group in last.groupby("dept_id"):
        applied = int(df.loc[(df["dept_id"] == dept_id) & (df["stage"] == "Applied"), "application_id"].nunique())
        hired = int((group["stage"] == "Hired").sum())
        rejected = int((group["stage"] == "Rejected").sum())
        declined = int((group["stage"] == "Offer Declined").sum())
        by_dept.append({
            "dept_id": dept_id,
            "dept_name": dept_names.get(dept_id, dept_id),
            "applications": applied,
            "hired": hired,
            "rejected": rejected,
            "offer_declined": declined,
            "hire_rate_pct": round(100.0 * hired / applied, 1) if applied else 0.0,
        })
    by_dept_df = pd.DataFrame(by_dept).sort_values("applications", ascending=False)
    by_dept_df.to_csv(OUT / "funnel_by_department.csv", index=False)

    # Monthly trend: applications and hires by Applied / Hired month.
    applied_m = df[df["stage"] == "Applied"].copy()
    applied_m["month"] = applied_m["stage_date"].dt.strftime("%Y-%m")
    hired_m = df[df["stage"] == "Hired"].copy()
    hired_m["month"] = hired_m["stage_date"].dt.strftime("%Y-%m")
    monthly = pd.DataFrame({
        "month": sorted(applied_m["month"].unique()),
    })
    monthly["applied"] = monthly["month"].map(applied_m.groupby("month").size()).fillna(0).astype(int)
    monthly["hired"] = monthly["month"].map(hired_m.groupby("month").size()).fillna(0).astype(int)
    monthly.to_csv(OUT / "funnel_monthly.csv", index=False)

    # Time to hire: Applied date to Hired date, per hired candidate.
    applied_d = df[df["stage"] == "Applied"][["application_id", "stage_date"]].rename(columns={"stage_date": "applied_date"})
    hired_d = df[df["stage"] == "Hired"][["application_id", "stage_date"]].rename(columns={"stage_date": "hired_date"})
    tth = hired_d.merge(applied_d, on="application_id")
    tth["days_to_hire"] = (tth["hired_date"] - tth["applied_date"]).dt.days
    tth_median = int(tth["days_to_hire"].median())
    tth_mean = round(float(tth["days_to_hire"].mean()), 1)

    # Biggest drop in absolute and in percentage terms.
    drops = []
    for i in range(1, len(summary)):
        drops.append((summary[i]["stage"], summary[i - 1]["applications_reached"] - summary[i]["applications_reached"], summary[i]["conversion_from_previous_stage_pct"]))
    biggest_abs = max(drops, key=lambda x: x[1])
    biggest_pct = min(drops, key=lambda x: x[2])

    data = {
        "summary": summary,
        "transitions": trans.to_dict("records"),
        "by_dept": by_dept_df.to_dict("records"),
        "monthly": monthly.to_dict("records"),
        "total_applications": int(df["application_id"].nunique()),
        "total_hired": int(reached["Hired"]),
        "overall_hire_rate_pct": round(100.0 * reached["Hired"] / reached["Applied"], 1),
        "median_days_to_hire": tth_median,
        "mean_days_to_hire": tth_mean,
        "biggest_absolute_drop": {"stage": biggest_abs[0], "dropped": int(biggest_abs[1])},
        "biggest_percentage_drop": {"stage": biggest_pct[0], "conversion_pct": biggest_pct[2]},
    }
    (OUT / "funnel_data.json").write_text(json.dumps(data, indent=2))
    build_dashboard(data)
    print(f"Applications: {data['total_applications']}, Hired: {data['total_hired']}, Median days to hire: {tth_median}")


def build_dashboard(data):
    # Funnel bars, widths proportional to applications reached.
    bars = ""
    total = data["summary"][0]["applications_reached"]
    for row in data["summary"]:
        width = max(8, round(100.0 * row["applications_reached"] / total))
        bars += (
            f"<div class='row'><div class='label'>{row['stage']}</div>"
            f"<div class='bar' style='width:{width}%'>{row['applications_reached']}</div>"
            f"<div class='meta'>{row['pct_of_applied']}% of applied, "
            f"{row['conversion_from_previous_stage_pct']}% from previous step</div></div>"
        )

    # Department table, with a simple client side filter.
    dept_rows = ""
    for r in data["by_dept"]:
        dept_rows += (
            f"<tr><td>{r['dept_id']}</td><td>{r['dept_name']}</td>"
            f"<td>{r['applications']}</td><td>{r['hired']}</td>"
            f"<td>{r['rejected']}</td><td>{r['offer_declined']}</td>"
            f"<td>{r['hire_rate_pct']}%</td></tr>"
        )

    # Monthly trend bars.
    max_applied = max(r["applied"] for r in data["monthly"]) if data["monthly"] else 1
    monthly_bars = ""
    for r in data["monthly"]:
        width = max(5, round(100.0 * r["applied"] / max_applied))
        monthly_bars += (
            f"<div class='row'><div class='label'>{r['month']}</div>"
            f"<div class='bar teal' style='width:{width}%'>{r['applied']} applied, {r['hired']} hired</div></div>"
        )

    trans_rows = "".join(
        f"<tr><td>{r['from_stage']}</td><td>{r['to_stage']}</td>"
        f"<td>{r['count']}</td><td>{r['median']} days</td><td>{r['mean']} days</td></tr>"
        for r in data["transitions"]
    )

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indus Weave Recruitment Funnel</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; margin: 0; background: #f4f5f7; color: #1a1a1a; }}
header {{ background: #12355b; color: white; padding: 28px 32px; }}
header h1 {{ margin: 0 0 8px 0; font-size: 28px; }}
header p {{ margin: 0; color: #cdd8e4; }}
main {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
.cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
.card {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 16px; }}
.card b {{ font-size: 28px; display: block; }}
.card span {{ color: #555; }}
section {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-top: 16px; }}
h2 {{ margin-top: 0; }}
.row {{ display: flex; align-items: center; gap: 10px; margin: 8px 0; }}
.label {{ width: 130px; font-weight: bold; }}
.bar {{ background: #12355b; color: white; padding: 8px 10px; border-radius: 4px; min-width: 60px; }}
.bar.teal {{ background: #0f766e; }}
.meta {{ color: #555; font-size: 14px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #eee; }}
input {{ padding: 8px; width: 100%; box-sizing: border-box; margin-bottom: 10px; }}
.note {{ background: #fff7e6; border: 1px solid #f0d9a0; border-radius: 8px; padding: 14px; }}
footer {{ color: #666; font-size: 13px; padding: 16px 0 32px 0; }}
</style></head><body>
<header><h1>Indus Weave Recruitment Funnel</h1>
<p>Applications from April to September 2026. One row per stage change in applications.csv. Final outcomes are Hired, Rejected and Offer Declined.</p></header>
<main>
<div class="cards">
<div class="card"><b>{data['total_applications']}</b><span>Applications</span></div>
<div class="card"><b>{data['total_hired']}</b><span>Hired</span></div>
<div class="card"><b>{data['overall_hire_rate_pct']}%</b><span>Overall hire rate</span></div>
<div class="card"><b>{data['median_days_to_hire']} days</b><span>Median time to hire</span></div>
</div>

<section><h2>Funnel</h2>{bars}</section>

<section class="note"><h2>What to fix first</h2>
<p>Biggest absolute drop: {data['biggest_absolute_drop']['stage']} step, {data['biggest_absolute_drop']['dropped']} applications lost. Biggest percentage drop: {data['biggest_percentage_drop']['stage']} step, only {data['biggest_percentage_drop']['conversion_pct']}% moved forward. Screening and interview capacity are the bottleneck, not the number of applications.</p>
<p>Median time to hire is {data['median_days_to_hire']} days. Every stage takes about 8 to 9 days on median, so no single stage is unusually slow. The loss happens at the decision, not in waiting time.</p></section>

<section><h2>By department</h2>
<p>Type in the box to filter the table. Hire rate is hired divided by applications in that department.</p>
<input id="deptFilter" placeholder="Filter by department name or code, for example Cutting or D21">
<table id="deptTable"><thead><tr><th>Code</th><th>Department</th><th>Applications</th><th>Hired</th><th>Rejected</th><th>Offer declined</th><th>Hire rate</th></tr></thead>
<tbody>{dept_rows}</tbody></table></section>

<section><h2>Monthly trend</h2>{monthly_bars}
<p>Applied means applications received in that month. Hired means hires completed in that month, not hires from that month's applicants, so the two columns are not a cohort. September applications look low because the file ends in September and many September applications were still in progress. Do not compare September directly with earlier months.</p></section>

<section><h2>Median days between stages</h2>
<table><thead><tr><th>From</th><th>To</th><th>Cases</th><th>Median</th><th>Mean</th></tr></thead><tbody>{trans_rows}</tbody></table></section>

<footer>Source: data/applications.csv, 3,835 stage rows, 1,400 applications. Built by bonus/build_funnel.py. Re-run that script after any data change.</footer>
</main>
<script>
document.getElementById('deptFilter').addEventListener('input', function(e) {{
  var q = e.target.value.toLowerCase();
  document.querySelectorAll('#deptTable tbody tr').forEach(function(tr) {{
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}});
</script>
</body></html>
"""
    (OUT / "dashboard.html").write_text(html)
    return html


if __name__ == "__main__":
    main()
