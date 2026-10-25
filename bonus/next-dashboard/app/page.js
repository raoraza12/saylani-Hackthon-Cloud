"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { loadData, resetData } from "../lib/funnelData";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("");
  const [edited, setEdited] = useState(false);

  useEffect(() => {
    const loaded = loadData();
    setData(loaded);
    setEdited(window.localStorage.getItem("indus-funnel-data") !== null);
  }, []);

  if (!data) return <main>Loading dashboard...</main>;

  const applied = data.stages[0]?.count || 1;
  const hired = data.stages[data.stages.length - 1]?.count || 0;
  const hireRate = ((100 * hired) / applied).toFixed(1);
  const maxApplied = Math.max(...data.monthly.map((m) => m.applied), 1);
  const depts = data.departments.filter((d) =>
    `${d.code} ${d.name}`.toLowerCase().includes(filter.toLowerCase())
  );

  function handleReset() {
    resetData();
    window.location.reload();
  }

  return (
    <>
      <header>
        <h1>Indus Weave Recruitment Funnel</h1>
        <p>Applications from April to September 2026. <Link href="/admin">Open admin editor</Link></p>
      </header>
      <main>
        {edited && (
          <section className="note">
            <p>Showing edited data saved in this browser. Use Reset on this page or in admin to go back to the original numbers.</p>
            <button className="secondary" onClick={handleReset}>Reset to original data</button>
          </section>
        )}
        <div className="cards">
          <div className="card"><b>{applied}</b><span>Applications</span></div>
          <div className="card"><b>{hired}</b><span>Hired</span></div>
          <div className="card"><b>{hireRate}%</b><span>Overall hire rate</span></div>
          <div className="card"><b>{data.medianDaysToHire} days</b><span>Median time to hire</span></div>
        </div>

        <section>
          <h2>Funnel</h2>
          {data.stages.map((s, i) => {
            const width = Math.max(8, Math.round((100 * s.count) / applied));
            const prev = i === 0 ? null : data.stages[i - 1].count;
            const conv = prev ? ((100 * s.count) / prev).toFixed(1) : "100.0";
            const pct = ((100 * s.count) / applied).toFixed(1);
            return (
              <div className="row" key={s.stage}>
                <div className="label">{s.stage}</div>
                <div className="bar" style={{ width: `${width}%` }}>{s.count}</div>
                <div className="meta">{pct}% of applied, {conv}% from previous step</div>
              </div>
            );
          })}
        </section>

        <section className="note">
          <h2>What to fix first</h2>
          <p>Biggest percentage drop is Interviewed to Offered: only 34.2% move forward in the original data. Biggest absolute drop is Applied to Screened: 718 applications lost. Screening and interview capacity are the bottleneck, not the number of applications.</p>
        </section>

        <section>
          <h2>By department</h2>
          <input type="text" placeholder="Filter by department name or code, for example Cutting or D21" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <table>
            <thead><tr><th>Code</th><th>Department</th><th>Applications</th><th>Hired</th><th>Rejected</th><th>Offer declined</th><th>Hire rate</th></tr></thead>
            <tbody>
              {depts.map((d) => (
                <tr key={d.code}>
                  <td>{d.code}</td><td>{d.name}</td><td>{d.applications}</td><td>{d.hired}</td>
                  <td>{d.rejected}</td><td>{d.declined}</td>
                  <td>{d.applications ? ((100 * d.hired) / d.applications).toFixed(1) : "0.0"}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h2>Monthly trend</h2>
          {data.monthly.map((m) => (
            <div className="row" key={m.month}>
              <div className="label">{m.month}</div>
              <div className="bar teal" style={{ width: `${Math.max(5, Math.round((100 * m.applied) / maxApplied))}%` }}>{m.applied} applied, {m.hired} hired</div>
            </div>
          ))}
          <p>Applied means applications received in that month. Hired means hires completed in that month, not hires from that month&apos;s applicants.</p>
        </section>

        <footer>Source: data/applications.csv, 3,835 stage rows, 1,400 applications. Admin edits are stored in the browser only.</footer>
      </main>
    </>
  );
}
