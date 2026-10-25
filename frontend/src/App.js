
import React from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";

import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import WorkspacePage from "./pages/WorkspacePage";
import Drafter from "./pages/Drafter";
import Research from "./pages/Research";
import ChatAssistant from "./components/ChatAssistant";
import PageShell from "./components/PageShell";
import Understand from "./pages/Understand";
import ContractIntelligence from "./pages/ContractIntelligence";
import Productivity from "./pages/Productivity";
import CaseLaw from "./pages/CaseLaw";

import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <Navbar />

      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />

        <Route path="/home" element={<Home />} />

        <Route path="/drafter" element={<Drafter />} />

        <Route path="/research" element={<Research />} />

        {/* Pages served by the Python backend (localhost:8000) */}
        <Route path="/understand" element={<PageShell><Understand /></PageShell>} />

        <Route path="/contract-intelligence" element={<PageShell><ContractIntelligence /></PageShell>} />

        <Route path="/productivity" element={<PageShell><Productivity /></PageShell>} />

        <Route path="/court-case-law" element={<PageShell><CaseLaw /></PageShell>} />

        <Route path="/templates" element={<PageShell><Productivity initialTab="templates" /></PageShell>} />

        <Route path="/documents" element={<PageShell><Productivity initialTab="versions" /></PageShell>} />

        <Route path="/matters" element={<WorkspacePage />} />

        <Route path="/conversations" element={<WorkspacePage />} />

        <Route path="/skills-library" element={<WorkspacePage />} />

        <Route path="/compliance" element={<WorkspacePage />} />

        <Route path="/ai-tools" element={<WorkspacePage />} />

        <Route path="/settings" element={<WorkspacePage />} />

        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>

      <ChatAssistant />
    </BrowserRouter>
  );
}

export default App;
