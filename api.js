// Shared API helper for Module 3. Set REACT_APP_API_URL in .env if the backend isn't on :8000.
const BASE = (typeof process !== "undefined" && process.env && process.env.REACT_APP_API_URL) || "http://localhost:8000";

export async function api(path, { method = "GET", body, file } = {}) {
  const opts = { method };
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    opts.body = fd;
  } else if (body) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}/api/contract${path}`, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) { /* keep statusText */ }
    throw new Error(msg);
  }
  return res.json();
}
