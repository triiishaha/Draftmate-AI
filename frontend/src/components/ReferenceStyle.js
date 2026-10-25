import React, { useRef, useState } from "react";
import { agentApi } from "./agentApi";
import "./ReferenceStyle.css";

/** Upload a reference document (earlier draft or template). We learn its style and hand a guide to the drafter. */
export default function ReferenceStyle({ value, onChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef(null);

  const upload = async (file) => {
    if (!file) return;
    setBusy(true); setError("");
    try {
      const p = await agentApi("/../style/profile", { method: "POST", file });
      onChange({ name: p.filename || file.name, guide: p.guide, profile: p });
    } catch (e) { setError(e.message || "Could not read that file."); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  };

  const p = value?.profile;
  return (
    <div className="rs-box">
      <div className="rs-head">
        <strong>Reference document (optional)</strong>
        <span>Upload a previous draft or template and the new draft will follow its style.</span>
      </div>
      {!value && (
        <label className="rs-pick">
          <input ref={input} type="file" accept=".pdf,.docx,.txt,.md,.html" onChange={(e) => upload(e.target.files[0])} disabled={busy} />
          {busy ? "Learning the style…" : "Choose a PDF, Word or text file"}
        </label>
      )}
      {value && p && (
        <div className="rs-done">
          <p><strong>{value.name}</strong> <button type="button" onClick={() => onChange(null)}>Remove</button></p>
          <ul>
            <li>Tone: {p.tone}</li>
            {p.obligation_verb && <li>Obligations use “{p.obligation_verb}”</li>}
            <li>Numbering: {p.numbering}</li>
            <li>Headings: {p.heading_case}</li>
            {p.defined_terms?.length > 0 && <li>Defined terms: {p.defined_terms.slice(0, 5).join(", ")}</li>}
          </ul>
          <small>Only the style is copied. Your facts, names and amounts are never taken from the reference.</small>
        </div>
      )}
      {error && <p className="rs-error" role="alert">{error}</p>}
    </div>
  );
}
