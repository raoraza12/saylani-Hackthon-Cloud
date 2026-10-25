import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]

# ---------- ERD ----------
fig, ax = plt.subplots(figsize=(14, 9))
ax.set_xlim(0, 14); ax.set_ylim(0, 9); ax.axis("off")
ax.set_title("Indus Weave — Star Schema ERD", fontsize=18, weight="bold", pad=20)
def box(x, y, w, h, title, lines):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08", facecolor="#eef2ff", edgecolor="#1f3a93", linewidth=1.5))
    ax.text(x+w/2, y+h-0.35, title, ha="center", va="top", fontsize=11, weight="bold")
    for i, ln in enumerate(lines):
        ax.text(x+0.15, y+h-0.85-i*0.35, ln, ha="left", va="top", fontsize=9)
def line(x1, y1, x2, y2):
    ax.plot([x1, x2], [y1, y2], color="#333333", linewidth=1.2)
# Facts centre
box(5.0, 3.5, 4.0, 2.2, "fact_attendance_daily", ["PK emp_id, work_date", "FK employee_key -> dim_employee", "FK dept_id -> dim_department", "FK shift_code -> dim_shift", "status, worked_hours, overtime_hours"])
box(0.3, 0.3, 3.2, 1.8, "fact_leave_day", ["emp_id, leave_date", "leave_type, request_id"])
box(5.0, 0.3, 3.2, 1.8, "fact_overtime_approved", ["request_id, emp_id, ot_date", "approved_hours"])
box(9.8, 0.3, 3.9, 1.8, "fact_payroll_line", ["line_id, payroll_month", "emp_id, component, amount, units"])
# Dimensions
box(0.3, 6.5, 3.2, 1.8, "dim_employee (SCD2)", ["PK employee_key", "emp_id, dept_id, grade", "valid_from, valid_to, is_current"])
box(5.0, 6.5, 3.2, 1.8, "dim_department", ["PK dept_id", "dept_name, plant, cost_center"])
box(9.8, 6.5, 3.2, 1.8, "dim_shift", ["PK shift_code", "start_time, end_time"])
box(9.8, 3.5, 3.2, 1.8, "dim_date", ["PK date", "year, month, day_of_week"])
line(3.5, 7.4, 5.0, 5.0); line(8.2, 7.4, 7.0, 5.7); line(11.4, 6.5, 9.0, 5.0); line(9.8, 4.4, 9.0, 4.6)
ax.text(7, 8.7, "Attendance belongs to Workforce; Payroll consumes attendance results.", ha="center", fontsize=10, style="italic")
plt.tight_layout()
plt.savefig(BASE / "warehouse" / "erd.png", dpi=200, bbox_inches="tight")
plt.close()
print("erd.png written")

# ---------- Slides (6 pages) ----------
slides = [
    ("Indus Weave Textiles\nWhy overtime cost keeps rising", "PeopleOps Data Hackathon  •  Solo  •  Python + SQL + SQLite\n6 months: 1 Apr – 30 Sep 2026  •  ~1,200 employees  •  Headcount fell, OT bill rose\n\nThe question: is this more work, or more paid-but-not-worked overtime?"),
    ("1  •  Paid OT is not worked OT", "Computed OT from biometric punches: 29,116 hours in 6 months\nApproved / paid OT: 36,402 hours\nGap: 7,286 hours\n\nApr gap: 856 hours  →  Sep gap: 1,748 hours\nOT bill: PKR 2.81m (Apr) → PKR 3.48m (Sep), +23.5%\nWorked OT was flat: 4,670 – 5,051 hours per month.\n\nAction: pay OT only from computed OT. No computed OT, no payment."),
    ("2  •  Approvals pay for days with no OT worked", "3,518 of 19,666 approved OT requests (17.9%)\nhad zero computed OT on that day.\n\n584 were Present days with zero OT after shift end.\nThe rest were Absent, Missing Punch, On Leave, Holiday or Weekly Off days.\n\nFaisalabad Plant is the worst: 14,418 paid vs 9,895 computed hours.\n\nAction: block approval when computed OT = 0, and audit Faisalabad first."),
    ("3  •  Pay did not stop on separation", "5 employees were paid after separation.\nTotal: PKR 1,983,188 across 21 employee-months.\n\nExample: Umair Baloch, separated 23 Apr 2026,\npaid May–Sep: PKR 682,100.\n\nOnly 1 employee-month had pay with zero Present days in that month —\nthe same control failure, not a workload story.\n\nAction: payroll must stop automatically on separation_date, with a monthly Q8 check."),
    ("How we proved it — and what to fix next", "• Raw loaded untouched, all TEXT, with _row_hash — 472,907 rows\n• DEV-SITE-01 clock was 60 min fast from 1 Jul 2026 — corrected, documented\n• 20,465 Missing Punch days (9.4%) — fix biometric check-out discipline\n• 20 employees already exceed full-year Annual leave in 6 months\n• DQ: 22/22 checks pass, raw = staging + rejected\n\nNext: computed-OT approval gate, separation payroll stop, SITE device audit."),
    ("Demo  •  What to look at", "Run:  python run_pipeline.py\nThen:  python analytics/run_queries.py\n\nQ1–Q10: analytics/q01..q10.sql  →  analytics/results/*.csv\nWarehouse: indus_weave.db  •  dim_employee (SCD2), dim_department, dim_shift, dim_date\nFacts: fact_attendance_daily, fact_leave_day, fact_overtime_approved, fact_payroll_line\n\nQuestions? I can explain every line — start with Q5, Q6, Q8."),
]
with PdfPages(BASE / "presentation" / "slides.pdf") as pdf:
    for title, body in slides:
        fig, ax = plt.subplots(figsize=(13.33, 7.5))
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
        ax.set_facecolor("#f8fafc")
        ax.text(0.5, 9.2, title, ha="left", va="top", fontsize=22, weight="bold", wrap=True)
        ax.text(0.5, 7.2, body, ha="left", va="top", fontsize=15, linespacing=1.6)
        ax.text(0.5, 0.4, "Indus Weave  •  PeopleOps Data Hackathon  •  5-minute demo", ha="left", fontsize=10, color="#555555")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()
print("slides.pdf written")
