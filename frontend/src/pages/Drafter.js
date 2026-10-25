
import React, { useState } from "react";
import {
  FileText,
  Sparkles,
  Copy,
  Download,
  RotateCcw,
  LoaderCircle,
} from "lucide-react";
import VerifyPanel from "../components/VerifyPanel";
import DraftAssistant from "../components/DraftAssistant";
import ReferenceStyle from "../components/ReferenceStyle";
import "./Drafter.css";

const fieldsByType = {
  "Legal Notice": [
    ["senderName", "Your full name", "e.g. Aditi Sharma"],
    ["senderAddress", "Your address", "Enter your address"],
    ["recipientName", "Recipient's full name", "e.g. Landlord's name"],
    ["recipientAddress", "Recipient's address", "Enter their address"],
    ["issue", "What is the issue?", "Explain what happened and why you need the notice."],
    ["dates", "Important dates", "Mention relevant dates."],
    ["demand", "What outcome do you want?", "e.g. Return the security deposit"],
    ["deadline", "Response deadline (if any)", "e.g. Within 15 days"],
  ],
  "Rental Agreement": [
    ["landlord", "Landlord's full name", "Full legal name"],
    ["tenant", "Tenant's full name", "Full legal name"],
    ["property", "Property address", "Full property address"],
    ["rent", "Monthly rent", "e.g. ₹15,000"],
    ["deposit", "Security deposit", "e.g. ₹30,000"],
    ["duration", "Agreement duration", "e.g. 11 months"],
    ["startDate", "Start date", "DD/MM/YYYY"],
    ["noticePeriod", "Notice period", "e.g. 30 days, if agreed"],
    ["terms", "Other terms", "Maintenance, utilities, restrictions, etc."],
  ],
  "Employment Contract": [
    ["employer", "Employer / company name", "Legal name"],
    ["employee", "Employee full name", "Full legal name"],
    ["role", "Job title and responsibilities", "Describe the role"],
    ["startDate", "Employment start date", "DD/MM/YYYY"],
    ["salary", "Salary / compensation", "Enter agreed compensation"],
    ["workTerms", "Working arrangements", "Location, hours, leave, etc."],
    ["specialTerms", "Additional terms", "Confidentiality, probation, etc."],
  ],
  "Business Contract": [
    ["partyA", "First party", "Name and address"],
    ["partyB", "Second party", "Name and address"],
    ["purpose", "Purpose of agreement", "Describe the business arrangement"],
    ["deliverables", "Services / deliverables", "What each party will provide"],
    ["payment", "Payment terms", "Amount, schedule, and currency"],
    ["timeline", "Timeline", "Start date and milestones"],
    ["otherTerms", "Additional terms", "Confidentiality, termination, etc."],
  ],
  Affidavit: [
    ["deponent", "Deponent's full name", "Full legal name"],
    ["address", "Deponent's address", "Current address"],
    ["facts", "Statements of fact", "Write the facts you personally confirm."],
    ["purpose", "Purpose of affidavit", "Why is the affidavit required?"],
    ["placeDate", "Place and date", "Enter place and date"],
  ],
  Complaint: [
    ["complainant", "Your name and contact details", "Enter your details"],
    ["recipient", "Complaint addressed to", "Authority / organisation / person"],
    ["incidentDate", "Date of incident", "DD/MM/YYYY, if known"],
    ["incident", "Describe what happened", "Explain the incident in order."],
    ["evidence", "Supporting evidence", "List available documents or evidence."],
    ["resolution", "Action requested", "What action do you want taken?"],
  ],
  "Demand Letter": [
    ["sender", "Sender details", "Name and address"],
    ["recipient", "Recipient details", "Name and address"],
    ["reason", "Reason for demand", "Explain the facts."],
    ["amount", "Amount or remedy requested", "Amount, if applicable"],
    ["deadline", "Requested response date", "Enter date if agreed"],
  ],
  "Formal Letter": [
    ["sender", "Sender details", "Name and address"],
    ["recipient", "Recipient details", "Name and address"],
    ["subject", "Letter subject", "What is the letter about?"],
    ["details", "Letter details", "Explain what you want to communicate."],
    ["request", "Your request", "What response or action do you want?"],
  ],
  Application: [
    ["applicant", "Applicant details", "Name and address"],
    ["authority", "Addressed to", "Authority / organisation"],
    ["purpose", "Purpose of application", "What are you applying for?"],
    ["grounds", "Supporting facts", "Explain your circumstances."],
    ["request", "Requested action", "What approval or action do you seek?"],
  ],
  "Other Document": [
    ["documentPurpose", "What document do you need?", "Describe the document type."],
    ["parties", "People or organisations involved", "Add names if known."],
    ["facts", "Describe the situation", "Explain the relevant facts."],
    ["desiredOutcome", "Desired outcome", "What should the document achieve?"],
  ],
};

const documentTypes = Object.keys(fieldsByType);

function Drafter() {
  const [documentType, setDocumentType] = useState("Legal Notice");
  const [jurisdiction, setJurisdiction] = useState("India");
  const [details, setDetails] = useState({});
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [generated, setGenerated] = useState(false);
  const [reference, setReference] = useState(null);

  const currentFields = fieldsByType[documentType];

  function changeType(type) {
    setDocumentType(type);
    setDetails({});
    setDraft("");
    setError("");
    setGenerated(false);
  }

  function updateField(key, value) {
    setDetails((previous) => ({ ...previous, [key]: value }));
  }

  async function generateDraft() {
    const hasDetails = currentFields.some(
      ([key]) => details[key]?.trim()
    );

    if (!hasDetails) {
      setError("Please enter the details for your document first.");
      return;
    }

    setLoading(true);
    setError("");
    setGenerated(false);

    try {
      const response = await fetch("http://localhost:5000/api/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          documentType,
          jurisdiction,
          details,
          styleGuide: reference?.guide || "",
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Could not generate the draft.");
      }

      setDraft(data.draft);
      setGenerated(true);
    } catch (err) {
      setError(
        err.message ||
          "Could not connect to the backend. Check that the server is running."
      );
    } finally {
      setLoading(false);
    }
  }

  async function copyDraft() {
    try {
      await navigator.clipboard.writeText(draft);
      alert("Draft copied!");
    } catch {
      setError("Copy was blocked by your browser. Please select the draft and copy it manually.");
    }
  }

  function downloadDraft() {
    const blob = new Blob([draft], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `DraftMate-${documentType.replace(/\s+/g, "-")}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function resetForm() {
    setDetails({});
    setDraft("");
    setError("");
    setGenerated(false);
  }

  return (
    <main className="drafter-page">
      <header className="drafter-topbar">
        <div>
          <span className="drafter-breadcrumb">Workspace / Drafter</span>
          <h1>Legal Drafter</h1>
          <p>Tell us what you need. Get a document tailored to your details.</p>
        </div>

        <div className="drafter-status">
          <span />
          AI drafting workspace
        </div>
      </header>

      <div className="drafter-layout">
        <section className="drafter-input-panel">
          <div className="drafter-panel-heading">
            <div className="drafter-heading-icon">
              <FileText size={20} />
            </div>
            <div>
              <h2>Document details</h2>
              <p>Fill in the information relevant to your case.</p>
            </div>
          </div>

          <label htmlFor="document-type">Document type</label>
          <select
            id="document-type"
            value={documentType}
            onChange={(e) => changeType(e.target.value)}
          >
            {documentTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>

          <label htmlFor="jurisdiction">Jurisdiction</label>
          <select
            id="jurisdiction"
            value={jurisdiction}
            onChange={(e) => setJurisdiction(e.target.value)}
          >
            <option>India</option>
            <option>United States</option>
            <option>United Kingdom</option>
            <option>Other / not sure</option>
          </select>

          <ReferenceStyle value={reference} onChange={setReference} />

          {currentFields.map(([key, label, placeholder]) => (
            <div className="drafter-field" key={key}>
              <label htmlFor={key}>{label}</label>
              <textarea
                id={key}
                rows={key === "issue" || key === "facts" ||
                  key === "incident" || key === "terms" ||
                  key === "details" || key === "grounds" ? 4 : 2}
                value={details[key] || ""}
                onChange={(e) => updateField(key, e.target.value)}
                placeholder={placeholder}
              />
            </div>
          ))}

          <div className="drafter-tip">
            <Sparkles size={17} />
            <p>
              Enter accurate details. Leave unknown information blank;
              the AI should flag missing details instead of inventing them.
            </p>
          </div>

          {error && (
            <div className="drafter-error" role="alert">
              {error}
            </div>
          )}

          <button
            type="button"
            className="drafter-generate-btn"
            onClick={generateDraft}
            disabled={loading}
          >
            {loading ? (
              <>
                <LoaderCircle size={18} className="drafter-spinner" />
                Generating your draft...
              </>
            ) : (
              <>
                <Sparkles size={18} />
                Generate legal draft
              </>
            )}
          </button>

          <button
            type="button"
            className="drafter-reset-btn"
            onClick={resetForm}
            disabled={loading}
          >
            <RotateCcw size={15} />
            Clear details
          </button>
        </section>

        <section className="drafter-output-panel">
          <div className="drafter-output-heading">
            <div>
              <span className="drafter-output-eyebrow">AI-GENERATED DOCUMENT</span>
              <h2>Draft preview</h2>
              <p>Edit the generated text before using it.</p>
            </div>
            {generated && (
              <div className="drafter-ready-tag">
                <span />
                Draft ready
              </div>
            )}
          </div>

          {loading ? (
            <div className="drafter-empty-state">
              <LoaderCircle size={34} className="drafter-spinner" />
              <h3>Preparing your document...</h3>
              <p>AI is organising your details into a draft. This may take a little while.</p>
            </div>
          ) : !generated ? (
            <div className="drafter-empty-state">
              <div className="drafter-empty-icon">
                <FileText size={30} />
              </div>
              <h3>Your draft will appear here</h3>
              <p>
                Choose a document type, fill in its details, and generate
                your personalised draft.
              </p>
              <div className="drafter-empty-steps">
                <span>01</span> Select document type
                <span>02</span> Enter your details
                <span>03</span> Generate and edit
              </div>
            </div>
          ) : (
            <div className="drafter-document">
              <div className="drafter-document-toolbar">
                <span><FileText size={16} /> {documentType}</span>
                <div>
                  <button type="button" onClick={copyDraft}>
                    <Copy size={15} /> Copy
                  </button>
                  <button type="button" onClick={downloadDraft}>
                    <Download size={15} /> Download
                  </button>
                </div>
              </div>

              <textarea
                className="drafter-document-editor"
                aria-label="Edit generated legal document"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                spellCheck="true"
              />

              <p className="drafter-edit-hint">
                Changes are editable in this preview. Download to keep a copy.
              </p>

              <DraftAssistant styleGuide={reference?.guide} draft={draft} setDraft={setDraft} documentType={documentType} onVerify={() => document.querySelector(".vp-panel")?.scrollIntoView({ behavior: "smooth" })} />

              <VerifyPanel text={draft} />
            </div>
          )}
        </section>
      </div>

      <footer className="drafter-disclaimer">
        <strong>Review before use.</strong> AI-generated documents may be
        incomplete or incorrect. Check all facts, local legal requirements,
        and important terms with a qualified legal professional before signing
        or sending.
      </footer>
    </main>
  );
}

export default Drafter;
