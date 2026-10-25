import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import Research from "../Research";
import ContractIntelligence from "../ContractIntelligence";
import Productivity from "../Productivity";
import "./demo.css";

const PAGES = { research: ["Legal Research", Research], contracts: ["Contract Intelligence", ContractIntelligence], tracker: ["Deadline Tracker", Productivity] };

function App() {
  const [page, setPage] = useState(PAGES[window.location.hash.slice(1)] ? window.location.hash.slice(1) : "research");
  const Page = PAGES[page][1];
  return (
    <>
      <nav className="demo-nav" aria-label="Pages">
        <strong>DraftMate AI</strong>
        {Object.entries(PAGES).map(([id, [label]]) => (
          <button key={id} className={page === id ? "on" : ""} onClick={() => { window.location.hash = id; setPage(id); }}>{label}</button>
        ))}
      </nav>
      <Page />
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
