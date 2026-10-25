"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { loadData, saveData, resetData, defaultData } from "../../lib/funnelData";

export default function Admin() {
  const [data, setData] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setData(loadData());
  }, []);

  if (!data) return <main>Loading admin...</main>;

  function updateStage(index, value) {
    const stages = [...data.stages];
    stages[index] = { ...stages[index], count: Number(value) || 0 };
    setData({ ...data, stages });
    setSaved(false);
  }

  function updateDept(index, field, value) {
    const departments = [...data.departments];
    departments[index] = {
      ...departments[index],
      [field]: field === "code" || field === "name" ? value : Number(value) || 0,
    };
    setData({ ...data, departments });
    setSaved(false);
  }

  function addDept() {
    setData({
      ...data,
      departments: [...data.departments, { code: "NEW", name: "New department", applications: 0, hired: 0, rejected: 0, declined: 0 }],
    });
  }

  function removeDept(index) {
    setData({ ...data, departments: data.departments.filter((_, i) => i !== index) });
  }

  function handleSave() {
    saveData(data);
    setSaved(true);
  }

  function handleReset() {
    resetData();
    setData(defaultData);
    setSaved(false);
  }

  function handleExport() {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "funnel-data.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <header>
        <h1>Admin: Edit Funnel Data</h1>
        <p><Link href="/">Back to dashboard</Link> - Edits save in this browser only. Original CSV files are not changed.</p>
      </header>
      <main>
        <section>
          <h2>Funnel stages</h2>
          {data.stages.map((s, i) => (
            <div className="row" key={s.stage}>
              <div className="label">{s.stage}</div>
              <input type="number" value={s.count} onChange={(e) => updateStage(i, e.target.value)} />
            </div>
          ))}
          <div className="row">
            <div className="label">Median days to hire</div>
            <input type="number" value={data.medianDaysToHire} onChange={(e) => setData({ ...data, medianDaysToHire: Number(e.target.value) || 0 })} />
          </div>
        </section>

        <section>
          <h2>Departments</h2>
          <table>
            <thead><tr><th>Code</th><th>Name</th><th>Applications</th><th>Hired</th><th>Rejected</th><th>Declined</th><th></th></tr></thead>
            <tbody>
              {data.departments.map((d, i) => (
                <tr key={i}>
                  <td><input type="text" value={d.code} onChange={(e) => updateDept(i, "code", e.target.value)} /></td>
                  <td><input type="text" value={d.name} onChange={(e) => updateDept(i, "name", e.target.value)} /></td>
                  <td><input type="number" value={d.applications} onChange={(e) => updateDept(i, "applications", e.target.value)} /></td>
                  <td><input type="number" value={d.hired} onChange={(e) => updateDept(i, "hired", e.target.value)} /></td>
                  <td><input type="number" value={d.rejected} onChange={(e) => updateDept(i, "rejected", e.target.value)} /></td>
                  <td><input type="number" value={d.declined} onChange={(e) => updateDept(i, "declined", e.target.value)} /></td>
                  <td><button className="secondary" onClick={() => removeDept(i)}>Remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <br />
          <button className="secondary" onClick={addDept}>Add department</button>
        </section>

        <section>
          <button onClick={handleSave}>Save changes</button>
          <button className="secondary" onClick={handleReset}>Reset to original</button>
          <button className="secondary" onClick={handleExport}>Export JSON</button>
          {saved && <p>Saved. Open the dashboard to see the updated numbers.</p>}
        </section>
      </main>
    </>
  );
}
