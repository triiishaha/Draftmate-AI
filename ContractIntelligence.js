import React, { useState } from "react";
import { api } from "./api";
import "./ContractIntelligence.css";

const TABS = [
  { id: "risk", label: "Risk Radar" },
  { id: "compare", label: "Compare & Redline" },
  { id: "impact", label: "Legal Change Impact" },
];

function DocInput({ label, value, onChange }) {
  const [err, setErr] = useState("");
  const upload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setErr("");
    try { onChange((await api("/extract", { method: "POST", file })).text); }
    catch (ex) { setErr(ex.message); }
    e.target.value = "";
  };
  return (
    <div className="ci-doc">
      <div className="ci-doc-head">
        <label>{label}</label>
        <label className="ci-link">Upload .txt, .pdf or .docx
          <input type="file" accept=".txt,.pdf,.docx" onChange={upload} hidden />
        </label>
      </div>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder="Paste contract text here" rows={12} />
      {err && <p className="ci-error">{err}</p>}
    </div>
  );
}

const Sev = ({ s }) => <span className={`ci-sev ci-sev-${s}`}>{s}</span>;

function RiskRadar() {
  const [text, setText] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const run = async () => {
    setBusy(true); setErr("");
    try { setRes(await api("/analyze", { method: "POST", body: { text } })); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <section>
      <DocInput label="Contract" value={text} onChange={setText} />
      <button className="ci-btn" disabled={!text.trim() || busy} onClick={run}>{busy ? "Analysing…" : "Analyse risks"}</button>
      {err && <p className="ci-error">{err}</p>}
      {res && (
        <div className="ci-results">
          <div className={`ci-score ci-level-${res.level.toLowerCase()}`}>
            <strong>{res.score}</strong><span>/100 risk score · {res.level} risk · {res.clause_count} clauses read</span>
          </div>
          <h3>Risky or unclear clauses ({res.flags.length})</h3>
          {res.flags.length === 0 && <p className="ci-empty">No risky wording matched our rules.</p>}
          {res.flags.map((f, i) => (
            <article key={i} className={`ci-card ci-border-${f.severity}`}>
              <header><h4>{f.title}</h4><Sev s={f.severity} /></header>
              <p className="ci-excerpt">{f.excerpt}</p>
              <p><b>Why it matters:</b> {f.why}</p>
              <p><b>Suggestion:</b> {f.suggestion}</p>
            </article>
          ))}
          <h3>Missing clauses ({res.missing.length})</h3>
          {res.missing.map((m) => (
            <article key={m.id} className={`ci-card ci-border-${m.severity}`}>
              <header><h4>{m.title}</h4><Sev s={m.severity} /></header>
              <p>{m.why} {m.suggestion}</p>
            </article>
          ))}
          <p className="ci-disclaimer">Automated screening only. Have a lawyer review anything marked high.</p>
        </div>
      )}
    </section>
  );
}

function Compare() {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const run = async () => {
    setBusy(true); setErr("");
    try { setRes(await api("/compare", { method: "POST", body: { text_a: a, text_b: b } })); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <section>
      <div className="ci-two">
        <DocInput label="Version A (old)" value={a} onChange={setA} />
        <DocInput label="Version B (new)" value={b} onChange={setB} />
      </div>
      <button className="ci-btn" disabled={!a.trim() || !b.trim() || busy} onClick={run}>{busy ? "Comparing…" : "Compare versions"}</button>
      {err && <p className="ci-error">{err}</p>}
      {res && (
        <div className="ci-results">
          <div className="ci-stats">
            <span className="ci-chip ci-added">{res.stats.added} added</span>
            <span className="ci-chip ci-removed">{res.stats.removed} removed</span>
            <span className="ci-chip ci-changed">{res.stats.changed} changed</span>
            <span className="ci-chip">{res.stats.unchanged} unchanged</span>
            <span className="ci-chip ci-review">{res.needs_review} need legal review</span>
          </div>
          <h3>Key terms</h3>
          <div className="ci-table-wrap">
            <table className="ci-table">
              <thead><tr><th>Term</th><th>Version A</th><th>Version B</th><th>Status</th></tr></thead>
              <tbody>
                {res.terms.map((t) => (
                  <tr key={t.term} className={`ci-row-${t.status}`}>
                    <td>{t.term}</td><td>{t.a || "—"}</td><td>{t.b || "—"}</td><td>{t.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>Redline</h3>
          {res.changes.length === 0 && <p className="ci-empty">The two versions are identical.</p>}
          {res.changes.map((c, i) => (
            <article key={i} className="ci-card">
              <header><h4>{c.type[0].toUpperCase() + c.type.slice(1)} clause</h4>
                {c.review.length > 0 && <span className="ci-sev ci-sev-high">needs review</span>}</header>
              <p className="ci-redline">
                {c.words.map((w, j) => <span key={j} className={`ci-w-${w.op}`}>{w.t} </span>)}
              </p>
              {c.review.map((r, j) => <p key={j} className="ci-note"><Sev s={r.severity} /> {r.title}: {r.why}</p>)}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function Impact() {
  const [text, setText] = useState("");
  const [topics, setTopics] = useState([]);
  const [topic, setTopic] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  React.useEffect(() => {
    api("/impact/topics").then((t) => { setTopics(t); setTopic(t[0]?.id || ""); }).catch((e) => setErr(e.message));
  }, []);
  const run = async () => {
    setErr("");
    try { setRes(await api("/impact", { method: "POST", body: { text, topic } })); }
    catch (e) { setErr(e.message); }
  };
  return (
    <section>
      <DocInput label="Contract" value={text} onChange={setText} />
      <div className="ci-inline">
        <label htmlFor="ci-topic">Law that changed</label>
        <select id="ci-topic" value={topic} onChange={(e) => setTopic(e.target.value)}>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.label} — {t.law}</option>)}
        </select>
        <button className="ci-btn" disabled={!text.trim() || !topic} onClick={run}>Find affected clauses</button>
      </div>
      {err && <p className="ci-error">{err}</p>}
      {res && !res.error && (
        <div className="ci-results">
          <h3>{res.affected.length} clause(s) may need review under {res.law}</h3>
          {res.affected.map((h, i) => (
            <article key={i} className="ci-card ci-border-medium">
              <header><h4>Clause {h.clause_index + 1}</h4><span className="ci-chip">matched “{h.matched}”</span></header>
              <p className="ci-excerpt">{h.excerpt}</p>
              <p>{h.action}</p>
            </article>
          ))}
          <p><b>Sources:</b> {res.sources.map((s) => <a key={s} href={s} target="_blank" rel="noreferrer" className="ci-src">{s}</a>)}</p>
          <p className="ci-disclaimer">{res.note}</p>
        </div>
      )}
    </section>
  );
}

export default function ContractIntelligence() {
  const [tab, setTab] = useState("risk");
  return (
    <main className="ci-page">
      <h1>Contract Intelligence</h1>
      <p className="ci-sub">Check a contract for risk, compare versions, and see which clauses a law change touches.</p>
      <div className="ci-tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      {tab === "risk" && <RiskRadar />}
      {tab === "compare" && <Compare />}
      {tab === "impact" && <Impact />}
    </main>
  );
}
