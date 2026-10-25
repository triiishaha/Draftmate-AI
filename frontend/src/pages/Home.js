
import React from "react";
import Navbar from "../components/Navbar";
import "./Home.css";

const features = [
  {
    id: "drafting",
    icon: "✍️",
    title: "AI Legal Drafting",
    text: "Create first drafts of notices, agreements and contracts from your requirements.",
    tag: "Draft Mode",
  },
  {
    id: "understand",
    icon: "📖",
    title: "Understand Documents",
    text: "Break down complicated legal language into simpler explanations.",
    tag: "Understand Mode",
  },
  {
    id: "citations",
    icon: "🔎",
    title: "Citation Verification",
    text: "Review legal references against available sources and flag details to verify.",
    tag: "Research",
  },
  {
    id: "risk",
    icon: "🛡️",
    title: "Contract Risk Review",
    text: "Identify unclear clauses, obligations and terms that may need closer attention.",
    tag: "Review",
  },
  {
    id: "clauses",
    icon: "⚖️",
    title: "Clause Analysis",
    text: "Understand individual clauses, conditions and responsibilities.",
    tag: "Analysis",
  },
  {
    id: "compare",
    icon: "↔️",
    title: "Compare Documents",
    text: "Compare document versions to see what has changed.",
    tag: "Comparison",
  },
  {
    id: "questions",
    icon: "💬",
    title: "Ask Your Document",
    text: "Ask questions about a document and locate relevant information.",
    tag: "Document Q&A",
  },
  {
    id: "translation",
    icon: "🌐",
    title: "Plain-Language Explanations",
    text: "Make legal terminology easier to understand using simpler language.",
    tag: "Simplify",
  },
  {
    id: "deadlines",
    icon: "📅",
    title: "Deadline Tracker",
    text: "Identify important dates, deadlines and responsibilities in documents.",
    tag: "Organisation",
  },
  {
    id: "templates",
    icon: "🗂️",
    title: "Templates & Export",
    text: "Start with structured templates and prepare documents for further editing.",
    tag: "Workspace",
  },
  {
    id: "voice",
    icon: "🎙️",
    title: "Voice-Assisted Drafting",
    text: "Explore a voice-first way to describe your requirements for a draft.",
    tag: "Planned",
  },
  {
    id: "research",
    icon: "📚",
    title: "Legal Research Assistant",
    text: "Organise legal research and identify relevant sources to check.",
    tag: "Research",
  },
];

const steps = [
  {
    number: "01",
    title: "Choose your task",
    text: "Start with a document you want to create or understand.",
  },
  {
    number: "02",
    title: "Add your information",
    text: "Describe what you need or provide a document to review.",
  },
  {
    number: "03",
    title: "Review the result",
    text: "Check the draft or explanation and make your own edits.",
  },
];

function Home() {
  return (
    <div className="home-page">
      <Navbar />

      <main>
        <section className="hero section-wrap" id="home">
          <div className="hero-copy">
            <div className="eyebrow">
              <span>✳</span> LEGAL WORK, MADE CLEARER
            </div>

            <h1>
              Legal documents,
              <br />
              <em>without the</em>
              <br />
              unnecessary complexity.
            </h1>

            <p className="hero-description">
              DraftMate AI helps you create legal document drafts and
              understand complicated legal language. Less confusion,
              more clarity — all in one place.
            </p>

            <div className="hero-actions">
              <a className="button button-dark" href="#workspace">
                Explore DraftMate <span>↗</span>
              </a>
              <a className="button button-light" href="#how-it-works">
                See how it works <span>↓</span>
              </a>
            </div>

            <p className="hero-note">
              <span>✓</span> No account needed to explore this homepage
            </p>
          </div>

          <div className="hero-visual">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />

            <div className="floating-label label-top">
              <span>✦</span> Built for clarity
            </div>

            <div className="document-card">
              <div className="document-top">
                <span className="document-brand">
                  <b>d.</b> DRAFTMATE AI
                </span>
                <span className="document-status">SAMPLE DOCUMENT</span>
              </div>

              <div className="document-content">
                <span className="document-kicker">AGREEMENT · PREVIEW</span>
                <h3>Understanding the fine print.</h3>
                <p>
                  A clearer view of the terms, conditions and
                  responsibilities that matter.
                </p>

                <div className="document-line" />
                <div className="document-line medium" />
                <div className="document-line short" />

                <div className="highlighted-clause">
                  <strong>✳ In simple words</strong>
                  <p>
                    This section explains what each party is expected
                    to do and which conditions apply.
                  </p>
                </div>

                <div className="document-line" />
                <div className="document-line medium" />

                <div className="document-footer">
                  <span>MADE FOR BETTER UNDERSTANDING</span>
                  <span>01 / 04</span>
                </div>
              </div>
            </div>

            <div className="floating-label label-bottom">
              <span className="status-dot" />
              Clarity over complexity
            </div>

            <span className="decorative-star">✳</span>
          </div>
        </section>

        <section className="value-strip">
          <div className="value-strip-inner">
            <span className="strip-heading">MADE FOR EVERYDAY LEGAL WORK</span>
            <span>✳ Draft with guidance</span>
            <span>↗ Understand the details</span>
            <span>✓ Review with care</span>
          </div>
        </section>

        <section className="modes-section section-wrap" id="workspace">
          <div className="section-heading">
            <div className="eyebrow">YOUR WORKSPACE, YOUR WAY</div>
            <h2>Two ways to get to <em>clarity.</em></h2>
            <p>
              Whether you're starting from a blank page or trying to
              understand an existing document, start with what you need.
            </p>
          </div>

          <div className="modes-grid">
            <article className="mode-card draft-mode">
              <div className="mode-top">
                <span className="mode-icon">✍️</span>
                <span className="mode-number">MODE 01</span>
              </div>
              <div className="mode-label">CREATE SOMETHING NEW</div>
              <h3>Draft Mode</h3>
              <p>
                Start with an idea, a situation or a set of requirements.
                Build a structured first draft you can review and edit.
              </p>
              <ul>
                <li>✓ Legal notice and letter drafts</li>
                <li>✓ Agreement and contract drafts</li>
                <li>✓ Structured writing assistance</li>
              </ul>
              <a className="text-link" href="#drafting">
                Explore drafting ↗
              </a>
              <span className="mode-decoration">Aa</span>
            </article>

            <article className="mode-card understand-mode">
              <div className="mode-top">
                <span className="mode-icon">⌕</span>
                <span className="mode-number">MODE 02</span>
              </div>
              <div className="mode-label">MAKE SENSE OF THE DETAILS</div>
              <h3>Understand Mode</h3>
              <p>
                Explore a legal document in plain language. Find key terms,
                obligations and sections that may need closer attention.
              </p>
              <ul>
                <li>✓ Simple clause explanations</li>
                <li>✓ Questions about your document</li>
                <li>✓ Key terms and deadline identification</li>
              </ul>
              <a className="text-link" href="#understand">
                Explore understanding ↗
              </a>
              <span className="mode-decoration">§</span>
            </article>
          </div>
        </section>

        <section className="features-section" id="features">
          <div className="section-wrap">
            <div className="features-heading">
              <div className="eyebrow">WHAT YOU CAN EXPLORE</div>
              <h2>Useful tools. <em>Less guesswork.</em></h2>
              <p>
                A growing set of tools designed to make legal drafting,
                reading and reviewing feel more manageable.
              </p>
            </div>

            <div className="features-grid">
              {features.map((feature, index) => (
                <article
                  className="feature-card"
                  id={feature.id}
                  key={feature.id}
                >
                  <div className="feature-top">
                    <span className="feature-icon">{feature.icon}</span>
                    <span className="feature-number">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                  </div>
                  <h3>{feature.title}</h3>
                  <p>{feature.text}</p>
                  <div className="feature-bottom">
                    <span className="feature-tag">{feature.tag}</span>
                    <span className="feature-arrow">↗</span>
                  </div>
                </article>
              ))}
            </div>

            <p className="features-note">
              Some tools are planned for future versions and may not be
              available yet.
            </p>
          </div>
        </section>

        <section className="workflow-section section-wrap" id="how-it-works">
          <div className="workflow-intro">
            <div className="eyebrow">A SIMPLE PLACE TO START</div>
            <h2>From confusion to a <em>clearer next step.</em></h2>
            <p>
              The idea is simple: make legal documents easier to work with
              without pretending every situation has an easy answer.
            </p>
            <a className="button button-dark" href="#workspace">
              Explore the idea ↗
            </a>
          </div>

          <div className="workflow-steps">
            {steps.map((step) => (
              <article className="workflow-step" key={step.number}>
                <span className="step-number">{step.number}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
                <span className="step-arrow">↗</span>
              </article>
            ))}
          </div>
        </section>

        <section className="principles-section" id="about">
          <div className="section-wrap principles-layout">
            <div className="principles-heading">
              <div className="eyebrow">OUR APPROACH</div>
              <h2>Helpful AI.<br /><em>Human judgement.</em></h2>
            </div>

            <div className="principles-content">
              <p className="principles-lead">
                Legal work needs more than words that sound convincing.
                It needs care, context and a habit of checking details.
              </p>

              <article className="principle-item">
                <span>01</span>
                <div>
                  <h3>Clarity comes first</h3>
                  <p>
                    Explanations should help people understand, not
                    overwhelm them with jargon.
                  </p>
                </div>
              </article>

              <article className="principle-item">
                <span>02</span>
                <div>
                  <h3>Check important details</h3>
                  <p>
                    Facts, legal references and document terms should be
                    verified rather than blindly trusted.
                  </p>
                </div>
              </article>

              <article className="principle-item">
                <span>03</span>
                <div>
                  <h3>AI is an assistant, not a lawyer</h3>
                  <p>
                    AI-generated drafts and explanations need careful
                    review, especially when the stakes are high.
                  </p>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="closing-section section-wrap">
          <div className="closing-card">
            <span className="closing-decoration">d.</span>
            <div className="eyebrow">START WITH CLARITY</div>
            <h2>
              Legal language can be complex.
              <br />
              <em>Getting started doesn't have to be.</em>
            </h2>
            <p>
              Explore a more approachable way to work with legal documents.
            </p>
            <a className="button button-cream" href="#home">
              Back to the beginning ↑
            </a>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="section-wrap footer-main">
          <div className="footer-brand">
            <a className="brand" href="#home">
              <span className="brand-mark">d.</span>
              <span className="brand-name">
                DraftMate<span>AI</span>
              </span>
            </a>
            <p>
              Making legal documents easier to draft, read and understand.
            </p>
          </div>

          <div className="footer-links">
            <strong>EXPLORE</strong>
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#about">Our approach</a>
          </div>

          <div className="footer-links">
            <strong>THE WORKSPACE</strong>
            <a href="#drafting">Draft Mode</a>
            <a href="#understand">Understand Mode</a>
            <a href="#workspace">Workspace</a>
          </div>
        </div>

        <div className="section-wrap footer-bottom">
          <span>© 2026 DraftMate AI. A work in progress.</span>
          <span>
            AI assistance does not replace advice from a qualified legal professional.
          </span>
        </div>
      </footer>
    </div>
  );
}

export default Home;
