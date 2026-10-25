import React, { useEffect, useRef, useState } from "react";
import { agentApi } from "./agentApi";
import { SkillChips } from "./SkillsLibrary";
import VoiceAgent from "./VoiceAgent";
import { exportDraft } from "./exportDraft";
import { DocumentUpload, PromptMeter, TokenSavings } from "./ContextTools";
import "./DraftAssistant.css";

/**
 * AI assistant under the draft: pick a skill (chips, library, or voice), pick a model,
 * type or speak an instruction. Results are shown as a proposal and only replace the
 * draft after the user confirms. Voice delete/overwrite are confirmed by the voice agent first.
 */
export default function DraftAssistant({ styleGuide, draft, setDraft, documentType, onVerify }) {
  const [models, setModels] = useState([]);
  const [tier, setTier] = useState("");
  const [skill, setSkill] = useState(null);
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState(null);   // { text, mode: "replace" | "append", skill }
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [attachments, setAttachments] = useState([]);   // uploaded reference materials (converted to Markdown)
  const [templates, setTemplates] = useState([]);       // saved templates available in the store
  const [picked, setPicked] = useState([]);             // templates added to this request
  const [budget, setBudget] = useState(3000);
  const [stats, setStats] = useState(null);
  const [check, setCheck] = useState(null);             // meaning check of the current proposal
  const history = useRef([]);
  const draftRef = useRef(draft);
  draftRef.current = draft;

  useEffect(() => {
    agentApi("/models").then((m) => { setModels(m); if (m[0]) setTier(m[0].id); }).catch(() => setError("Could not reach the skills backend on port 8000."));
  }, []);

  useEffect(() => {
    agentApi("/../store/templates").then((r) => setTemplates(r.templates || [])).catch(() => {});
  }, []);

  const addTemplate = async (id) => {
    if (!id || picked.some((t) => String(t.id) === String(id))) return;
    try {
      const t = await agentApi(`/../store/templates/${id}`);
      setPicked((p) => [...p, { id: t.id ?? id, name: `Template: ${t.name}`, markdown: t.text || t.body || "" }]);
    } catch (e) { setError("Could not load that template."); }
  };

  const change = (text, message) => {
    history.current.push(draftRef.current);
    setDraft(text);
    setNote(message || "");
  };

  const run = async (instr, chosen = skill, mode = "replace") => {
    const useSkill = chosen || { id: "agreement-drafting", name: "Drafting assistant" };
    setBusy(true); setError(""); setProposal(null); setCheck(null);
    try {
      const r = await agentApi("/skills/run", {
        method: "POST",
        body: {
          skill_id: useSkill.id,
          instruction: `${instr}\n\nWork on the current draft below. Keep all facts and substantive meaning unless told otherwise. Return the full revised text only, as plain text without markdown symbols such as #, ** or ---.${styleGuide ? `\n\nREFERENCE STYLE GUIDE (follow it for tone and structure; take no facts from it):\n${styleGuide}` : ""}`,
          full_text: draftRef.current,                       // the draft is always sent whole, never trimmed
          documents: [...attachments, ...picked].map((d) => ({ name: d.name, markdown: d.markdown })),
          budget_tokens: budget,                             // only attached material is trimmed to this budget
          tier,
        },
      });
      setStats(r.context_stats);
      if (r.result.error) throw new Error(r.result.error);
      if (r.result.dry_run) throw new Error("No model key is set on the backend, so nothing was generated.");
      setProposal({ text: r.result.text, mode, skill: r.skill.name });
      setCheck(null);
      if (mode === "replace") {
        agentApi("/../style/check", { method: "POST", body: { original: draftRef.current, revised: r.result.text } })
          .then(setCheck).catch(() => {});
      }
    } catch (e) {
      setError(e.message || "The assistant could not answer. Try again.");
    } finally { setBusy(false); }
  };

  const FORMATS = [
    ["Clean up numbering and headings", "Reformat only. Renumber clauses consecutively (1, 1.1, 1.2), make all headings consistent in UPPERCASE, and fix spacing. Do not change any wording, facts or amounts."],
    ["Letterhead / formal letter layout", "Lay the text out as a formal letter: sender block, date, recipient block, subject line in UPPERCASE, salutation, numbered body paragraphs, closing and signature block. Keep every fact. Use [BRACKETS] for anything missing."],
    ["Contract layout (title, parties, clauses)", "Lay the text out as a formal contract: title, date and place, parties block, recitals, numbered operative clauses with sub-clauses, signature block. Keep every fact and obligation. Use [BRACKETS] for anything missing."],
    ["Plain-English tidy", "Shorten long sentences and replace unnecessary legal jargon with plain words. Keep every fact, amount, date, deadline and obligation exactly as they are."],
  ];

  // Typed box: "@contract-review check this" or "review this contract" picks the skill from the words.
  const submitTyped = async (raw) => {
    const mention = raw.match(/@[a-z0-9-]+/i);
    const text = raw.replace(/@[a-z0-9-]+/gi, "").trim();
    setError(""); setNote("");
    let chosen = skill;
    if (mention || !skill) {
      try {
        const r = await agentApi("/skills/route", { method: "POST", body: { query: raw } });
        if (r.skill && (mention || r.confidence >= 0.34)) {
          chosen = { id: r.skill.id, name: r.skill.name };
          setSkill(chosen);
          setNote(mention ? `Skill: ${r.skill.name}` : `Using ${r.skill.name}, picked from your words. Change it with the chips above.`);
        } else if (mention) {
          const alt = r.alternatives?.map((a) => a.name).join(", ");
          setError(`No skill matches ${mention[0]}.${alt ? ` Did you mean: ${alt}?` : ""}`);
          return;
        }
      } catch (e) { /* routing is optional: fall back to the selected or default skill */ }
    }
    if (!text) { setNote((n) => n || "Skill selected. Now type what you want it to do."); return; }
    run(text, chosen);
  };

  const apply = () => {
    if (!proposal) return;
    change(proposal.mode === "append" ? `${draftRef.current.trimEnd()}\n\n${proposal.text}` : proposal.text, `Applied ${proposal.skill}. Undo is available.`);
    setProposal(null);
  };

  const undo = () => {
    if (!history.current.length) { setNote("Nothing to undo."); return; }
    setDraft(history.current.pop()); setNote("Last change undone.");
  };

  const paragraphs = (t) => t.split(/\n\s*\n/);
  const onVoice = (a) => {
    const p = a.params || {};
    setNote("");
    switch (a.intent) {
      case "activate_skill":
        setSkill({ id: p.skill_id, name: p.skill_name }); setNote(`Skill: ${p.skill_name}`);
        if (p.instruction) run(p.instruction, { id: p.skill_id, name: p.skill_name });
        break;
      case "replace_text": {
        if (!draftRef.current.includes(p.find)) { setNote(`“${p.find}” was not found in the draft.`); break; }
        change(draftRef.current.split(p.find).join(p.replace), `Replaced “${p.find}” with “${p.replace}”.`);
        break;
      }
      case "rewrite": run(p.style ? `Rewrite the whole draft to be more ${p.style}.` : `Rewrite ${p.scope || "the draft"} ${p.number || ""}.`); break;
      case "insert": run(p.instruction, skill, "append"); break;
      case "instruction": run(p.instruction); break;
      case "dictate_text": change(`${draftRef.current.trimEnd()} ${p.text}`.trim(), "Dictated text added."); break;
      case "overwrite_document": change("", "Draft cleared. Say undo to bring it back."); break;
      case "delete": {
        const parts = paragraphs(draftRef.current);
        if (["document", "draft", "everything"].includes(p.target)) change("", "Draft deleted. Say undo to bring it back.");
        else if (p.number && parts[p.number - 1] !== undefined) { parts.splice(p.number - 1, 1); change(parts.join("\n\n"), `Deleted ${p.target} ${p.number}.`); }
        else setNote("Say which one to delete, for example “delete paragraph 2”.");
        break;
      }
      case "export": exportDraft(draftRef.current, documentType, p.format || "docx"); setNote(`Exported as ${p.format || "docx"}.`); break;
      case "verify_citations": onVerify?.(); break;
      case "read_aloud": if (window.speechSynthesis) { window.speechSynthesis.cancel(); window.speechSynthesis.speak(new SpeechSynthesisUtterance(draftRef.current)); } break;
      case "undo": undo(); break;
      default: break;
    }
  };

  return (
    <section className="da-box" aria-label="AI assistant">
      <header className="da-head">
        <h3>AI assistant</h3>
        <label className="da-model">Model
          <select value={tier} onChange={(e) => setTier(e.target.value)} disabled={!models.length}>
            {models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
        </label>
      </header>

      <SkillChips onSelect={(s) => { setSkill(s); setNote(`Skill: ${s.name}`); }} onMore={() => window.open("/skills-library", "_blank")} />
      {skill && <p className="da-skill">Using <strong>{skill.name}</strong> <button type="button" onClick={() => setSkill(null)}>clear</button></p>}

      <details className="da-attach">
        <summary>Reference materials and templates{attachments.length + picked.length > 0 ? ` (${attachments.length + picked.length} attached)` : ""}</summary>
        <DocumentUpload onChange={setAttachments} />
        <div className="da-row">
          <label>Saved template
            <select value="" onChange={(e) => addTemplate(e.target.value)}>
              <option value="">{templates.length ? "Add a template…" : "No saved templates yet (save one in Productivity)"}</option>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <label>Material to send
            <select value={budget} onChange={(e) => setBudget(Number(e.target.value))}>
              <option value={1500}>Small (about 1,500 tokens)</option>
              <option value={3000}>Normal (about 3,000 tokens)</option>
              <option value={6000}>Large (about 6,000 tokens)</option>
            </select>
          </label>
        </div>
        {picked.length > 0 && <ul className="da-picked">{picked.map((t) => <li key={t.id}>{t.name} <button type="button" onClick={() => setPicked(picked.filter((x) => x.id !== t.id))}>remove</button></li>)}</ul>}
        <p className="da-hint">Your draft is always sent whole. Only attached material is trimmed to the budget, keeping the parts relevant to your request.</p>
      </details>

      <form className="da-ask" onSubmit={(e) => { e.preventDefault(); if (instruction.trim()) { submitTyped(instruction.trim()); setInstruction(""); } }}>
        <input value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Tell the AI what to do. Type @ and a skill name, e.g. @contract-review check clause 2" aria-label="Instruction for the AI" />
        <button type="submit" disabled={busy || !instruction.trim()}>{busy ? "Working…" : "Run"}</button>
      </form>

      <PromptMeter prompt={instruction} />
      <label className="da-format">Format the draft
        <select value="" disabled={busy || !draft.trim()} onChange={(e) => { const f = FORMATS[e.target.value]; if (f) run(f[1]); }}>
          <option value="">Choose a layout or clean-up…</option>
          {FORMATS.map((f, i) => <option key={f[0]} value={i}>{f[0]}</option>)}
        </select>
      </label>

      <VoiceAgent sessionId="drafter" onAction={onVoice} />

      {proposal && (
        <div className="da-proposal" role="alertdialog" aria-label="Review proposed change">
          <strong>{proposal.skill} proposes {proposal.mode === "append" ? "an addition" : "a revised draft"}</strong>
          <pre>{proposal.text}</pre>
          {check && (
            <div className={`da-check ${check.ok ? "ok" : "warn"}`} role="status">
              <strong>{check.summary}</strong>
              {Object.entries(check.missing || {}).map(([k, v]) => <p key={"m" + k}>Missing {k}: {v.join(", ")}</p>)}
              {Object.entries(check.added || {}).map(([k, v]) => <p key={"a" + k}>New {k}: {v.join(", ")}</p>)}
              {check.obligations && <p>{check.obligations}</p>}
            </div>
          )}
          <button type="button" className="da-yes" onClick={apply}>{proposal.mode === "append" ? "Add to draft" : "Replace draft"}</button>
          <button type="button" onClick={() => setProposal(null)}>Discard</button>
        </div>
      )}
      <TokenSavings stats={stats} />
      {error && <p className="da-error" role="alert">{error}</p>}
      {note && <p className="da-note">{note}</p>}
      <div className="da-tools">
        <button type="button" onClick={undo}>Undo</button>
        <button type="button" onClick={() => exportDraft(draft, documentType, "docx")}>Export Word (.docx)</button>
        <button type="button" onClick={() => exportDraft(draft, documentType, "pdf")}>Export PDF</button>
      </div>
    </section>
  );
}
