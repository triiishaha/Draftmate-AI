import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import "./Productivity.css";

const STORE_KEY = "m3_tracker_v1";
const load = () => { try { return JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch (e) { return []; } };
const persist = (items) => { try { localStorage.setItem(STORE_KEY, JSON.stringify(items)); } catch (e) { /* storage unavailable */ } };

function dueLabel(d) {
  if (d == null) return "";
  if (d < 0) return `${-d} days overdue`;
  if (d === 0) return "Due today";
  return `in ${d} days`;
}
const dueClass = (d) => (d == null ? "" : d < 0 ? "pr-overdue" : d <= 14 ? "pr-soon" : "");

function Tracker() {
  const [text, setText] = useState("");
  const [items, setItems] = useState(load);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("all");

  const update = (next) => { setItems(next); persist(next); };

  const extract = async () => {
    setBusy(true); setErr("");
    try {
      const { items: found } = await api("/deadlines", { method: "POST", body: { text } });
      const known = new Set(items.map((i) => i.title + (i.date || "")));
      const fresh = found.filter((f) => !known.has(f.title + (f.date || "")))
        .map((f) => ({ ...f, id: `${Date.now()}-${f.id}`, done: false }));
      update([...items, ...fresh]);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const toggle = (id) => update(items.map((i) => (i.id === id ? { ...i, done: !i.done } : i)));
  const remove = (id) => update(items.filter((i) => i.id !== id));

  const shown = items.filter((i) => filter === "all" || i.type === filter)
    .sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999"));
  const overdue = items.filter((i) => !i.done && i.days_left != null && i.days_left < 0).length;
  const upcoming = items.filter((i) => !i.done && i.days_left != null && i.days_left >= 0 && i.days_left <= 14).length;

  return (
    <section>
      <textarea className="pr-text" rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste a contract to extract dates, notice periods and obligations" />
      <button className="pr-btn" disabled={!text.trim() || busy} onClick={extract}>{busy ? "Extracting…" : "Add to tracker"}</button>
      {err && <p className="pr-error">{err}</p>}
      <div className="pr-summary">
        <span className="pr-pill pr-overdue">{overdue} overdue</span>
        <span className="pr-pill pr-soon">{upcoming} due in 14 days</span>
        <span className="pr-pill">{items.filter((i) => i.done).length} done</span>
        <select aria-label="Filter" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All items</option><option value="date">Dates</option>
          <option value="period">Periods &amp; notice</option><option value="obligation">Obligations</option>
        </select>
      </div>
      {shown.length === 0 && <p className="pr-empty">Nothing tracked yet. Paste a contract above to start.</p>}
      <ul className="pr-list">
        {shown.map((i) => (
          <li key={i.id} className={`pr-item ${i.done ? "pr-done" : ""}`}>
            <input type="checkbox" checked={i.done} onChange={() => toggle(i.id)} aria-label={`Mark done: ${i.title}`} />
            <div className="pr-body">
              <p>{i.title}</p>
              <small>
                {i.type === "date" && <b className={dueClass(i.days_left)}>{i.date} · {dueLabel(i.days_left)}</b>}
                {i.type === "period" && <b>{i.period}</b>}
                {i.type === "obligation" && <b>Owed by: {i.party}</b>}
              </small>
            </div>
            <button className="pr-x" onClick={() => remove(i.id)} aria-label="Remove">Remove</button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Templates() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: "", category: "General", text: "" });
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState("");
  const refresh = useCallback(() => api("/templates").then(setList).catch((e) => setErr(e.message)), []);
  useEffect(() => { refresh(); }, [refresh]);

  const save = async () => {
    setErr("");
    try { await api("/templates", { method: "POST", body: form }); setForm({ name: "", category: "General", text: "" }); refresh(); }
    catch (e) { setErr(e.message); }
  };
  const view = async (id) => { setOpen(await api(`/templates/${id}`)); };
  const del = async (id) => { await api(`/templates/${id}`, { method: "DELETE" }); if (open?.id === id) setOpen(null); refresh(); };

  return (
    <section className="pr-grid">
      <div>
        <h3>Save an approved template</h3>
        <input className="pr-input" placeholder="Template name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="pr-input" placeholder="Category (e.g. Employment, NDA)" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
        <textarea className="pr-text" rows={9} placeholder="Template text" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
        <button className="pr-btn" disabled={!form.name.trim() || !form.text.trim()} onClick={save}>Save template</button>
        {err && <p className="pr-error">{err}</p>}
      </div>
      <div>
        <h3>Saved templates ({list.length})</h3>
        {list.length === 0 && <p className="pr-empty">No templates saved yet.</p>}
        <ul className="pr-list">
          {list.map((t) => (
            <li key={t.id} className="pr-item">
              <div className="pr-body"><p>{t.name}</p><small>{t.category} · {t.created_at.slice(0, 10)}</small></div>
              <button className="pr-x" onClick={() => view(t.id)}>View</button>
              <button className="pr-x" onClick={() => del(t.id)}>Delete</button>
            </li>
          ))}
        </ul>
        {open && (
          <div className="pr-preview">
            <h4>{open.name}</h4><pre>{open.text}</pre>
            <button className="pr-x" onClick={() => navigator.clipboard?.writeText(open.text)}>Copy text</button>
          </div>
        )}
      </div>
    </section>
  );
}

function Versions() {
  const [docs, setDocs] = useState({});
  const [form, setForm] = useState({ doc: "", note: "", text: "" });
  const [pick, setPick] = useState([]);
  const [diff, setDiff] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const refresh = useCallback(() => api("/versions").then(setDocs).catch((e) => setErr(e.message)), []);
  useEffect(() => { refresh(); }, [refresh]);

  const save = async () => {
    setErr(""); setMsg("");
    try {
      const v = await api("/versions", { method: "POST", body: form });
      setMsg(v.unchanged ? `No changes since v${v.version}, nothing saved.` : `Saved as v${v.version}.`);
      refresh();
    } catch (e) { setErr(e.message); }
  };
  const toggle = (id) => setPick((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));
  const compare = async () => {
    const [a, b] = await Promise.all(pick.map((id) => api(`/versions/${id}`)));
    setDiff({ a, b, res: await api("/compare", { method: "POST", body: { text_a: a.text, text_b: b.text } }) });
  };

  return (
    <section className="pr-grid">
      <div>
        <h3>Save a new version</h3>
        <input className="pr-input" placeholder="Document name (e.g. Employment contract – Asha)" value={form.doc} onChange={(e) => setForm({ ...form, doc: e.target.value })} />
        <input className="pr-input" placeholder="What changed? (optional)" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        <textarea className="pr-text" rows={9} placeholder="Contract text" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
        <button className="pr-btn" disabled={!form.doc.trim() || !form.text.trim()} onClick={save}>Save version</button>
        {msg && <p className="pr-ok">{msg}</p>}{err && <p className="pr-error">{err}</p>}
      </div>
      <div>
        <h3>Version history</h3>
        {Object.keys(docs).length === 0 && <p className="pr-empty">No versions saved yet.</p>}
        {Object.entries(docs).map(([name, vs]) => (
          <div key={name} className="pr-doc">
            <h4>{name}</h4>
            <ul className="pr-list">
              {[...vs].reverse().map((v) => (
                <li key={v.id} className="pr-item">
                  <input type="checkbox" checked={pick.includes(v.id)} onChange={() => toggle(v.id)} aria-label={`Select v${v.version}`} />
                  <div className="pr-body"><p>v{v.version}{v.note ? ` – ${v.note}` : ""}</p><small>{v.created_at.replace("T", " ").slice(0, 16)}</small></div>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <button className="pr-btn" disabled={pick.length !== 2} onClick={compare}>Compare selected (pick 2)</button>
        {diff && (
          <div className="pr-preview">
            <h4>{diff.a.doc}: v{diff.a.version} → v{diff.b.version}</h4>
            <p>{diff.res.stats.added} added · {diff.res.stats.removed} removed · {diff.res.stats.changed} changed · {diff.res.needs_review} need review</p>
            {diff.res.changes.map((c, i) => (
              <p key={i} className="pr-redline">{c.words.map((w, j) => <span key={j} className={`pr-w-${w.op}`}>{w.t} </span>)}</p>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

const TABS = [["tracker", "Deadline tracker"], ["templates", "Templates"], ["versions", "Version history"]];

export default function Productivity() {
  const [tab, setTab] = useState("tracker");
  return (
    <main className="pr-page">
      <h1>Productivity</h1>
      <p className="pr-sub">Keep track of what is due, reuse approved templates, and see how each contract changed over time.</p>
      <div className="pr-tabs" role="tablist">
        {TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      {tab === "tracker" && <Tracker />}
      {tab === "templates" && <Templates />}
      {tab === "versions" && <Versions />}
    </main>
  );
}
