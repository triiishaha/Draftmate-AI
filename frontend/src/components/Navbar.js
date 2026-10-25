
import React from "react";
import { NavLink, Link } from "react-router-dom";
import "./Navbar.css";

const navItems = [
  { label: "Drafting Workspace", icon: "✎", to: "/drafter" },
  { label: "Understand Mode", icon: "▤", to: "/understand" },
  { label: "Legal Research", icon: "⌕", to: "/research" },
  { label: "Case Law & Citations", icon: "§", to: "/court-case-law" },
  { label: "Contract Intelligence", icon: "◇", to: "/contract-intelligence" },
  { label: "Productivity", icon: "▦", to: "/productivity" },
];

function Navbar() {
  return (
    <aside className="sidebar">
      <Link to="/home" className="sidebar-brand">
        <span className="sidebar-logo">d.</span>

        <span className="sidebar-brand-text">
          <strong>DraftMate</strong>
          <small>Your AI Assistant in Law</small>
        </span>
      </Link>

      <div className="sidebar-divider" />

      <nav className="sidebar-nav" aria-label="Main navigation">
        <span className="sidebar-section-title">WORKSPACE</span>

        {navItems.map((item) => (
          <NavLink
            key={item.label}
            to={item.to}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? "active" : ""}`
            }
            title={item.label}
          >
            <span className="sidebar-icon" aria-hidden="true">
              {item.icon}
            </span>

            <span className="sidebar-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <Link to="/help" className="sidebar-help">
          <span className="help-icon">?</span>
          <div>
            <strong>Need some help?</strong>
            <small>Explore DraftMate</small>
          </div>
        </Link>

        <div className="sidebar-version">
          <span className="version-dot" />
          DraftMate AI · Workspace
        </div>
      </div>
    </aside>
  );
}

export default Navbar;
