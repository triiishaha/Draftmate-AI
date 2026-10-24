import React, { useCallback, useEffect, useRef, useState } from "react";
import { agentApi } from "./agentApi";
import "./VoiceAgent.css";

const SR = typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;
const LABEL = { idle: "Ready", listening: "Listening", processing: "Working on it", awaiting_confirmation: "Waiting for your confirmation", done: "Done", error: "Problem" };

/**
 * Props
 *  sessionId    unique id per user session
 *  onAction(a)  called with {intent, params, ...} when a command should run in the workspace
 *               (activate_skill, replace_text, rewrite, insert, delete, overwrite_document, export,
 *                verify_citations, read_aloud, undo, instruction). Delete/overwrite only arrive AFTER the user confirms.
 *  onDictation(text) called with each dictated phrase while dictation mode is on
 */
export default function VoiceAgent({ sessionId = "default", onAction, onDictation }) {
  const [status, setStatus] = useState("idle");
  const [lang, setLang] = useState("en-IN");
  const [heard, setHeard] = useState("");
  const [msg, setMsg] = useState("");
  const [pending, setPending] = useState(null);
  const [dictating, setDictating] = useState(false);
  const [typed, setTyped] = useState("");
  const rec = useRef(null);
  const dictRef = useRef(false);
  const pendRef = useRef(false);

  const speak = useCallback((text, then) => {
    if (!text || !window.speechSynthesis) { then?.(); return; }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text); u.lang = lang; u.onend = () => then?.();
    window.speechSynthesis.speak(u);
  }, [lang]);

  const run = useCallback((r) => { if (r.status === "ok" || r.status === "confirmed") onAction?.(r); }, [onAction]);

  const listen = useCallback(() => {
    if (!SR) return;
    try { rec.current?.abort(); } catch (e) { /* ignore */ }
    const r = new SR();
    r.lang = lang; r.interimResults = true; r.continuous = false;
    r.onstart = () => setStatus("listening");
    r.onresult = (e) => {
      const res = e.results[e.results.length - 1];
      setHeard(res[0].transcript);
      if (res.isFinal) send(res[0].transcript);
    };
    r.onerror = (e) => { setStatus("error"); setMsg(e.error === "not-allowed" ? "Microphone access is blocked. Allow it in the browser address bar." : `Speech error: ${e.error}`); };
    r.onend = () => { if (dictRef.current || pendRef.current) setTimeout(listen, 250); else setStatus((s) => (s === "listening" ? "idle" : s)); };
    rec.current = r; r.start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const send = useCallback(async (text) => {
    if (!text.trim()) return;
    setStatus("processing"); setHeard(text);
    try {
      const r = await agentApi("/voice/command", { method: "POST", body: { session_id: sessionId, transcript: text } });
      if (r.intent === "start_dictation") { dictRef.current = true; setDictating(true); }
      if (r.intent === "stop_dictation") { dictRef.current = false; setDictating(false); }
      if (r.intent === "dictate_text") { onDictation?.(r.params.text); setStatus("listening"); return; }
      const waiting = r.status === "awaiting_confirmation";
      pendRef.current = waiting; setPending(waiting ? r : null);
      setStatus(waiting ? "awaiting_confirmation" : r.status === "error" ? "error" : "done");
      setMsg(r.feedback);
      run(r);
      speak(r.feedback, () => { if (waiting) listen(); });
    } catch (e) { setStatus("error"); setMsg(e.message); }
  }, [sessionId, onDictation, run, speak, listen]);

  const decide = async (accept) => {
    try {
      const r = await agentApi("/voice/confirm", { method: "POST", body: { session_id: sessionId, accept } });
      pendRef.current = false; setPending(null); setStatus("done"); setMsg(r.feedback); run(r); speak(r.feedback);
    } catch (e) { setStatus("error"); setMsg(e.message); }
  };

  useEffect(() => () => { try { rec.current?.abort(); window.speechSynthesis?.cancel(); } catch (e) { /* ignore */ } }, []);

  const toggle = () => {
    if (status === "listening") { dictRef.current = false; setDictating(false); try { rec.current?.stop(); } catch (e) { /* ignore */ } setStatus("idle"); }
    else { setMsg(""); listen(); }
  };

  return (
    <div className="va-box" aria-live="polite">
      <div className="va-row">
        <button className={`va-mic ${status === "listening" ? "on" : ""}`} onClick={toggle} disabled={!SR} aria-pressed={status === "listening"} aria-label={status === "listening" ? "Stop listening" : "Start voice command"}>
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V22h2v-3.1A7 7 0 0 0 19 12h-2Z"/></svg>
        </button>
        <div className="va-status">
          <strong>{LABEL[status]}{dictating ? " · dictation on" : ""}</strong>
          <span>{heard ? `“${heard}”` : SR ? "Try: “use contract review”, “make it more formal”, “export as Word”." : "Voice input is not supported in this browser. Type a command instead."}</span>
        </div>
        <select aria-label="Speech language" value={lang} onChange={(e) => setLang(e.target.value)}>
          <option value="en-IN">English (India)</option><option value="hi-IN">Hindi</option><option value="en-US">English (US)</option><option value="en-GB">English (UK)</option>
        </select>
      </div>
      {msg && <p className={`va-msg ${status === "error" ? "bad" : ""}`}>{msg}</p>}
      {pending && (
        <div className="va-confirm" role="alertdialog" aria-label="Confirm action">
          <p>{pending.feedback}</p>
          <button className="va-yes" onClick={() => decide(true)}>Confirm</button>
          <button className="va-no" onClick={() => decide(false)}>Cancel</button>
        </div>
      )}
      <form className="va-type" onSubmit={(e) => { e.preventDefault(); send(typed); setTyped(""); }}>
        <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Or type a command" aria-label="Type a voice command" />
      </form>
    </div>
  );
}
