import React, { useEffect, useRef, useState } from "react";
import { agentApi } from "./agentApi";
import "./ContextTools.css";

/** Real-time prompt quality bar with an "Improve prompt" tips list. */
export function PromptMeter({ prompt }) {
  const [r, setR] = useState(null);
  const [show, setShow] = useState(false);
  const timer = useRef(null);
  useEffect(() => {
    clearTimeout(timer.current);
    if (!prompt.trim()) { setR(null); return; }
    timer.current = setTimeout(() => agentApi("/prompt/score", { method: "POST", body: { prompt } }).then(setR).catch(() => {}), 350);
    return () => clearTimeout(timer.current);
  }, [prompt]);
  if (!r) return null;
  return (
    <div className="ct-meter">
      <div className="ct-meter-row">
        <span>Prompt strength: <b>{r.score}% · {r.label}</b></span>
        <div className="ct-bar" role="progressbar" aria-valuenow={r.score} aria-valuemin={0} aria-valuemax={100}><i className={`ct-${r.label.toLowerCase()}`} style={{ width: `${r.score}%` }} /></div>
        {r.tips.length > 0 && <button className="ct-link" onClick={() => setShow(!show)}>{show ? "Hide tips" : "Improve prompt"}</button>}
      </div>
      {show && <ul className="ct-tips">{r.tips.map((t) => <li key={t}>{t}</li>)}</ul>}
    </div>
  );
}

/** Upload documents, convert to Markdown (MarkItDown) and show token savings. onChange gets [{name, markdown, tokens}]. */
export function DocumentUpload({ onChange }) {
  const [docs, setDocs] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const update = (next) => { setDocs(next); onChange?.(next); };
  const add = async (e) => {
    setErr(""); setBusy(true);
    const added = [];
    for (const file of Array.from(e.target.files)) {
      try { const r = await agentApi("/convert", { method: "POST", file }); added.push({ name: r.filename, markdown: r.markdown, tokens: r.tokens, raw: r.raw_tokens, engine: r.engine }); }
      catch (ex) { setErr(`${file.name}: ${ex.message}`); }
    }
    e.target.value = ""; setBusy(false);
    if (added.length) update([...docs, ...added]);
  };
  const total = docs.reduce((n, d) => n + d.tokens, 0);

  return (
    <div className="ct-up">
      <label className="ct-pick">{busy ? "Converting…" : "Add documents"}
        <input type="file" multiple hidden onChange={add} accept=".pdf,.docx,.pptx,.xlsx,.html,.csv,.txt,.md" />
      </label>
      {err && <p className="ct-err">{err}</p>}
      {docs.length === 0 && <p className="ct-hint">PDF, Word, PowerPoint, Excel, HTML and text files are converted to Markdown before use.</p>}
      <ul className="ct-docs">
        {docs.map((d, i) => (
          <li key={d.name + i}>
            <span>{d.name}</span>
            <small>{d.tokens.toLocaleString()} tokens{d.raw > d.tokens ? ` (cleaned from ${d.raw.toLocaleString()})` : ""} · {d.engine}</small>
            <button className="ct-link" onClick={() => update(docs.filter((_, j) => j !== i))}>Remove</button>
          </li>
        ))}
      </ul>
      {docs.length > 0 && <p className="ct-hint">{total.toLocaleString()} tokens attached. Only the parts relevant to each request are sent to the model.</p>}
    </div>
  );
}

/** Shows what context trimming saved after a skill run (pass result.context_stats). */
export function TokenSavings({ stats }) {
  if (!stats || !stats.original_tokens) return null;
  return (
    <p className="ct-saved">
      Sent {stats.final_tokens.toLocaleString()} of {stats.original_tokens.toLocaleString()} tokens ({stats.saved_pct}% saved) using {stats.chunks_used} of {stats.chunks_total} sections.
      {stats.citations_in_source > 0 && ` Citations kept: ${stats.citations_kept}/${stats.citations_in_source}.`}
    </p>
  );
}
