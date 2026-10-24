import React, { useEffect, useMemo, useState } from "react";
import { agentApi } from "./agentApi";
import "./SkillsLibrary.css";

const AUDIENCES = [["all", "All Skills"], ["lawyer", "For Lawyers"], ["student", "For Law Students"]];

// Quick strip shown above the chat box: top skills + "More". Click or type @skill-id to activate.
export function SkillChips({ onSelect, onMore, ids = ["contract-review", "redlining", "case-law-research", "agreement-drafting", "case-analysis", "legal-notice-drafting", "document-summarisation", "due-diligence"] }) {
  const [skills, setSkills] = useState([]);
  useEffect(() => { agentApi("/skills").then((r) => setSkills(r.skills)).catch(() => {}); }, []);
  const shown = ids.map((id) => skills.find((s) => s.id === id)).filter(Boolean);
  return (
    <div className="sk-chips" role="group" aria-label="Legal skills">
      {shown.map((s) => <button key={s.id} className="sk-chip" onClick={() => onSelect?.(s)}>{s.name}</button>)}
      {onMore && <button className="sk-chip sk-more" onClick={onMore}>More</button>}
    </div>
  );
}

function CustomSkillForm({ onSaved }) {
  const [f, setF] = useState({ name: "", description: "", instruction: "" });
  const [err, setErr] = useState("");
  const save = async () => {
    setErr("");
    try { const s = await agentApi("/skills/custom", { method: "POST", body: f }); setF({ name: "", description: "", instruction: "" }); onSaved(s); }
    catch (e) { setErr(e.message); }
  };
  return (
    <div className="sk-custom">
      <input placeholder="Skill name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
      <input placeholder="What it does (one line)" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
      <textarea rows={4} placeholder="Instructions the model should follow" value={f.instruction} onChange={(e) => setF({ ...f, instruction: e.target.value })} />
      <button className="sk-btn" disabled={!f.name.trim() || !f.instruction.trim()} onClick={save}>Save skill</button>
      {err && <p className="sk-error">{err}</p>}
    </div>
  );
}

export default function SkillsLibrary({ onSelect }) {
  const [data, setData] = useState({ skills: [], categories: {} });
  const [q, setQ] = useState("");
  const [aud, setAud] = useState("all");
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);
  const [active, setActive] = useState(null);

  const load = () => agentApi("/skills").then(setData).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const grouped = useMemo(() => {
    const ql = q.trim().toLowerCase();
    const g = {};
    data.skills.forEach((s) => {
      if (aud !== "all" && !s.audience.includes(aud)) return;
      if (ql && !(s.name + " " + s.description).toLowerCase().includes(ql)) return;
      (g[s.category] = g[s.category] || []).push(s);
    });
    return g;
  }, [data, q, aud]);

  const pick = (s) => { setActive(s.id); onSelect?.(s); };
  const count = Object.values(grouped).reduce((n, a) => n + a.length, 0);

  return (
    <section className="sk-page">
      <header className="sk-head">
        <div><h2>Legal Skills Library</h2><p>{count} skills. Click one to use it, or type @ and a skill name in the chat box.</p></div>
        <input type="search" aria-label="Search skills" placeholder="Search skills" value={q} onChange={(e) => setQ(e.target.value)} />
      </header>
      <div className="sk-filters" role="tablist">
        {AUDIENCES.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={aud === id} className={aud === id ? "on" : ""} onClick={() => setAud(id)}>{label}</button>
        ))}
        <button className="sk-add" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add custom skill"}</button>
      </div>
      {adding && <CustomSkillForm onSaved={() => { setAdding(false); load(); }} />}
      {err && <p className="sk-error">{err}</p>}
      {count === 0 && !err && <p className="sk-empty">No skills match. Try a different word, or add your own skill.</p>}
      <div className="sk-grid">
        {Object.entries(grouped).map(([cat, list]) => (
          <div key={cat} className="sk-col">
            <h3>{cat}</h3>
            <ul>
              {list.map((s) => (
                <li key={s.id}>
                  <button className={active === s.id ? "sk-item on" : "sk-item"} onClick={() => pick(s)} title={s.description}>
                    <span>{s.name}</span>
                    <small>{s.description}{s.needs_document ? " · needs a document" : ""}</small>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
