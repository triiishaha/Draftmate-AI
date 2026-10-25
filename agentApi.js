// Shared fetch helper for the agent modules (skills, convert, context, voice). Set REACT_APP_API_URL if the API is not on :8000.
const BASE = (typeof process !== "undefined" && process.env && process.env.REACT_APP_API_URL) || "http://localhost:8000";

export async function agentApi(path, { method = "GET", body, file } = {}) {
  const opts = { method };
  if (file) { const fd = new FormData(); fd.append("file", file); opts.body = fd; }
  else if (body) { opts.headers = { "Content-Type": "application/json" }; opts.body = JSON.stringify(body); }
  const res = await fetch(`${BASE}/api${path}`, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) { /* keep statusText */ }
    throw new Error(msg);
  }
  return res.json();
}
