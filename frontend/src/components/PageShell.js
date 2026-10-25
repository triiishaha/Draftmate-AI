import React from "react";
import "./PageShell.css";

// Puts a page to the right of the fixed sidebar and gives it the DraftMate colours.
export default function PageShell({ children }) {
  return <div className="dm-shell">{children}</div>;
}
