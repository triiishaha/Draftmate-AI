import React from "react";
import { useLocation } from "react-router-dom";
import "./WorkspacePage.css";

const pageInfo = {
  "/drafter": {
    title: "Legal Drafter",
    subtitle: "Create and organise your legal drafts.",
    placeholder: "Describe the document you want to prepare...",
    action: "Start drafting",
  },
  "/research": {
    title: "Legal Research",
    subtitle: "Organise your legal research in one workspace.",
    placeholder: "Search a legal topic or enter your research question...",
    action: "Search research",
  },
  "/matters": {
    title: "Matters",
    subtitle: "Keep your cases and legal matters organised.",
    placeholder: "Search matters...",
    action: "Create matter",
  },
  "/documents": {
    title: "Documents",
    subtitle: "Manage your documents and drafts.",
    placeholder: "Search your documents...",
    action: "New document",
  },
  "/conversations": {
    title: "Conversations",
    subtitle: "Access your previous DraftMate conversations.",
    placeholder: "Search conversations...",
    action: "New conversation",
  },
  "/skills-library": {
    title: "Skills Library",
    subtitle: "Explore resources to improve your legal workflow.",
    placeholder: "Search skills and resources...",
    action: "Explore library",
  },
  "/templates": {
    title: "Templates",
    subtitle: "Start with a template for your next document.",
    placeholder: "Search document templates...",
    action: "Browse templates",
  },
  "/compliance": {
    title: "Compliance",
    subtitle: "Review requirements and organise compliance tasks.",
    placeholder: "Search compliance topics...",
    action: "Start checklist",
  },
  "/court-case-law": {
    title: "Court & Case Law",
    subtitle: "Explore your case-law research workspace.",
    placeholder: "Enter a case name, citation, or legal topic...",
    action: "Search cases",
  },
  "/ai-tools": {
    title: "AI Tools",
    subtitle: "Choose a tool for your writing and document workflow.",
    placeholder: "What would you like help with?",
    action: "Explore tools",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Manage your workspace preferences.",
    placeholder: "Search settings...",
    action: "Save preferences",
  },
};

function WorkspacePage() {
  const location = useLocation();
  const page = pageInfo[location.pathname] || pageInfo["/drafter"];

  return (
    <main className="workspace-page">
      <div className="workspace-topline">
        <span>DraftMate AI</span>
        <span className="workspace-status">Workspace</span>
      </div>

      <section className="workspace-heading">
        <p className="workspace-eyebrow">YOUR WORKSPACE</p>
        <h1>{page.title}</h1>
        <p>{page.subtitle}</p>
      </section>

      <section className="workspace-card">
        <label htmlFor="workspace-search">
          {page.title === "Legal Drafter"
            ? "What would you like to create?"
            : "Get started"}
        </label>

        <input
          id="workspace-search"
          type="text"
          placeholder={page.placeholder}
        />

        <button
          type="button"
          onClick={() =>
            window.alert("This frontend action will be connected later.")
          }
        >
          {page.action} <span aria-hidden="true">→</span>
        </button>

        <p className="workspace-note">
          Frontend preview · AI and data integration will be added later.
        </p>
      </section>
    </main>
  );
}

export default WorkspacePage;