import React, { useState } from "react";
import "./VerifyPanel.css";

// Backend address. Change this one line if the Python backend is not on port 8000.
const API =
  typeof window !== "undefined" && window.DRAFTMATE_API !== undefined
    ? window.DRAFTMATE_API
    : "http://localhost:8000";

// Wording from the brief. The API keeps its own status names.
const STATUS = {
  verified: { label: "Verified", cls: "ok" },
  partially_verified: { label: "Needs Review", cls: "warn" },
  unverified: { label: "Not Found", cls: "bad" },
};

export default function VerifyPanel({ text }) {
  const [state, setState] = useState({ busy: false, error: "", data: null, checked: "" });

  async function check() {
    setState((s) => ({ ...s, busy: true, error: "" }));
    try {
      const res = await fetch(`${API}/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      setState({ busy: false, error: "", data: await res.json(), checked: text });
    } catch (e) {
      setState((s) => ({
        ...s,
        busy: false,
        error: `Could not reach the verifier at ${API}. Is the Python backend running?`,
      }));
    }
  }

  const { busy, error, data, checked } = state;
  const stale = data && checked !== text;

  return (
    <section className="vp-panel" aria-label="Citation check">
      <div className="vp-head">
        <div>
          <h3>Citation check</h3>
          <p>Checks every case and section cited in this draft against a legal source.</p>
        </div>
        <button type="button" className="vp-btn" onClick={check} disabled={busy || !text.trim()}>
          {busy ? "Checking…" : data ? "Check again" : "Check citations"}
        </button>
      </div>

      {error && <p className="vp-error" role="alert">{error}</p>}

      {data && (
        <div aria-live="polite">
          <p className="vp-summary">
            <span className="vp-chip ok">{data.summary.verified} Verified</span>
            <span className="vp-chip warn">{data.summary.partially_verified} Needs Review</span>
            <span className="vp-chip bad">{data.summary.unverified} Not Found</span>
          </p>
          {stale && <p className="vp-note">You edited the draft after this check. Click Check again.</p>}
          {data.items.length === 0 && <p className="vp-muted">No citations were found in this draft.</p>}
          {data.items.map((it, i) => {
            const s = STATUS[it.status] || STATUS.unverified;
            return (
              <article key={i} className={`vp-item ${s.cls}`}>
                <div className="vp-item-head">
                  <span className={`vp-badge ${s.cls}`}>{s.label}</span>
                  <strong>{it.citation.raw}</strong>
                </div>
                {it.reasons && it.reasons.length > 0 && (
                  <ul>{it.reasons.map((r, j) => <li key={j}>{r}</li>)}</ul>
                )}
                {it.source && (
                  <a href={it.source.url} target="_blank" rel="noopener noreferrer">{it.source.title} ↗</a>
                )}
                {it.status === "unverified" && <p className="vp-warn">No matching authority found. Do not rely on it.</p>}
                {it.suggestion && it.suggestion.message && <p className="vp-suggest">{it.suggestion.message}</p>}
              </article>
            );
          })}
          <p className="vp-muted vp-fine">
            "Verified" means the authority exists under that name and year. It does not mean it supports your argument.
            A lawyer must review every citation.
          </p>
        </div>
      )}
    </section>
  );
}
