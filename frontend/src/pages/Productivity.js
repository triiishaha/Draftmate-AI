import React, { useEffect, useState } from "react";
import { RedlineResult } from "./ContractIntelligence";
import "./Productivity.css";

// Backend address. Change this one line if the Python backend is not on port 8000.
// A page can also set window.DRAFTMATE_API before this loads (the demo page does).
const API =
  typeof window !== "undefined" && window.DRAFTMATE_API !== undefined
    ? window.DRAFTMATE_API
    : (process.env.REACT_APP_API_URL || "http://localhost:8000");

const SAMPLE = `RENTAL AGREEMENT

This Agreement is effective from 1 November 2026.

The Tenant shall pay a monthly rent of Rs. 25,000 on or before the 5th day of each month.
The Tenant must pay the security deposit of Rs. 75,000 by 15/11/2026.
The Tenant shall submit police verification documents within 15 days of joining.
Either party may terminate this Agreement by giving thirty (30) days' notice in writing.
The Landlord shall return the security deposit within 30 days of the Tenant vacating the premises.
The Tenant shall keep the premises in good condition.
This Agreement shall expire on 31 October 2027 unless renewed.`;

const GROUPS = [
  ["overdue", "Overdue", "bad"],
  ["due_soon", "Due in the next 30 days", "warn"],
  ["upcoming", "Upcoming", "ok"],
  ["needs_start_date", "Needs an effective date to be dated", "mod"],
  ["event_based", "Runs from an event, not a calendar date", "mod"],
  ["notice_period", "Notice periods", "mod"],
  ["recurring", "Recurring duties", "mod"],
  ["undated", "Obligations with no stated deadline", "mute"],
];

const STORE = "draftmate.tracker.done";

function loadDone() {
  try {
    return JSON.parse(window.localStorage.getItem(STORE) || "{}");
  } catch (e) {
    return {};
  }
}

function saveDone(done) {
  try {
    window.localStorage.setItem(STORE, JSON.stringify(done));
  } catch (e) {
    /* private window or blocked storage: the tracker still works for this visit */
  }
}

function fmtDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function daysText(n) {
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  return n > 0 ? `in ${n} days` : `${-n} day${n === -1 ? "" : "s"} overdue`;
}

function icsEscape(s) {
  return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, " ");
}

function downloadIcs(items) {
  const dated = items.filter((i) => i.date);
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//DraftMate AI//Tracker//EN"];
  dated.forEach((i) => {
    const day = i.date.replace(/-/g, "");
    lines.push(
      "BEGIN:VEVENT",
      `UID:draftmate-${i.id}-${day}@draftmate`,
      `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`,
      `DTSTART;VALUE=DATE:${day}`,
      `SUMMARY:${icsEscape(`${i.type}${i.party ? " (" + i.party + ")" : ""}: ${i.text.slice(0, 80)}`)}`,
      `DESCRIPTION:${icsEscape(i.text)}`,
      "END:VEVENT"
    );
  });
  lines.push("END:VCALENDAR");
  const blob = new Blob([lines.join("\r\n")], { type: "text/calendar" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "contract-deadlines.ics";
  a.click();
  URL.revokeObjectURL(a.href);
}

function Item({ it, done, onToggle }) {
  const rel = it.relative;
  return (
    <article className={`pr-item ${done ? "done" : ""}`}>
      <div className="pr-when">
        {it.date ? (
          <>
            <strong>{fmtDate(it.date)}</strong>
            <span>{daysText(it.days_left)}</span>
          </>
        ) : rel ? (
          <strong>{rel.text}</strong>
        ) : it.recurring ? (
          <strong>{it.recurring}</strong>
        ) : (
          <strong>No date</strong>
        )}
      </div>
      <div className="pr-body">
        <div className="pr-tags">
          <span className="pr-tag">{it.type}</span>
          {it.party && <span className="pr-tag party">{it.party}</span>}
          {it.is_obligation && <span className="pr-tag">Obligation</span>}
        </div>
        <p className="pr-quote">{it.text}</p>
        {rel && rel.trigger && <p className="pr-note">Time limit: {rel.text} {rel.trigger}</p>}
        {it.due_from_start && <p className="pr-note">Date worked out from the effective date you entered.</p>}
      </div>
      <label className="pr-done">
        <input type="checkbox" checked={!!done} onChange={() => onToggle(it.text)} /> Done
      </label>
    </article>
  );
}

function Deadlines() {
  const [text, setText] = useState("");
  const [start, setStart] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(loadDone);
  const [hideDone, setHideDone] = useState(false);

  async function extract() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch(`${API}/contract/deadlines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, start_date: start || null }),
      });
      if (!r.ok) throw new Error(`Server returned ${r.status}`);
      setRes(await r.json());
    } catch (e) {
      setRes(null);
      setError("Could not read the contract. Is the backend running and CORS enabled?");
    } finally {
      setBusy(false);
    }
  }

  function toggle(key) {
    const next = { ...done, [key]: !done[key] };
    if (!next[key]) delete next[key];
    setDone(next);
    saveDone(next);
  }

  const s = res && res.summary;
  const dated = res ? res.items.filter((i) => i.date) : [];

  return (
    <div>
      <header className="pr-header">
        <h2 className="pr-h2">Deadline &amp; Obligation Tracker</h2>
        <p className="pr-muted">
          Finds dates, "within N days" deadlines and duties in a contract. Each item shows the exact sentence it came from. No AI is used, so nothing is invented.
        </p>
      </header>

      <label className="pr-label" htmlFor="pr-text">Contract text</label>
      <textarea
        id="pr-text"
        className="pr-textarea"
        rows={10}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste the contract text here"
      />

      <div className="pr-actions">
        <label className="pr-start">
          Effective date <span className="pr-muted">(optional)</span>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <button className="pr-btn" onClick={extract} disabled={busy || text.trim().length < 10}>
          {busy ? "Reading…" : "Find deadlines"}
        </button>
        <button className="pr-btn2" onClick={() => { setText(SAMPLE); setStart("2026-11-01"); setRes(null); }}>
          Load sample contract
        </button>
      </div>
      {error && <p className="pr-error" role="alert">{error}</p>}

      {res && (
        <section aria-live="polite">
          <p className="pr-summary">
            <span className="pr-chip bad">{s.overdue} overdue</span>
            <span className="pr-chip warn">{s.due_soon} due soon</span>
            <span className="pr-chip ok">{s.upcoming} upcoming</span>
            <span className="pr-chip">{s.total} items in total</span>
          </p>
          <div className="pr-tools">
            {dated.length > 0 && (
              <button className="pr-btn2" onClick={() => downloadIcs(dated)}>Download calendar file (.ics)</button>
            )}
            <label className="pr-check">
              <input type="checkbox" checked={hideDone} onChange={(e) => setHideDone(e.target.checked)} /> Hide items marked done
            </label>
            <span className="pr-muted pr-fine">As of {fmtDate(res.today)}</span>
          </div>
          {!start && s.needs_start_date > 0 && (
            <p className="pr-hint">Some deadlines count from the effective date. Enter it above to get calendar dates for them.</p>
          )}
          {res.items.length === 0 && <p className="pr-muted">No dates, deadlines or obligations were found in this text.</p>}
          {GROUPS.map(([key, title, tone]) => {
            const items = res.items.filter((i) => i.status === key && !(hideDone && done[i.text]));
            if (!items.length) return null;
            return (
              <div key={key} className="pr-group">
                <h2 className={`pr-group-title ${tone}`}>{title} <span>({items.length})</span></h2>
                {items.map((it) => <Item key={it.id} it={it} done={done[it.text]} onToggle={toggle} />)}
              </div>
            );
          })}
        </section>
      )}

      <p className="pr-fine pr-muted">
        Dates are read as written (DD/MM/YYYY for numeric dates). Check every item against the contract. A lawyer must review it.
      </p>
    </div>
  );
}

async function api(path, method = "GET", body) {
  const r = await fetch(`${API}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await r.json(); } catch (e) { /* no body */ }
  if (!r.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : `Server returned ${r.status}`);
  }
  return data;
}

function fmtStamp(iso) {
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function Templates() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: "", category: "", approved_by: "", note: "", text: "" });
  const [open, setOpen] = useState(null);
  const [msg, setMsg] = useState({ kind: "", text: "" });
  const [clash, setClash] = useState(false);

  const load = () => api("/store/templates").then((d) => setList(d.templates)).catch(() => setMsg({ kind: "error", text: "Could not reach the backend." }));
  useEffect(() => { load(); }, []);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function save(replace) {
    setMsg({ kind: "", text: "" });
    try {
      const t = await api("/store/templates", "POST", { ...form, replace });
      setMsg({ kind: "ok", text: t.replaced ? `Replaced "${t.name}".` : `Saved "${t.name}".` });
      setClash(false);
      setForm({ name: "", category: "", approved_by: "", note: "", text: "" });
      load();
    } catch (e) {
      setClash(/already exists/.test(e.message));
      setMsg({ kind: "error", text: e.message });
    }
  }

  async function view(id) {
    if (open && open.id === id) return setOpen(null);
    try { setOpen(await api(`/store/templates/${id}`)); } catch (e) { setMsg({ kind: "error", text: e.message }); }
  }

  async function remove(t) {
    if (!window.confirm(`Delete the template "${t.name}"? This cannot be undone.`)) return;
    try { await api(`/store/templates/${t.id}`, "DELETE"); setOpen(null); load(); } catch (e) { setMsg({ kind: "error", text: e.message }); }
  }

  return (
    <div>
      <header className="pr-header">
        <h2 className="pr-h2">Approved templates</h2>
        <p className="pr-muted">Save wording your team has approved, with who approved it and when. Reuse it instead of starting from a blank page.</p>
      </header>
      <div className="pr-form">
        <label className="pr-label" htmlFor="tp-name">Template name</label>
        <input id="tp-name" className="pr-input" value={form.name} onChange={set("name")} maxLength={120} placeholder="e.g. Employment agreement, India" />
        <div className="pr-row">
          <div><label className="pr-label" htmlFor="tp-cat">Category</label>
            <input id="tp-cat" className="pr-input" value={form.category} onChange={set("category")} maxLength={60} placeholder="e.g. HR" /></div>
          <div><label className="pr-label" htmlFor="tp-by">Approved by</label>
            <input id="tp-by" className="pr-input" value={form.approved_by} onChange={set("approved_by")} maxLength={80} placeholder="Name of the lawyer or reviewer" /></div>
        </div>
        <label className="pr-label" htmlFor="tp-note">Note</label>
        <input id="tp-note" className="pr-input" value={form.note} onChange={set("note")} maxLength={300} placeholder="Where to use it, what to check" />
        <label className="pr-label" htmlFor="tp-text">Template text</label>
        <textarea id="tp-text" className="pr-textarea" rows={7} value={form.text} onChange={set("text")} placeholder="Paste the approved wording" />
        <div className="pr-actions">
          <button className="pr-btn" disabled={!form.name.trim() || !form.text.trim()} onClick={() => save(false)}>Save template</button>
          {clash && <button className="pr-btn2" onClick={() => save(true)}>Replace the existing one</button>}
        </div>
        {msg.text && <p className={msg.kind === "ok" ? "pr-okmsg" : "pr-error"} role="alert">{msg.text}</p>}
      </div>

      <h3 className="pr-h3">Saved templates ({list.length})</h3>
      {list.length === 0 && <p className="pr-muted">No templates yet.</p>}
      {list.map((t) => (
        <article key={t.id} className="pr-item tpl">
          <div className="pr-body">
            <div className="pr-tags">
              <strong>{t.name}</strong>
              {t.category && <span className="pr-tag">{t.category}</span>}
            </div>
            <p className="pr-note">
              {t.approved_by ? `Approved by ${t.approved_by}` : "Approver not recorded"} · {fmtStamp(t.approved_at)}
            </p>
            {t.note && <p className="pr-note">{t.note}</p>}
            {open && open.id === t.id ? <pre className="pr-pre">{open.text}</pre> : <p className="pr-quote">{t.preview}…</p>}
            <div className="pr-actions">
              <button className="pr-btn2" onClick={() => view(t.id)}>{open && open.id === t.id ? "Hide" : "View full text"}</button>
              {open && open.id === t.id && (
                <button className="pr-btn2" onClick={() => { try { navigator.clipboard.writeText(open.text); setMsg({ kind: "ok", text: "Copied." }); } catch (e) { setMsg({ kind: "error", text: "Could not copy. Select the text instead." }); } }}>Copy</button>
              )}
              <button className="pr-btn2 danger" onClick={() => remove(t)}>Delete</button>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function Versions() {
  const [docs, setDocs] = useState([]);
  const [cur, setCur] = useState(null);      // {id, title, versions[]}
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [author, setAuthor] = useState("");
  const [pair, setPair] = useState({ a: "", b: "" });
  const [diff, setDiff] = useState(null);
  const [msg, setMsg] = useState({ kind: "", text: "" });

  const loadDocs = () => api("/store/documents").then((d) => setDocs(d.documents)).catch(() => setMsg({ kind: "error", text: "Could not reach the backend." }));
  useEffect(() => { loadDocs(); }, []);

  async function openDoc(id) {
    try {
      const d = await api(`/store/documents/${id}/versions`);
      setCur(d); setDiff(null);
      const v = d.versions;
      setPair(v.length > 1 ? { a: String(v[1].n), b: String(v[0].n) } : { a: "", b: "" });
    } catch (e) { setMsg({ kind: "error", text: e.message }); }
  }

  async function save() {
    setMsg({ kind: "", text: "" });
    try {
      let doc = cur;
      if (!doc) {
        const created = await api("/store/documents", "POST", { title });
        doc = { id: created.id, title: created.title };
      }
      const r = await api(`/store/documents/${doc.id}/versions`, "POST", { text, note, author });
      setMsg(r.unchanged
        ? { kind: "warn", text: `Nothing saved: this text is identical to version ${r.version.n}.` }
        : { kind: "ok", text: `Saved as version ${r.version.n}.` });
      setNote("");
      await openDoc(doc.id);
      loadDocs();
    } catch (e) { setMsg({ kind: "error", text: e.message }); }
  }

  async function compare() {
    try { setDiff(await api(`/store/documents/${cur.id}/diff?a=${pair.a}&b=${pair.b}`)); } catch (e) { setMsg({ kind: "error", text: e.message }); }
  }

  async function loadIntoEditor(n) {
    try { const v = await api(`/store/documents/${cur.id}/versions/${n}`); setText(v.text); setMsg({ kind: "ok", text: `Version ${n} loaded into the editor. Edit it and save to make a new version.` }); }
    catch (e) { setMsg({ kind: "error", text: e.message }); }
  }

  async function restore(n) {
    if (!window.confirm(`Restore version ${n}? It will be saved as a new latest version. No history is lost.`)) return;
    try {
      const r = await api(`/store/documents/${cur.id}/restore`, "POST", { n, author });
      setMsg(r.unchanged ? { kind: "warn", text: `Version ${n} is already the latest text.` } : { kind: "ok", text: `Restored as version ${r.version.n}.` });
      await openDoc(cur.id); loadDocs();
    } catch (e) { setMsg({ kind: "error", text: e.message }); }
  }

  const versions = cur ? cur.versions : [];
  return (
    <div>
      <header className="pr-header">
        <h2 className="pr-h2">Version history</h2>
        <p className="pr-muted">Every save is a new numbered version. Old versions are never changed or deleted, and restoring one makes a new version on top.</p>
      </header>

      <div className="pr-row top">
        <div>
          <h3 className="pr-h3">Documents</h3>
          {docs.length === 0 && <p className="pr-muted">No documents yet. Save one on the right.</p>}
          <ul className="pr-doclist">
            {docs.map((d) => (
              <li key={d.id}>
                <button className={`pr-doc ${cur && cur.id === d.id ? "on" : ""}`} onClick={() => openDoc(d.id)}>
                  <strong>{d.title}</strong>
                  <span>{d.versions} version{d.versions === 1 ? "" : "s"}{d.updated_at ? ` · ${fmtStamp(d.updated_at)}` : ""}</span>
                </button>
              </li>
            ))}
          </ul>
          {cur && <button className="pr-btn2" onClick={() => { setCur(null); setDiff(null); setText(""); setTitle(""); }}>Start a new document</button>}
        </div>
        <div>
          <h3 className="pr-h3">{cur ? `Save a new version of "${cur.title}"` : "Save a new document"}</h3>
          {!cur && (
            <>
              <label className="pr-label" htmlFor="vh-title">Document title</label>
              <input id="vh-title" className="pr-input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="e.g. Acme services agreement" />
            </>
          )}
          <label className="pr-label" htmlFor="vh-text">Text</label>
          <textarea id="vh-text" className="pr-textarea" rows={9} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste this version of the document" />
          <div className="pr-row">
            <div><label className="pr-label" htmlFor="vh-note">What changed? (optional)</label>
              <input id="vh-note" className="pr-input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} /></div>
            <div><label className="pr-label" htmlFor="vh-by">Your name (optional)</label>
              <input id="vh-by" className="pr-input" value={author} onChange={(e) => setAuthor(e.target.value)} maxLength={80} /></div>
          </div>
          <div className="pr-actions">
            <button className="pr-btn" disabled={!text.trim() || (!cur && !title.trim())} onClick={save}>Save version</button>
          </div>
        </div>
      </div>
      {msg.text && <p className={msg.kind === "ok" ? "pr-okmsg" : msg.kind === "warn" ? "pr-hint" : "pr-error"} role="alert">{msg.text}</p>}

      {cur && (
        <section>
          <h3 className="pr-h3">History of "{cur.title}"</h3>
          {versions.length === 0 && <p className="pr-muted">No versions saved yet.</p>}
          {versions.map((v, i) => (
            <article key={v.n} className="pr-item ver">
              <div className="pr-when"><strong>Version {v.n}</strong><span>{i === 0 ? "latest" : ""}</span></div>
              <div className="pr-body">
                <p className="pr-note">{fmtStamp(v.created_at)}{v.author ? ` · ${v.author}` : ""} · {v.words} words · fingerprint {v.sha}</p>
                {v.note && <p className="pr-quote">{v.note}</p>}
                <div className="pr-actions">
                  <button className="pr-btn2" onClick={() => loadIntoEditor(v.n)}>Open in editor</button>
                  {i !== 0 && <button className="pr-btn2" onClick={() => restore(v.n)}>Restore this version</button>}
                </div>
              </div>
            </article>
          ))}
          {versions.length > 1 && (
            <div className="pr-compare">
              <h3 className="pr-h3">Compare two versions</h3>
              <div className="pr-actions">
                <label className="pr-start">From
                  <select value={pair.a} onChange={(e) => setPair({ ...pair, a: e.target.value })}>
                    {versions.map((v) => <option key={v.n} value={v.n}>Version {v.n}</option>)}
                  </select></label>
                <label className="pr-start">To
                  <select value={pair.b} onChange={(e) => setPair({ ...pair, b: e.target.value })}>
                    {versions.map((v) => <option key={v.n} value={v.n}>Version {v.n}</option>)}
                  </select></label>
                <button className="pr-btn" onClick={compare} disabled={!pair.a || !pair.b}>Show changes</button>
              </div>
              {diff && (
                <div className="ci-page ci-embed">
                  <p className="pr-muted">Version {diff.from.n} → version {diff.to.n}</p>
                  <RedlineResult data={diff} onlyChanges />
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

const TABS = [["deadlines", "Deadlines"], ["templates", "Templates"], ["versions", "Version history"]];

export default function Productivity({ initialTab = "deadlines" }) {
  const [tab, setTab] = useState(initialTab);
  return (
    <main className="pr-page">
      <div className="pr-tabs" role="tablist" aria-label="Productivity tools">
        {TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} className={`pr-tab ${tab === id ? "on" : ""}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      {tab === "deadlines" && <Deadlines />}
      {tab === "templates" && <Templates />}
      {tab === "versions" && <Versions />}
    </main>
  );
}
