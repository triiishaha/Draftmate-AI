import React, { useEffect, useState } from "react";
import "./ContractIntelligence.css";

// Backend address. Change this one line if the Python backend is not on port 8000.
// A page can also set window.DRAFTMATE_API before this loads (the demo page does).
const API =
  typeof window !== "undefined" && window.DRAFTMATE_API !== undefined
    ? window.DRAFTMATE_API
    : "http://localhost:8000";

const SAMPLE_OLD = `EMPLOYMENT AGREEMENT

1. Position. The Employee shall serve as Software Engineer from 1 November 2026.

2. Salary. The Company shall pay the Employee a salary of Rs. 12,00,000 per annum, payable monthly.

3. Probation. The Employee shall be on probation for 3 months.

4. Termination. Either party may terminate this Agreement by giving 30 days' notice in writing.

5. Confidentiality. The Employee shall keep all Company information confidential.

6. Governing Law. This Agreement is governed by the laws of India and the courts at Delhi shall have jurisdiction.`;

const SAMPLE_NEW = `EMPLOYMENT AGREEMENT

1. Position. The Employee shall serve as Software Engineer from 1 November 2026.

2. Salary. The Company shall pay the Employee a salary of Rs. 14,00,000 per annum, payable monthly.

3. Probation. The Employee shall be on probation for 6 months.

4. Termination. Either party may terminate this Agreement by giving 60 days' notice in writing.

5. Confidentiality. The Employee shall keep all Company information confidential.

6. Non-Compete. The Employee shall not compete with the Company for 12 months after leaving.

7. Governing Law. This Agreement is governed by the laws of India and the courts at Mumbai shall have jurisdiction.`;

const KIND = {
  added: { label: "Added", cls: "add" },
  removed: { label: "Removed", cls: "del" },
  modified: { label: "Changed", cls: "mod" },
  unchanged: { label: "Unchanged", cls: "same" },
};

const COMPARE_STATUS = {
  same: { label: "Same", cls: "same" },
  changed: { label: "Changed", cls: "mod" },
  only_a: { label: "Only in original", cls: "del" },
  only_b: { label: "Only in revised", cls: "add" },
};

async function post(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

function readTextFile(file, done) {
  if (!file) return;
  if (!/\.(txt|md)$/i.test(file.name)) {
    done(null, "Only .txt files can be read here. For PDF or DOCX, extract the text first (Understand Mode) and paste it.");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => done(String(reader.result || ""), null);
  reader.onerror = () => done(null, "Could not read that file.");
  reader.readAsText(file);
}

function TextPane({ label, value, onChange, onError }) {
  return (
    <div className="ci-pane">
      <div className="ci-pane-head">
        <label className="ci-label">{label}</label>
        <label className="ci-file">
          Open .txt
          <input
            type="file"
            accept=".txt,.md,text/plain"
            onChange={(e) => {
              readTextFile(e.target.files[0], (text, err) => (err ? onError(err) : onChange(text)));
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <textarea
        className="ci-textarea"
        rows={12}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Paste the contract text here"
      />
    </div>
  );
}

function Segments({ segments }) {
  return (
    <p className="ci-clause-text">
      {segments.map((s, i) =>
        s.op === "delete" ? (
          <del key={i} className="ci-del">{s.text} </del>
        ) : s.op === "insert" ? (
          <ins key={i} className="ci-ins">{s.text} </ins>
        ) : (
          <span key={i}>{s.text} </span>
        )
      )}
    </p>
  );
}

export function RedlineResult({ data, onlyChanges }) {
  const s = data.summary;
  const shown = data.changes.filter((c) => !onlyChanges || c.kind !== "unchanged");
  return (
    <div className="ci-result">
      <p className="ci-summary">
        <span className="ci-chip add">{s.added} added</span>
        <span className="ci-chip del">{s.removed} removed</span>
        <span className="ci-chip mod">{s.modified} changed</span>
        <span className="ci-chip same">{s.unchanged} unchanged</span>
        <span className="ci-chip review">{s.review} need legal review</span>
      </p>
      {shown.length === 0 && <p className="ci-muted">No differences found. The two versions read the same.</p>}
      {shown.map((c, i) => (
        <article key={i} className={`ci-clause ${KIND[c.kind].cls}`}>
          <div className="ci-clause-head">
            <span className={`ci-badge ${KIND[c.kind].cls}`}>{KIND[c.kind].label}</span>
            {c.review && <span className="ci-badge review">Needs legal review</span>}
            {c.topics.slice(0, 2).map((t) => <span key={t} className="ci-topic">{t}</span>)}
          </div>
          <Segments segments={c.segments} />
          {c.details.length > 0 && (
            <ul className="ci-details">
              {c.details.map((d, j) => <li key={j}>{d}</li>)}
            </ul>
          )}
        </article>
      ))}
    </div>
  );
}

function CompareResult({ data }) {
  const s = data.summary;
  return (
    <div className="ci-result">
      <p className="ci-summary">
        <span className="ci-chip same">{s.same} same</span>
        <span className="ci-chip mod">{s.changed} changed</span>
        <span className="ci-chip del">{s.only_a} only in original</span>
        <span className="ci-chip add">{s.only_b} only in revised</span>
        <span className="ci-chip review">{s.review} need legal review</span>
      </p>
      {data.rows.length === 0 && <p className="ci-muted">No standard terms (salary, notice, termination, etc.) were found in either text.</p>}
      <div className="ci-table-wrap">
        <table className="ci-table">
          <thead>
            <tr><th>Term</th><th>Original</th><th>Revised</th><th>Status</th></tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.topic} className={r.review ? "flag" : ""}>
                <th scope="row">{r.topic}</th>
                <td>
                  {r.a ? (<><b>{r.a.value || "Mentioned"}</b><small>{r.a.quote}</small></>) : <span className="ci-muted">Not in this version</span>}
                </td>
                <td>
                  {r.b ? (<><b>{r.b.value || "Mentioned"}</b><small>{r.b.quote}</small></>) : <span className="ci-muted">Not in this version</span>}
                </td>
                <td>
                  <span className={`ci-badge ${COMPARE_STATUS[r.status].cls}`}>{COMPARE_STATUS[r.status].label}</span>
                  {r.review && <span className="ci-badge review">Needs legal review</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


const AXES = ["Termination", "Payment", "Liability", "Restrictions", "Disputes", "Clarity"];
const LEVEL_CLS = { Low: "ok", Medium: "warn", High: "bad" };
const SEV = { high: ["High", "bad"], medium: ["Medium", "warn"], low: ["Low", "same"] };
const KIND_LABEL = { risky: "Risky wording", missing: "Missing protection", unclear: "Unclear wording" };

async function get(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

function RadarChart({ axes }) {
  const size = 260, c = size / 2, r = 88;
  const names = AXES.filter((a) => a in axes);
  const pt = (i, v) => {
    const ang = (-90 + (360 / names.length) * i) * (Math.PI / 180);
    return [c + Math.cos(ang) * r * v, c + Math.sin(ang) * r * v];
  };
  const poly = (v) => names.map((_, i) => pt(i, v).join(",")).join(" ");
  const shape = names.map((n, i) => pt(i, Math.max(axes[n], 4) / 100).join(",")).join(" ");
  return (
    <svg className="ci-radar" viewBox={`0 0 ${size} ${size}`} role="img"
      aria-label={"Risk by area: " + names.map((n) => `${n} ${axes[n]} out of 100`).join(", ")}>
      {[0.25, 0.5, 0.75, 1].map((v) => <polygon key={v} points={poly(v)} className="ci-radar-grid" />)}
      {names.map((n, i) => <line key={n} x1={c} y1={c} x2={pt(i, 1)[0]} y2={pt(i, 1)[1]} className="ci-radar-grid" />)}
      <polygon points={shape} className="ci-radar-shape" />
      {names.map((n, i) => {
        const [x, y] = pt(i, 1.2);
        return (
          <text key={n} x={x} y={y} className="ci-radar-label" textAnchor={x < c - 4 ? "end" : x > c + 4 ? "start" : "middle"} dominantBaseline="middle">
            {n} {axes[n]}
          </text>
        );
      })}
    </svg>
  );
}

function RiskResult({ data }) {
  const [kindFilter, setKindFilter] = useState("all");
  const f = data.findings.filter((x) => kindFilter === "all" || x.kind === kindFilter);
  return (
    <div className="ci-result">
      <div className="ci-risk-top">
        <RadarChart axes={data.axes} />
        <div>
          <p className="ci-score">
            <span className={`ci-badge ${LEVEL_CLS[data.level]}`}>{data.level} risk</span>
            <b>{data.score}</b><span className="ci-muted">/ 100</span>
          </p>
          <p className="ci-summary">
            <span className="ci-chip bad">{data.counts.high} high</span>
            <span className="ci-chip warn">{data.counts.medium} medium</span>
            <span className="ci-chip same">{data.counts.low} low</span>
          </p>
          {!data.checked_missing && (
            <p className="ci-muted ci-small">The text is short, so checks for missing protections were skipped.</p>
          )}
          <label className="ci-label" htmlFor="ci-kind">Show</label>{" "}
          <select id="ci-kind" className="ci-select" value={kindFilter} onChange={(e) => setKindFilter(e.target.value)}>
            <option value="all">All findings</option>
            {Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
      </div>
      {data.findings.length === 0 && <p className="ci-muted">No risky, unclear or missing terms were found by our checks. That does not mean the contract is safe.</p>}
      {f.map((x) => (
        <article key={x.n} className={`ci-clause ${SEV[x.severity][1] === "bad" ? "del" : SEV[x.severity][1] === "warn" ? "mod" : "same"}`}>
          <div className="ci-clause-head">
            <span className={`ci-badge ${SEV[x.severity][1]}`}>{SEV[x.severity][0]}</span>
            <span className="ci-badge same">{KIND_LABEL[x.kind]}</span>
            <span className="ci-topic">{x.axis}</span>
          </div>
          <h3 className="ci-h3">{x.title}</h3>
          {x.quote && <blockquote className="ci-quote">{x.quote}</blockquote>}
          <p className="ci-p"><b>Why it matters.</b> {x.why}</p>
          <p className="ci-p"><b>What to ask for.</b> {x.suggestion}</p>
          {x.law && (
            <p className="ci-p ci-small">
              <b>{x.law.act}, {x.law.section}.</b> {x.law.note}{" "}
              <a href={x.law.url} target="_blank" rel="noreferrer noopener">Search on Indian Kanoon</a>
            </p>
          )}
        </article>
      ))}
      <p className="ci-fine">{data.disclaimer}</p>
    </div>
  );
}

function ImpactResult({ data }) {
  return (
    <div className="ci-result">
      <h2 className="ci-h2">{data.law}</h2>
      {data.note && <p className="ci-hint">{data.note}</p>}
      {data.impacted.length === 0 && <p className="ci-muted">No clause in this contract deals with the topics we could link to this law.</p>}
      {data.impacted.map((i) => (
        <article key={i.topic} className="ci-clause mod">
          <div className="ci-clause-head"><span className="ci-badge mod">{i.label}</span></div>
          <p className="ci-p">{i.why}</p>
          {i.clauses.map((c, j) => <blockquote key={j} className="ci-quote">{c}</blockquote>)}
        </article>
      ))}
      {data.no_clause_found.length > 0 && (
        <>
          <h3 className="ci-h3">Covered by this law, but no matching clause in your contract</h3>
          <ul className="ci-details">
            {data.no_clause_found.map((n) => <li key={n.topic}><b>{n.label}.</b> <span className="ci-muted">{n.why}</span></li>)}
          </ul>
        </>
      )}
      <h3 className="ci-h3">Read the law itself</h3>
      {data.sources.length === 0 && <p className="ci-muted ci-small">No sources could be fetched right now. Use the search link below.</p>}
      <ul className="ci-sources">
        {data.sources.map((s) => (
          <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.title}</a>{s.snippet && <small>{s.snippet}</small>}</li>
        ))}
      </ul>
      <p className="ci-p"><a href={data.search_url} target="_blank" rel="noreferrer noopener">Search this law on Indian Kanoon</a></p>
      <p className="ci-fine">{data.disclaimer}</p>
    </div>
  );
}

export default function ContractIntelligence() {
  const [tab, setTab] = useState("redline");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [onlyChanges, setOnlyChanges] = useState(true);
  const [res, setRes] = useState({ redline: null, compare: null, risk: null, impact: null });
  const [laws, setLaws] = useState([]);
  const [law, setLaw] = useState("");
  const [change, setChange] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const single = tab === "risk" || tab === "impact";
  const ready = single ? a.trim().length > 10 && (tab === "risk" || law.trim().length > 1) : a.trim().length > 10 && b.trim().length > 10;

  useEffect(() => {
    if (tab !== "impact" || laws.length) return;
    get("/contract/laws").then((d) => setLaws(d.laws)).catch(() => {});   // the box still works as free text
  }, [tab, laws.length]);

  async function run() {
    setBusy(true);
    setError("");
    try {
      const data =
        tab === "redline" ? await post("/contract/redline", { old: a, new: b })
        : tab === "compare" ? await post("/contract/compare", { a, b })
        : tab === "risk" ? await post("/contract/risk", { text: a })
        : await post("/contract/impact", { text: a, law, change: change });
      setRes((r) => ({ ...r, [tab]: data }));
    } catch (e) {
      setError("Could not analyse the contracts. Is the backend running and CORS enabled?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="ci-page">
      <header className="ci-header">
        <h1>Contract Intelligence</h1>
        <p className="ci-muted">
          Compare versions, scan for risky terms, and see which clauses a changed law touches. Everything is shown in the contract's own words. No AI is used, so nothing is invented.
        </p>
      </header>

      <div className="ci-tabs" role="tablist" aria-label="Analysis type">
        {[["redline", "Smart Redline"], ["compare", "Compare key terms"], ["risk", "Risk Radar"], ["impact", "Law change impact"]].map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} className={`ci-tab ${tab === id ? "on" : ""}`} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>

      {single ? (
        <div className="ci-panes one">
          <TextPane label="Contract text" value={a} onChange={setA} onError={setError} />
        </div>
      ) : (
        <div className="ci-panes">
          <TextPane label="Original version" value={a} onChange={setA} onError={setError} />
          <TextPane label="Revised version" value={b} onChange={setB} onError={setError} />
        </div>
      )}
      {tab === "impact" && (
        <div className="ci-impact-form">
          <label className="ci-label" htmlFor="ci-law">Which law changed?</label>
          <input id="ci-law" className="ci-input" list="ci-laws" value={law} onChange={(e) => setLaw(e.target.value)}
            placeholder="Pick from the list or type a law, e.g. Digital Personal Data Protection Act" />
          <datalist id="ci-laws">{laws.map((l) => <option key={l.id} value={l.name} />)}</datalist>
          <label className="ci-label" htmlFor="ci-change">What changed? <span className="ci-muted">(optional, in your own words)</span></label>
          <input id="ci-change" className="ci-input" value={change} onChange={(e) => setChange(e.target.value)}
            placeholder="e.g. consent is now required before sharing personal data" />
          <p className="ci-muted ci-small">You tell us the law. We never claim a law has changed. We show which clauses of your contract deal with the same subjects.</p>
        </div>
      )}

      <div className="ci-actions">
        <button className="ci-btn" onClick={run} disabled={busy || !ready}>
          {busy ? "Analysing…" : { redline: "Show changes", compare: "Compare terms", risk: "Scan for risks", impact: "Show impact" }[tab]}
        </button>
        <button className="ci-btn2" onClick={() => { setA(single ? SAMPLE_NEW : SAMPLE_OLD); setB(SAMPLE_NEW); if (tab === "impact") setLaw("Indian Contract Act, 1872"); setRes({ redline: null, compare: null, risk: null, impact: null }); }}>
          {single ? "Load sample contract" : "Load sample contracts"}
        </button>
        {tab === "redline" && (
          <label className="ci-check">
            <input type="checkbox" checked={onlyChanges} onChange={(e) => setOnlyChanges(e.target.checked)} /> Show only changes
          </label>
        )}
      </div>
      {error && <p className="ci-error" role="alert">{error}</p>}

      {tab === "redline" && res.redline && <RedlineResult data={res.redline} onlyChanges={onlyChanges} />}
      {tab === "compare" && res.compare && <CompareResult data={res.compare} />}
      {tab === "risk" && res.risk && <RiskResult data={res.risk} />}
      {tab === "impact" && res.impact && <ImpactResult data={res.impact} />}

      <p className="ci-fine">
        "Needs legal review" marks changes to money, notice, termination, non-compete, penalties, liability and governing law.
        It is a prompt to look closely, not a legal opinion. A lawyer must review the contract.
      </p>
    </main>
  );
}
