// Export the draft without extra libraries. Word opens the HTML as a document; PDF uses the browser's "Save as PDF".
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function html(text, title) {
  const body = text.split(/\n\s*\n/).map((p) => `<p>${esc(p).replace(/\n/g, "<br>")}</p>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title>
<style>body{font-family:"Times New Roman",serif;font-size:12pt;line-height:1.5;margin:2.5cm}p{margin:0 0 10pt}</style></head><body>${body}</body></html>`;
}

const API = (typeof process !== "undefined" && process.env && process.env.REACT_APP_API_URL) || "http://localhost:8000";

function save(blob, filename) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  URL.revokeObjectURL(a.href);
}

/** Real .docx from the backend (python-docx). Falls back to a Word-compatible .doc if the backend is unreachable. */
export async function exportDocx(text, documentType) {
  const name = `DraftMate-${documentType.replace(/\s+/g, "-")}`;
  try {
    const res = await fetch(`${API}/export/docx`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, title: documentType }),
    });
    if (!res.ok) throw new Error("export failed");
    save(await res.blob(), `${name}.docx`);
    return "docx";
  } catch (e) {
    save(new Blob([html(text, name)], { type: "application/msword" }), `${name}.doc`);
    return "doc";
  }
}

/** Real PDF from the backend (reportlab). Falls back to the browser's Save as PDF if the backend is unreachable. */
export async function exportPdf(text, documentType) {
  const name = `DraftMate-${documentType.replace(/\s+/g, "-")}`;
  try {
    const res = await fetch(`${API}/export/pdf`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, title: documentType }),
    });
    if (!res.ok) throw new Error("export failed");
    save(await res.blob(), `${name}.pdf`);
    return "pdf";
  } catch (e) {
    const w = window.open("", "_blank");
    if (!w) return "blocked";
    w.document.write(html(text, name)); w.document.close(); w.focus();
    setTimeout(() => w.print(), 300);
    return "print";
  }
}

export function exportDraft(text, documentType, format = "docx") {
  const name = `DraftMate-${documentType.replace(/\s+/g, "-")}`;
  const fmt = String(format).toLowerCase();
  if (fmt === "pdf") { exportPdf(text, documentType); return true; }
  if (fmt === "docx" || fmt === "word") { exportDocx(text, documentType); return true; }
  const isMd = fmt === "markdown" || fmt === "md";
  const blob = new Blob([isMd ? text : html(text, name)], { type: isMd ? "text/markdown;charset=utf-8" : "application/msword" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = `${name}.${isMd ? "md" : "doc"}`; a.click();
  URL.revokeObjectURL(a.href);
  return true;
}
