
require("dotenv").config();

const express = require("express");
const cors = require("cors");
const { GoogleGenAI } = require("@google/genai");

const app = express();
const PORT = process.env.PORT || 5000;

app.use(
  cors({
    origin: ["http://localhost:3000", "http://localhost:5173"],
  })
);

app.use(express.json({ limit: "50kb" }));

// Check API key
if (!process.env.GEMINI_API_KEY) {
  console.error("Missing GEMINI_API_KEY in server/.env");
  process.exit(1);
}

// Initialize Gemini
const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
});

// Supported document types and instructions
const documentGuidance = {
  "Legal Notice":
    "Prepare a formal legal notice with sender, recipient, facts, requested remedy and closing.",

  "Rental Agreement":
    "Prepare a rental agreement with parties, property, rent, deposit, term, responsibilities and signatures.",

  "Employment Contract":
    "Prepare an employment contract with role, compensation, responsibilities, leave, confidentiality and termination.",

  "Business Contract":
    "Prepare a business contract with parties, scope, payment, deliverables, timelines and termination.",

  Affidavit:
    "Prepare an affidavit-style statement using only supplied facts, with numbered statements and signature placeholders.",

  Complaint:
    "Prepare a formal complaint with parties, facts, supporting evidence and requested action.",

  "Demand Letter":
    "Prepare a demand letter with the factual basis, remedy sought and response deadline if appropriate.",

  "Formal Letter":
    "Prepare a professional formal letter with recipient, subject, details and request.",

  Application:
    "Prepare a structured application with applicant details, purpose, grounds and requested relief.",

  "Other Document":
    "Prepare the appropriate document using the supplied purpose and facts.",
};

// Helper: generate text using Gemini
// Gemini calls: retries when a model is overloaded, falls back to other models. See gemini.js.
// Optional in server/.env:  GEMINI_MODELS=gemini-3.8-flash,another-model
const { createGenerator } = require("./gemini");

const GEMINI_MODELS = (process.env.GEMINI_MODELS || "gemini-3.8-flash")
  .split(",")
  .map((name) => name.trim())
  .filter(Boolean);

const generateAIText = createGenerator(ai, GEMINI_MODELS);

// Health check
app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    service: "DraftMate AI API",
  });
});

// Research route connection test
app.get("/api/research", (req, res) => {
  res.json({
    status: "ok",
    message: "Research route is connected!",
    method: "GET",
  });
});

// Legal document drafting
app.post("/api/draft", async (req, res) => {
  try {
    const { documentType, jurisdiction, details } = req.body || {};

    if (!documentGuidance[documentType]) {
      return res.status(400).json({
        error: "Please select a supported document type.",
      });
    }

    if (
      typeof jurisdiction !== "string" ||
      !jurisdiction.trim()
    ) {
      return res.status(400).json({
        error: "Please provide the jurisdiction.",
      });
    }

    if (
      !details ||
      typeof details !== "object" ||
      Array.isArray(details)
    ) {
      return res.status(400).json({
        error: "Please provide document details.",
      });
    }

    const detailsText = Object.entries(details)
      .filter(
        ([, value]) =>
          typeof value === "string" && value.trim()
      )
      .map(([key, value]) => `${key}: ${value.trim()}`)
      .join("\n");

    if (!detailsText) {
      return res.status(400).json({
        error: "Please fill in some details.",
      });
    }

    if (detailsText.length > 15000) {
      return res.status(400).json({
        error: "Please shorten the document details.",
      });
    }

    const prompt = `
You are DraftMate AI, a legal document drafting assistant.

Document type: ${documentType}
Jurisdiction: ${jurisdiction.trim()}

Instructions:
${documentGuidance[documentType]}

User-provided details:
${detailsText}

Prepare a complete, professional document based on the supplied facts.

Rules:
- Never invent facts, names, dates, laws, legal sections or case citations.
- Use placeholders for missing information.
- Clearly flag legal details that need verification.
- Include an "Items to verify" section.
- Explain that the document should be reviewed before use.
`;

    const draft = await generateAIText(prompt);

    return res.json({ draft });
  } catch (error) {
    console.error("Draft generation error:", error.message);

    return res.status(500).json({
      error:
        "Draft generation failed. Check the backend terminal for the API error.",
    });
  }
});

// Legal research
app.post("/api/research", async (req, res) => {
  try {
    const { question, jurisdiction, history = [] } = req.body || {};

    if (
      typeof question !== "string" ||
      !question.trim()
    ) {
      return res.status(400).json({
        error: "Please enter a legal question.",
      });
    }

    if (question.length > 5000) {
      return res.status(400).json({
        error: "Please shorten your question.",
      });
    }

    const location =
      typeof jurisdiction === "string" && jurisdiction.trim()
        ? jurisdiction.trim().slice(0, 150)
        : "Not specified";

    const previousMessages = Array.isArray(history)
      ? history
          .filter(
            (item) =>
              item &&
              ["user", "assistant"].includes(item.role) &&
              typeof item.content === "string"
          )
          .slice(-8)
          .map(
            (item) =>
              `${item.role}: ${item.content.slice(0, 3000)}`
          )
          .join("\n\n")
      : "";

    const prompt = `
You are DraftMate AI, a legal research assistant.

Jurisdiction: ${location}

Previous conversation:
${previousMessages || "No previous messages."}

Current legal question:
${question.trim()}

Instructions:
- Answer clearly in simple language with useful headings.
- Explain relevant legal principles and practical next steps.
- Never invent laws, section numbers, judgments, quotations or citations.
- Clearly distinguish established information from uncertainty.
- If the jurisdiction is essential but unclear, explain this limitation.
- Suggest official sources that the user can consult.
- Do not claim that you searched the web or verified live sources.
- This is general legal information, not personalized legal advice.
- End with a short "What to verify" section when appropriate.
`;

    const answer = await generateAIText(prompt);

    return res.json({
      answer,
      citations: [],
    });
  } catch (error) {
    console.error("Research generation error:", error.message);

    return res.status(500).json({
      error:
        "Research failed. Check the backend terminal for the Gemini API error.",
    });
  }
});

// Assistant chat (used by the floating "Ask DraftMate" widget)
const LANGUAGE_NAMES = {
  en: "English", hi: "Hindi", bn: "Bengali", ta: "Tamil", te: "Telugu",
  mr: "Marathi", gu: "Gujarati", kn: "Kannada", ml: "Malayalam", pa: "Punjabi",
  ur: "Urdu", or: "Odia", as: "Assamese",
};

app.post("/api/chat", async (req, res) => {
  try {
    const { message, language, history } = req.body || {};

    if (typeof message !== "string" || !message.trim()) {
      return res.status(400).json({ error: "Please type a question." });
    }
    if (message.length > 2000) {
      return res.status(400).json({ error: "Please shorten your question." });
    }

    const code = typeof language === "string" ? language.split("-")[0].toLowerCase() : "en";
    const languageName = LANGUAGE_NAMES[code] || "English";

    const turns = (Array.isArray(history) ? history : [])
      .slice(-10)
      .filter(
        (turn) =>
          turn &&
          (turn.role === "user" || turn.role === "assistant") &&
          typeof turn.content === "string"
      )
      .map(
        (turn) =>
          `${turn.role === "user" ? "User" : "Assistant"}: ${turn.content.slice(0, 2000)}`
      )
      .join("\n");

    const prompt = `
You are DraftMate Assistant, a helpful legal drafting assistant for Indian users.

What DraftMate can do (point users to these pages when relevant):
- Drafting Workspace: generate legal notices, rental agreements, employment contracts and similar documents.
- Understand Mode: upload a contract and ask about a clause, or ask for a summary.
- Legal Research and Case Law & Citations: look up laws and check that a cited case or section really exists.
- Contract Intelligence: risk radar, redlining and comparing contract versions.
- Productivity: deadlines, templates and version history.

Rules:
- Reply in ${languageName}. Keep answers short and clear, in plain language.
- Never invent case names, citations, section numbers or facts. If you are not sure, say so and suggest checking with the Case Law & Citations page.
- This is general information, not legal advice. For anything important, advise consulting a qualified lawyer.

${turns ? "Conversation so far:\n" + turns + "\n" : ""}
User: ${message.trim()}
Assistant:`;

    const answer = await generateAIText(prompt);
    return res.json({ answer });
  } catch (error) {
    console.error("Chat error:", error.message);
    return res.status(500).json({
      error: "The assistant couldn't respond. Check the backend terminal for the API error.",
    });
  }
});

// Handle unknown API routes
app.use("/api", (req, res) => {
  res.status(404).json({
    error: "API route not found.",
    path: req.path,
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`DraftMate API running at http://localhost:${PORT}`);
});
