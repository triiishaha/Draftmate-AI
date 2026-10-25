import React, { useState } from "react";
import "./Understand.css";

// Backend address. Change this one line if the Python backend is not on port 8000.
const API =
  typeof window !== "undefined" && window.DRAFTMATE_API !== undefined
    ? window.DRAFTMATE_API
    : (process.env.REACT_APP_API_URL || "http://localhost:8000");

const EXAMPLES = [
  "Explain clause 1.1",
  "Rewrite clause 1.1 in simpler language",
  "Summarise this agreement",
  "What happens on termination?",
];

const BUDGETS = [
  [2000, "Small (2,000 tokens)"],
  [6000, "Standard (6,000 tokens)"],
  [12000, "Large (12,000 tokens)"],
];

const ACTION = {
  explain_clause: "Explain clause",
  rewrite_clause: "Rewrite clause",
  summarize_document: "Summarise document",
  general_instruction: "General instruction",
  clarification_needed: "Needs a clearer command",
};

const SpeechRecognition =
  typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : undefined;

export default function Understand() {
  const [file, setFile] = useState(null);
  const [command, setCommand] = useState("");
  const [budget, setBudget] = useState(6000);
  const [useAi, setUseAi] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState(null);
  const [listening, setListening] = useState(false);

  function dictate() {
    if (!SpeechRecognition) return;
    const rec = new SpeechRecognition();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.onresult = (e) => setCommand((prev) => (prev ? prev + " " : "") + e.results[0][0].transcript);
    rec.onend = () => setListening(false);
    rec.onerror = () => {
      setListening(false);
      setError("Could not hear that. Check the microphone permission and try again.");
    };
    setError("");
    setListening(true);
    rec.start();
  }

  async function run() {
    setBusy(true);
    setError("");
    setRes(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("command", command);
      form.append("max_tokens", String(budget));
      form.append("ai", String(useAi));
      const r = await fetch(`${API}/document/process`, { method: "POST", body: form });
      let data = null;
      try { data = await r.json(); } catch (e) { /* no body */ }
      if (!r.ok) throw new Error(data && typeof data.detail === "string" ? data.detail : `Server returned ${r.status}`);
      setRes(data);
    } catch (e) {
      setError(
        e instanceof TypeError
          ? `Could not reach the backend at ${API}. Is it running?`
          : e.message
      );
    } finally {
      setBusy(false);
    }
  }

  const ready = file && command.trim().length > 2;
  const o = res && res.optimization;
  const ctx = res && res.context;

  return (
    <main className="un-page">
      <header className="un-header">
        <h1>Understand Mode</h1>
        <p className="un-muted">
          Upload a contract, then ask about it by typing or speaking. Only the parts of the document that matter are sent
          to the AI, and you can see exactly which.
        </p>
      </header>

      <div className="un-card">
        <label className="un-label" htmlFor="un-file">Document (PDF or DOCX)</label>
        <input id="un-file" type="file" accept=".pdf,.docx" onChange={(e) => setFile(e.target.files[0] || null)} />

        <label className="un-label" htmlFor="un-cmd">What do you want to know?</label>
        <div className="un-row">
          <input
            id="un-cmd"
            className="un-input"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ready && !busy && run()}
            placeholder="e.g. Explain clause 1.1"
          />
          {SpeechRecognition && (
            <button type="button" className="un-btn2" onClick={dictate} disabled={listening} aria-label="Speak your command">
              {listening ? "Listening…" : "🎤 Speak"}
            </button>
          )}
        </div>
        <p className="un-chips">
          {EXAMPLES.map((x) => (
            <button key={x} type="button" className="un-chip" onClick={() => setCommand(x)}>{x}</button>
          ))}
        </p>

        <div className="un-row un-opts">
          <label>
            Token budget{" "}
            <select value={budget} onChange={(e) => setBudget(Number(e.target.value))}>
              {BUDGETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label>
            <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> Get an AI answer
          </label>
          <button className="un-btn" onClick={run} disabled={!ready || busy}>
            {busy ? "Reading the document…" : "Process document"}
          </button>
        </div>
        {error && <p className="un-error" role="alert">{error}</p>}
      </div>

      {res && (
        <section aria-live="polite" className="un-result">
          <p className="un-tags">
            <span className="un-tag">{ACTION[res.action] || res.action}</span>
            {res.target_clause && <span className="un-tag">Clause {res.target_clause}</span>}
            <span className="un-tag mute">Converted with {res.conversion.engine}</span>
          </p>
          {res.conversion.warnings.map((w, i) => <p key={i} className="un-warn">{w}</p>)}

          {!ctx.found && <p className="un-warn">{ctx.message || "The requested clause or context was not found."}</p>}

          {ctx.found && (
            <>
              <div className="un-metrics">
                <div><b>{o.full_document_tokens}</b><span>whole document (tokens)</span></div>
                <div><b>{o.sent_tokens}</b><span>sent to the model</span></div>
                <div><b>{o.saved_pct}%</b><span>saved</span></div>
              </div>

              {res.ai_response && (
                <div className="un-card">
                  <h2 className="un-h2">AI answer</h2>
                  <div className="un-answer">{res.ai_response}</div>
                  <p className="un-muted un-fine">Based only on the text below. AI can be wrong. Check it against the document, and have a lawyer review it.</p>
                </div>
              )}
              {res.ai_error && <p className="un-warn">{res.ai_error}</p>}
              {!res.ai_response && !res.ai_error && !useAi && <p className="un-muted">AI answer is switched off. The selected text is shown below.</p>}

              <div className="un-card">
                <h2 className="un-h2">Text sent to the model</h2>
                {ctx.section_heading && <p className="un-ctx-head">{ctx.section_heading}</p>}
                {ctx.heading && <p className="un-ctx-head">{ctx.heading}</p>}
                <pre className="un-pre">{ctx.text}</pre>
                {o.citations && o.citations.total > 0 && (
                  <p className="un-muted un-fine">Citations kept: {o.citations.kept} of {o.citations.total}</p>
                )}
              </div>

              {o.sections.length > 0 && (
                <details className="un-card">
                  <summary>Which sections were kept ({o.sections.filter((s) => s.kept).length} of {o.sections.length})</summary>
                  <ul className="un-sections">
                    {o.sections.map((s) => (
                      <li key={s.id} className={s.kept ? "kept" : "left"}>
                        <span>{s.id}. {s.title}</span>
                        <small>{s.kept ? (s.cut ? "kept, cut to fit" : "kept") : "left out"} · {s.tokens} tokens</small>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {o.cleaning.length > 0 && <p className="un-muted un-fine">Cleaned: {o.cleaning.join("; ")}.</p>}
            </>
          )}
        </section>
      )}

      <p className="un-muted un-fine">Token counts are estimates. Nothing is rewritten when the document is cut down: the original wording is kept.</p>
    </main>
  );
}
