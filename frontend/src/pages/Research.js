
import React, { useRef, useState } from "react";
import {
  Search,
  Send,
  Scale,
  Copy,
  ExternalLink,
  Sparkles,
  RotateCcw,
  BookOpen,
  LoaderCircle,
} from "lucide-react";
import "./Research.css";

const suggestions = [
  "What are a tenant's rights if the landlord refuses to return the deposit?",
  "What should an employment contract include?",
  "How can a consumer file a complaint?",
  "Explain the difference between a civil and criminal case.",
];

function Research() {
  const [question, setQuestion] = useState("");
  const [jurisdiction, setJurisdiction] = useState("India");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  async function askQuestion(text = question) {
    const trimmedQuestion = text.trim();

    if (!trimmedQuestion || loading) return;

    const previousHistory = messages.map((message) => ({
      role: message.role,
      content: message.content,
    }));

    const userMessage = {
      id: `${Date.now()}-user`,
      role: "user",
      content: trimmedQuestion,
    };

    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${(process.env.REACT_APP_NODE_URL || "http://localhost:5000")}/api/research`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          jurisdiction,
          history: previousHistory,
        }),
      });
const rawResponse = await response.text();

let data;

try {
  data = JSON.parse(rawResponse);
} catch {
  console.error("Non-JSON response:", rawResponse.slice(0, 500));

  throw new Error(
    "Backend returned HTML instead of JSON. Check localhost:5000/api/research and restart the backend."
  );
}

if (!response.ok) {
  throw new Error(data.error || "Unable to complete legal research.");
}

      setMessages((current) => [
        ...current,
        {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          content: data.answer,
          citations: data.citations || [],
        },
      ]);

      setTimeout(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } catch (err) {
      setError(
        err.message === "Failed to fetch"
          ? "Cannot connect to DraftMate's backend. Make sure your server is running on port 5000."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  }

  async function copyAnswer(content) {
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      setError("Could not copy automatically. Please select and copy the answer.");
    }
  }

  function startNewResearch() {
    if (loading) return;
    setMessages([]);
    setQuestion("");
    setError("");
  }

  return (
    <main className="research-page">
      <header className="research-header">
        <div>
          <div className="research-eyebrow">
            <Scale size={15} />
            DRAFTMATE AI / RESEARCH
          </div>
          <h1>Legal Research</h1>
          <p>
            Ask legal questions, explore relevant laws, and discover
            sources to help you understand the answer.
          </p>
        </div>

        <button
          className="research-new-btn"
          onClick={startNewResearch}
          disabled={loading}
        >
          <RotateCcw size={15} />
          New research
        </button>
      </header>

      <section className="research-workspace">
        <div className="research-toolbar">
          <div className="research-tool-title">
            <div className="research-icon-box">
              <BookOpen size={19} />
            </div>
            <div>
              <strong>Research assistant</strong>
              <span>AI-assisted legal information</span>
            </div>
          </div>

          <label className="research-jurisdiction">
            <span>Jurisdiction</span>
            <select
              value={jurisdiction}
              onChange={(event) => setJurisdiction(event.target.value)}
              disabled={loading}
            >
              <option value="India">India</option>
              <option value="United States">United States</option>
              <option value="United Kingdom">United Kingdom</option>
              <option value="Canada">Canada</option>
              <option value="Australia">Australia</option>
              <option value="Not specified">Other / not specified</option>
            </select>
          </label>
        </div>

        <div className="research-conversation">
          {messages.length === 0 ? (
            <div className="research-welcome">
              <div className="research-welcome-icon">
                <Sparkles size={25} />
              </div>

              <h2>What would you like to understand?</h2>
              <p>
                Ask a legal question in your own words. Include the country
                or state when it matters.
              </p>

              <div className="research-suggestions">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    className="research-suggestion"
                    onClick={() => askQuestion(suggestion)}
                    disabled={loading}
                  >
                    <Search size={15} />
                    <span>{suggestion}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="research-messages">
              {messages.map((message) => (
                <article
                  className={`research-message ${message.role}`}
                  key={message.id}
                >
                  <div className="research-avatar">
                    {message.role === "assistant" ? (
                      <Scale size={17} />
                    ) : (
                      "You"
                    )}
                  </div>

                  <div className="research-message-body">
                    <span className="research-message-label">
                      {message.role === "assistant"
                        ? "DraftMate Research"
                        : "Your question"}
                    </span>

                    <div className="research-answer-text">
                      {message.content}
                    </div>

                    {message.role === "assistant" && (
                      <>
                        {message.citations?.length > 0 && (
                          <div className="research-citations">
                            <h4>
                              <BookOpen size={15} />
                              Sources
                            </h4>
                            {message.citations.map((citation) => (
                              <a
                                key={citation.url}
                                href={citation.url}
                                target="_blank"
                                rel="noreferrer"
                                className="research-source"
                              >
                                <span>{citation.title}</span>
                                <ExternalLink size={13} />
                              </a>
                            ))}
                          </div>
                        )}

                        <button
                          className="research-copy-btn"
                          onClick={() => copyAnswer(message.content)}
                        >
                          <Copy size={14} />
                          Copy answer
                        </button>
                      </>
                    )}
                  </div>
                </article>
              ))}

              {loading && (
                <div className="research-loading">
                  <LoaderCircle size={18} className="research-spin" />
                  <span>Researching your question and checking sources...</span>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}

          {error && <div className="research-error">{error}</div>}
        </div>

        <form
          className="research-composer"
          onSubmit={(event) => {
            event.preventDefault();
            askQuestion();
          }}
        >
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                askQuestion();
              }
            }}
            placeholder="Ask anything about law, rights, legal procedures..."
            rows={3}
            maxLength={5000}
            disabled={loading}
          />

          <div className="research-composer-footer">
            <span>Enter to send · Shift + Enter for a new line</span>
            <button
              type="submit"
              className="research-send-btn"
              disabled={!question.trim() || loading}
            >
              {loading ? (
                <LoaderCircle size={16} className="research-spin" />
              ) : (
                <Send size={16} />
              )}
              {loading ? "Researching..." : "Ask Research"}
            </button>
          </div>
        </form>

        <p className="research-disclaimer">
          AI-generated legal information may be incomplete or inaccurate.
          Verify important claims against the cited sources and consult a
          qualified lawyer for advice about your specific situation.
        </p>
      </section>
    </main>
  );
}

export default Research;
