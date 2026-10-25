// Export the draft without extra libraries. Word opens the HTML as a document; PDF uses the browser's "Save as PDF".
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function html(text, title) {
  const body = text.split(/\n\s*\n/).map((p) => `<p>${esc(p).replace(/\n/g, "<br>")}</p>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title>
<style>body{font-family:"Times New Roman",serif;font-size:12pt;line-height:1.5;margin:2.5cm}p{margin:0 0 10pt}</style></head><body>${body}</body></html>`;
}

export function exportDraft(text, documentType, format = "docx") {
  const name = `DraftMate-${documentType.replace(/\s+/g, "-")}`;
  const fmt = String(format).toLowerCase();
  if (fmt === "pdf") {
    const w = window.open("", "_blank");
    if (!w) return false;
    w.document.write(html(text, name)); w.document.close(); w.focus();
    setTimeout(() => w.print(), 300);
    return true;
  }
  const isMd = fmt === "markdown" || fmt === "md";
  const blob = new Blob([isMd ? text : html(text, name)], { type: isMd ? "text/markdown;charset=utf-8" : "application/msword" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = `${name}.${isMd ? "md" : "doc"}`; a.click();
  URL.revokeObjectURL(a.href);
  return true;
}
