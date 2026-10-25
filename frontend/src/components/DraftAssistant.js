import React, { useEffect, useRef, useState } from "react";
import { agentApi } from "./agentApi";
import { SkillChips } from "./SkillsLibrary";
import VoiceAgent from "./VoiceAgent";
import { exportDraft } from "./exportDraft";
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
  const history = useRef([]);
  const draftRef = useRef(draft);
  draftRef.current = draft;

  useEffect(() => {
    agentApi("/models").then((m) => { setModels(m); if (m[0]) setTier(m[0].id); }).catch(() => setError("Could not reach the skills backend on port 8000."));
  }, []);

  const change = (text, message) => {
    history.current.push(draftRef.current);
    setDraft(text);
    setNote(message || "");
  };

  const run = async (instr, chosen = skill, mode = "replace") => {
    const useSkill = chosen || { id: "agreement-drafting", name: "Drafting assistant" };
    setBusy(true); setError(""); setProposal(null); setNote("");
    try {
      const r = await agentApi("/skills/run", {
        method: "POST",
        body: {
          skill_id: useSkill.id,
          instruction: `${instr}\n\nWork on the current draft below. Keep all facts and substantive meaning unless told otherwise. Return the full revised text only.${styleGuide ? `\n\nREFERENCE STYLE GUIDE (follow it for tone and structure; take no facts from it):\n${styleGuide}` : ""}`,
          documents: [{ name: `Current ${documentType}`, markdown: draftRef.current }],
          tier,
        },
      });
      if (r.result.error) throw new Error(r.result.error);
      if (r.result.dry_run) throw new Error("No model key is set on the backend, so nothing was generated.");
      setProposal({ text: r.result.text, mode, skill: r.skill.name });
    } catch (e) {
      setError(e.message || "The assistant could not answer. Try again.");
    } finally { setBusy(false); }
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

      <form className="da-ask" onSubmit={(e) => { e.preventDefault(); if (instruction.trim()) run(instruction.trim()); }}>
        <input value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Tell the AI what to change, e.g. make clause 2 stricter" aria-label="Instruction for the AI" />
        <button type="submit" disabled={busy || !instruction.trim()}>{busy ? "Working…" : "Run"}</button>
      </form>

      <VoiceAgent sessionId="drafter" onAction={onVoice} />

      {proposal && (
        <div className="da-proposal" role="alertdialog" aria-label="Review proposed change">
          <strong>{proposal.skill} proposes {proposal.mode === "append" ? "an addition" : "a revised draft"}</strong>
          <pre>{proposal.text}</pre>
          <button type="button" className="da-yes" onClick={apply}>{proposal.mode === "append" ? "Add to draft" : "Replace draft"}</button>
          <button type="button" onClick={() => setProposal(null)}>Discard</button>
        </div>
      )}
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
