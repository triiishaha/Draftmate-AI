import React, { useState } from "react";
import "./CaseLaw.css";

// Backend address. Change this one line if the Python backend is not on port 8000.
// A page can also set window.DRAFTMATE_API before this loads (the demo page does).
const API =
  typeof window !== "undefined" && window.DRAFTMATE_API !== undefined
    ? window.DRAFTMATE_API
    : "http://localhost:8000";

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

function ResultCard({ r, terms, q, summary }) {
  const [pass, setPass] = useState(null);
  const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true);
    try {
      const id = (r.url.match(/doc\/(\d+)/) || [])[1];
      setPass(await api(`/research/doc/${id}?q=${encodeURIComponent(q)}`));
    } catch (e) {
      setPass({ ok: false, note: "Could not load the passage." });
    } finally {
      setBusy(false);
    }
  }
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
          <span className="rs-snippet-label">Relevant paragraph from the source</span>
          <Marked text={r.snippet} terms={terms} />
        </p>
      ) : (
        <p className="rs-snippet rs-muted">No extract returned. Open the source to read it.</p>
      )}
      {summary && (
        <p className="rs-aisum">
          <span className="rs-snippet-label">Short summary (AI, from the paragraph above)</span>
          {summary}{" "}
          <a className="rs-link" href={r.url} target="_blank" rel="noopener noreferrer">Source ↗</a>
        </p>
      )}
      <div className="rs-actions">
        {!pass && (
          <button className="rs-btn2" onClick={load} disabled={busy}>
            {busy ? "Loading…" : "Show relevant passages"}
          </button>
        )}
        <a className="rs-link" href={r.url} target="_blank" rel="noopener noreferrer">
          Open source on Indian Kanoon ↗
        </a>
      </div>
      {pass && (
        <div className="rs-passages">
          {pass.ok
            ? pass.passages.map((x, i) => (
                <blockquote className="rs-quote" key={i}><Marked text={x} terms={terms} /></blockquote>
              ))
            : <p className="rs-muted">{pass.note || "No passage available."}</p>}
        </div>
      )}
    </article>
  );
}

function CitationChecker() {
  const [text, setText] = useState("");
  const [checked, setChecked] = useState(null); // { text, data }: spans in data point into text
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState(-1);

  async function check(body = text) {
    if (!body.trim()) return;
    setBusy(true);
    setError("");
    try {
      const data = await api("/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: body }),
      });
      setChecked({ text: body, data });
    } catch (e) {
      setError("Could not reach the verifier. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  // Replace the cited text at its span, then re-verify (later spans shift after an edit).
  function applyFix(it) {
    const t = checked.text;
    const [a, b] = it.citation.span;
    if (t.slice(a, b) !== it.citation.raw) return check(t);
    const next = t.slice(0, a) + it.suggestion.replace_with + t.slice(b);
    setText(next);
    check(next);
  }

  function jump(i) {
    const node = document.getElementById(`verdict-${i}`);
    if (node) node.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlash(i);
    setTimeout(() => setFlash(-1), 1200);
  }

  function highlighted() {
    const { text: t, data } = checked;
    const parts = [];
    let pos = 0;
    data.items
      .map((it, i) => ({ it, i }))
      .sort((x, y) => x.it.citation.span[0] - y.it.citation.span[0])
      .forEach(({ it, i }) => {
        const [a, b] = it.citation.span;
        if (a < pos || b > t.length) return;
        parts.push(t.slice(pos, a));
        parts.push(
          <mark
            key={i}
            className={`rs-hl ${STATUS[it.status].cls}`}
            tabIndex={0}
            title={STATUS[it.status].label}
            onClick={() => jump(i)}
            onKeyDown={(e) => e.key === "Enter" && jump(i)}
          >
            {t.slice(a, b)}
          </mark>
        );
        pos = b;
      });
    parts.push(t.slice(pos));
    return parts;
  }

  const data = checked && checked.data;
  const stale = checked && text !== checked.text;

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
      <button className="rs-btn" onClick={() => check()} disabled={busy || !text.trim()}>
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
          {stale && <p className="rs-note">You edited the draft after this check. Click Check citations again.</p>}
          {data.items.length === 0 && <p className="rs-muted">No citations found in this text.</p>}
          {data.items.length > 0 && (
            <>
              <h3 className="rs-sub">Your draft, checked</h3>
              <p className="rs-legend">
                {Object.values(STATUS).map((s) => (
                  <span key={s.label}><span className={`rs-dot ${s.cls}`} />{s.label}{"   "}</span>
                ))}
              </p>
              <div className="rs-draft">{highlighted()}</div>
            </>
          )}
          {data.items.map((it, i) => {
            const s = STATUS[it.status];
            return (
              <div key={i} id={`verdict-${i}`} className={`rs-verdict ${s.cls}${flash === i ? " flash" : ""}`}>
                <div className="rs-verdict-head">
                  <span className={`rs-badge ${s.cls}`}>{s.label}</span>
                  <span className="rs-verdict-name">{it.citation.raw}</span>
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
                {it.suggestion && (
                  <>
                    <p className="rs-suggest">{it.suggestion.message}</p>
                    {it.suggestion.replace_with && (
                      <>
                        <button className="rs-btn2" disabled={stale || busy} onClick={() => applyFix(it)}>
                          Apply fix: {it.suggestion.replace_with}
                        </button>
                        <p className="rs-muted rs-fine">This fixes the year only. Check the reporter reference yourself.</p>
                      </>
                    )}
                  </>
                )}
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

export default function CaseLaw() {
  const [q, setQ] = useState("");
  const [type, setType] = useState("all");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [sum, setSum] = useState(null);
  const [aiSums, setAiSums] = useState({});

  // One AI call for the page of results. The AI sees only the extracts the server already returned.
  async function fetchSummaries(results, query, reset) {
    const items = results.filter((r) => r.snippet).map((r) => ({ url: r.url, title: r.title, snippet: r.snippet }));
    if (reset) setAiSums({});
    if (!items.length) return;
    try {
      const d = await api("/research/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, results: items }),
      });
      setAiSums((prev) => ({ ...prev, ...(d.summaries || {}) }));
    } catch (e) {
      /* optional: extracts and links are already on screen */
    }
  }
  const [sumBusy, setSumBusy] = useState(false);

  async function summarise() {
    setSumBusy(true);
    try {
      setSum(await api(`/research/answer?q=${encodeURIComponent(res.query)}`));
    } catch (e) {
      setSum({ answer: [], sources: [], note: "Could not summarise. Is the backend running?" });
    } finally {
      setSumBusy(false);
    }
  }

  async function search(query = q, t = type, more = false) {
    const term = query.trim();
    if (term.length < 2) return;
    const next = more ? page + 1 : 0;
    if (!more) setSum(null);
    setBusy(true);
    setError("");
    try {
      const data = await api(`/research?q=${encodeURIComponent(term)}&type=${t}&page=${next}`);
      setPage(next);
      fetchSummaries(data.results, data.query, !more);
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
          <div className="rs-actions">
            <button className="rs-btn2" onClick={summarise} disabled={sumBusy}>
              {sumBusy ? "Summarising…" : "Summarise from sources"}
            </button>
            <span className="rs-muted rs-fine">Uses only the extracts below. Every sentence cites its source.</span>
          </div>
          {sum && (
            <div className="rs-summarybox">
              <h2>Summary from sources</h2>
              {sum.answer.length ? (
                sum.answer.map((a, i) => (
                  <p key={i}>
                    {a.text} {a.sources.map((n) => <sup className="rs-cite" key={n}>[{n}]</sup>)}
                  </p>
                ))
              ) : (
                <p className="rs-muted">{sum.note || "No summary available."}</p>
              )}
              <ol className="rs-srclist">
                {sum.sources.map((s) => (
                  <li key={s.url}><a className="rs-link" href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a></li>
                ))}
              </ol>
              <p className="rs-muted rs-fine">Written from the extracts only. Open each source to confirm before relying on it.</p>
            </div>
          )}
          <div className="rs-results">
            {res.results.map((r) => <ResultCard key={r.url} r={r} q={res.query} summary={aiSums[r.url]} terms={q.trim().split(/\s+/)} />)}
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
