export const defaultData = {
  totalApplications: 1400,
  totalHired: 74,
  medianDaysToHire: 33,
  stages: [
    { stage: "Applied", count: 1400 },
    { stage: "Screened", count: 682 },
    { stage: "Interviewed", count: 263 },
    { stage: "Offered", count: 90 },
    { stage: "Hired", count: 74 },
  ],
  departments: [
    { code: "D21", name: "Cutting", applications: 180, hired: 12, rejected: 167, declined: 1 },
    { code: "D08", name: "Spinning", applications: 162, hired: 14, rejected: 144, declined: 4 },
    { code: "D23", name: "Maintenance", applications: 156, hired: 6, rejected: 148, declined: 2 },
    { code: "D15", name: "Finishing", applications: 143, hired: 4, rejected: 136, declined: 3 },
    { code: "D14", name: "Dyeing", applications: 121, hired: 6, rejected: 114, declined: 1 },
    { code: "D22", name: "Packing", applications: 105, hired: 8, rejected: 96, declined: 1 },
    { code: "D02", name: "Finance", applications: 96, hired: 6, rejected: 90, declined: 0 },
    { code: "D25", name: "Warehouse", applications: 91, hired: 3, rejected: 87, declined: 1 },
    { code: "D18", name: "Warehouse", applications: 89, hired: 3, rejected: 84, declined: 2 },
    { code: "D05", name: "Sales & Marketing", applications: 85, hired: 4, rejected: 80, declined: 1 },
    { code: "D20", name: "Stitching", applications: 50, hired: 3, rejected: 47, declined: 0 },
    { code: "D11", name: "Quality Control", applications: 42, hired: 2, rejected: 40, declined: 0 },
    { code: "D16", name: "Maintenance", applications: 42, hired: 3, rejected: 39, declined: 0 },
    { code: "D06", name: "Administration", applications: 38, hired: 0, rejected: 38, declined: 0 },
  ],
  monthly: [
    { month: "2026-04", applied: 256, hired: 1 },
    { month: "2026-05", applied: 269, hired: 10 },
    { month: "2026-06", applied: 257, hired: 14 },
    { month: "2026-07", applied: 276, hired: 11 },
    { month: "2026-08", applied: 283, hired: 17 },
    { month: "2026-09", applied: 59, hired: 14 },
  ],
};

export const STORAGE_KEY = "indus-funnel-data";

export function loadData() {
  if (typeof window === "undefined") return defaultData;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultData;
    const parsed = JSON.parse(raw);
    if (!parsed.stages || !parsed.departments) return defaultData;
    return parsed;
  } catch {
    return defaultData;
  }
}

export function saveData(data) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

export function resetData() {
  window.localStorage.removeItem(STORAGE_KEY);
}
