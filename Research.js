import React, { useState } from "react";
import "./Research.css";

// Backend address. Set REACT_APP_API_URL in .env if the backend is not on port 8000.
const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

// UI wording the brief asks for. The API keeps its own status names.
const STATUS = {
  verified: { label: "Verified", cls: "ok" },
  partially_verified: { label: "Needs Review", cls: "warn" },
  unverified: { label: "Not Found", cls: "bad" },
};

const TYPES = [
  { id: "all", label: "All" },
  { id: "supremecourt", label: "Supreme Court" },
  { id: "laws", label: "Laws & sections" },
];

const EXAMPLES = [
  "breach of contract",
  "Maneka Gandhi v. Union of India",
  "Section 138 Negotiable Instruments Act",
  "right to privacy",
];

async function api(path, options) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

function Marked({ text, terms }) {
  const ts = (terms || []).filter((t) => t.length > 2).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!ts.length) return text;
  return text.split(new RegExp("(" + ts.join("|") + ")", "gi")).map((part, i) =>
    i % 2 ? <mark className="rs-mark" key={i}>{part}</mark> : part
  );
}

function ResultCard({ r, terms }) {
  return (
    <article className="rs-card">
      <div className="rs-card-top">
        <span className={`rs-kind ${r.kind}`}>{r.kind === "law" ? "Law" : "Judgment"}</span>
        {r.court && <span className="rs-meta">{r.court}</span>}
        {r.year && <span className="rs-meta">{r.year}</span>}
      </div>
      <h3 className="rs-title"><Marked text={r.title} terms={terms} /></h3>
      {r.snippet ? (
        <p className="rs-snippet">
          <span className="rs-snippet-label">Extract from source</span>
          <Marked text={r.snippet} terms={terms} />
        </p>
      ) : (
        <p className="rs-snippet rs-muted">No extract returned. Open the source to read it.</p>
      )}
      <a className="rs-link" href={r.url} target="_blank" rel="noopener noreferrer">
        Open source on Indian Kanoon ↗
      </a>
    </article>
  );
}

function CitationChecker() {
  const [text, setText] = useState("");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function check() {
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      setData(
        await api("/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        })
      );
    } catch (e) {
      setData(null);
      setError("Could not reach the verifier. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rs-panel" aria-labelledby="cc-title">
      <h2 id="cc-title">Check a citation</h2>
      <p className="rs-muted">
        Paste a sentence or paragraph. Each case and section is matched against Indian Kanoon.
      </p>
      <textarea
        className="rs-textarea"
        rows={4}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="e.g. See Vishaka v. State of Rajasthan, AIR 1999 SC 3011."
      />
      <button className="rs-btn" onClick={check} disabled={busy || !text.trim()}>
        {busy ? "Checking…" : "Check citations"}
      </button>
      {error && <p className="rs-error" role="alert">{error}</p>}

      {data && (
        <div className="rs-verdicts">
          <p className="rs-summary">
            <b className="ok">{data.summary.verified}</b> Verified ·{" "}
            <b className="warn">{data.summary.partially_verified}</b> Needs Review ·{" "}
            <b className="bad">{data.summary.unverified}</b> Not Found
          </p>
          {data.items.length === 0 && <p className="rs-muted">No citations found in this text.</p>}
          {data.items.map((it, i) => {
            const s = STATUS[it.status];
            const c = it.citation;
            return (
              <div key={i} className={`rs-verdict ${s.cls}`}>
                <div className="rs-verdict-head">
                  <span className={`rs-badge ${s.cls}`}>{s.label}</span>
                  <span className="rs-verdict-name">{c.raw}</span>
                </div>
                <ul className="rs-reasons">
                  {it.reasons.map((x, j) => <li key={j}>{x}</li>)}
                </ul>
                {it.source && (
                  <a className="rs-link" href={it.source.url} target="_blank" rel="noopener noreferrer">
                    {it.source.title} ↗
                  </a>
                )}
                {it.status === "unverified" && (
                  <p className="rs-warning">No matching authority found. Do not rely on it.</p>
                )}
                {it.suggestion && <p className="rs-suggest">{it.suggestion.message}</p>}
              </div>
            );
          })}
          <p className="rs-muted rs-fine">
            "Verified" means the authority exists under that name and year. It does not mean it
            supports your argument. A lawyer must review.
          </p>
        </div>
      )}
    </section>
  );
}

export default function Research() {
  const [q, setQ] = useState("");
  const [type, setType] = useState("all");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);

  async function search(query = q, t = type, more = false) {
    const term = query.trim();
    if (term.length < 2) return;
    const next = more ? page + 1 : 0;
    setBusy(true);
    setError("");
    try {
      const data = await api(`/research?q=${encodeURIComponent(term)}&type=${t}&page=${next}`);
      setPage(next);
      setRes(
        more && res
          ? { ...data, count: res.count + data.count, results: [...res.results, ...data.results], note: data.note || res.note }
          : data
      );
    } catch (e) {
      if (!more) setRes(null);
      setError("Search failed. Is the backend running and CORS enabled?");
    } finally {
      setBusy(false);
    }
  }

  function pickType(t) {
    setType(t);
    if (q.trim().length >= 2) search(q, t);
  }

  return (
    <main className="rs-page">
      <header className="rs-header">
        <h1>Legal Research</h1>
        <p className="rs-muted">
          Every result is a real document from Indian Kanoon, with a link. Nothing is written by an AI.
        </p>
      </header>

      <form
        className="rs-search"
        onSubmit={(e) => { e.preventDefault(); search(); }}
        role="search"
      >
        <input
          className="rs-input"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search a topic, a law or a case name"
          aria-label="Search legal topics, laws or case names"
        />
        <button className="rs-btn" type="submit" disabled={busy || q.trim().length < 2}>
          {busy ? "Searching…" : "Search"}
        </button>
      </form>

      <div className="rs-tabs" role="tablist" aria-label="Result type">
        {TYPES.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={type === t.id}
            className={`rs-tab ${type === t.id ? "on" : ""}`}
            onClick={() => pickType(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {!res && !busy && !error && (
        <div className="rs-examples">
          <span className="rs-muted">Try:</span>
          {EXAMPLES.map((x) => (
            <button key={x} className="rs-chip" onClick={() => { setQ(x); search(x); }}>
              {x}
            </button>
          ))}
        </div>
      )}

      {error && <p className="rs-error" role="alert">{error}</p>}
      {busy && <p className="rs-muted" aria-live="polite">Searching Indian Kanoon…</p>}

      {res && (
        <section aria-live="polite">
          <p className="rs-count">
            {res.count} result{res.count === 1 ? "" : "s"} for “{res.query}”
          </p>
          {res.note && <p className="rs-note">{res.note}</p>}
          <div className="rs-results">
            {res.results.map((r) => <ResultCard key={r.url} r={r} terms={q.trim().split(/\s+/)} />)}
          </div>
          {res.has_more && (
            <button className="rs-btn rs-more" disabled={busy} onClick={() => search(q, type, true)}>
              {busy ? "Loading…" : "Load more results"}
            </button>
          )}
        </section>
      )}

      <CitationChecker />

      <footer className="rs-footer">Case data: Indian Kanoon API.</footer>
    </main>
  );
}
