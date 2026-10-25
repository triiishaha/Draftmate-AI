
import React, { useEffect, useRef, useState } from "react";
import {
  Bot,
  X,
  RotateCcw,
  Mic,
  Send,
  Volume2,
  Square,
  Languages,
  CircleHelp,
} from "lucide-react";
import "./ChatAssistant.css";

const languages = [
  { label: "English (India)", code: "en-IN" },
  { label: "Hindi", code: "hi-IN" },
  { label: "English (US)", code: "en-US" },
  { label: "Bengali", code: "bn-IN" },
  { label: "Tamil", code: "ta-IN" },
  { label: "Telugu", code: "te-IN" },
  { label: "Marathi", code: "mr-IN" },
  { label: "Gujarati", code: "gu-IN" },
  { label: "Spanish", code: "es-ES" },
  { label: "French", code: "fr-FR" },
  { label: "Arabic", code: "ar-SA" },
];

const welcomeMessage = {
  role: "assistant",
  text: "Hi! I'm DraftMate Assistant. You can type or speak to me in your preferred language. Ask me about legal drafting, documents, clauses, or how to use DraftMate.",
};

function ChatAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([welcomeMessage]);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState("en-IN");
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [voiceReplies, setVoiceReplies] = useState(false);
  const [error, setError] = useState("");

  const recognitionRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();

      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  function speakText(text) {
    if (!("speechSynthesis" in window)) {
      setError("Voice playback is not supported in this browser.");
      return;
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language;

    const voices = window.speechSynthesis.getVoices();
    const languagePrefix = language.split("-")[0];

    const matchingVoice =
      voices.find(
        (voice) => voice.lang.toLowerCase() === language.toLowerCase()
      ) ||
      voices.find((voice) =>
        voice.lang.toLowerCase().startsWith(languagePrefix)
      );

    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }

  function startListening() {
    setError("");

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError(
        "Voice input is not supported in this browser. Try a recent version of Chrome."
      );
      return;
    }

    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = language;
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => {
      setListening(true);
      setError("");
    };

    recognition.onresult = (event) => {
      let transcript = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }

      setInput(transcript);
    };

    recognition.onerror = (event) => {
      setListening(false);

      if (event.error === "not-allowed") {
        setError("Please allow microphone access in your browser settings.");
      } else if (event.error !== "no-speech" && event.error !== "aborted") {
        setError("Couldn't recognise your speech. Please try again.");
      }
    };

    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
  }

  async function sendMessage(event) {
    event?.preventDefault();

    const question = input.trim();

    if (!question || loading) return;

    setError("");
    setInput("");

    const updatedMessages = [
      ...messages,
      { role: "user", text: question },
    ];

    setMessages(updatedMessages);
    setLoading(true);

    try {
      const response = await fetch(`${(process.env.REACT_APP_NODE_URL || "http://localhost:5000")}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          language,
          history: messages.slice(-10).map((message) => ({
            role: message.role,
            content: message.text,
          })),
        }),
      });

      if (!response.ok) {
        throw new Error(
          response.status === 404
            ? "The AI backend isn't connected yet. We'll connect it next."
            : "The assistant couldn't respond. Please try again."
        );
      }

      const data = await response.json();
      const answer = data.answer || data.reply;

      if (!answer) {
        throw new Error("The server returned an empty response.");
      }

      setMessages((previous) => [
        ...previous,
        { role: "assistant", text: answer },
      ]);

      if (voiceReplies) {
        speakText(answer);
      }
    } catch (err) {
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          text:
            err.message ||
            "I couldn't connect right now. Please try again shortly.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function clearConversation() {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    recognitionRef.current?.stop();
    setListening(false);
    setSpeaking(false);
    setMessages([welcomeMessage]);
    setError("");
  }

  return (
    <div className="draftmate-assistant">
      {isOpen && (
        <section className="assistant-panel" aria-label="DraftMate chat">
          <header className="assistant-header">
            <div className="assistant-heading">
              <div className="assistant-avatar">
                <Bot size={24} strokeWidth={1.8} />
              </div>

              <div>
                <h2>DraftMate Assistant</h2>
                <p>
                  <span className="assistant-online-dot" />
                  Your legal AI companion
                </p>
              </div>
            </div>

            <div className="assistant-header-actions">
              <button
                type="button"
                onClick={clearConversation}
                title="Clear conversation"
                aria-label="Clear conversation"
              >
                <RotateCcw size={17} />
              </button>

              <button
                type="button"
                onClick={() => {
                  window.speechSynthesis?.cancel();
                  recognitionRef.current?.stop();
                  setSpeaking(false);
                  setListening(false);
                  setIsOpen(false);
                }}
                title="Close assistant"
                aria-label="Close assistant"
              >
                <X size={20} />
              </button>
            </div>
          </header>

          <div className="assistant-language">
            <label htmlFor="assistant-language-select">
              <Languages size={14} /> Conversation language
            </label>

            <select
              id="assistant-language-select"
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
            >
              {languages.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          <div className="assistant-messages" aria-live="polite">
            <div className="assistant-date-label">YOUR CONVERSATION</div>

            {messages.map((message, index) => (
              <div
                className={`assistant-message-row ${
                  message.role === "user" ? "user-row" : "bot-row"
                }`}
                key={`${index}-${message.role}`}
              >
                {message.role === "assistant" && (
                  <span className="message-avatar">
                    <Bot size={17} strokeWidth={1.8} />
                  </span>
                )}

                <div
                  className={`assistant-message ${
                    message.role === "user" ? "user-message" : "bot-message"
                  }`}
                >
                  <p>{message.text}</p>

                  {message.role === "assistant" && index > 0 && (
                    <button
                      type="button"
                      className="message-speak"
                      onClick={() => speakText(message.text)}
                      title="Read this answer aloud"
                    >
                      <Volume2 size={14} /> Listen
                    </button>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="assistant-message-row bot-row">
                <span className="message-avatar">
                  <Bot size={17} strokeWidth={1.8} />
                </span>

                <div className="assistant-message bot-message typing-message">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {error && <div className="assistant-error">{error}</div>}

          <div className="assistant-voice-settings">
            <button
              type="button"
              className={`voice-toggle ${voiceReplies ? "enabled" : ""}`}
              onClick={() => setVoiceReplies(!voiceReplies)}
              aria-pressed={voiceReplies}
            >
              <Volume2 size={14} />
              Voice replies {voiceReplies ? "On" : "Off"}
            </button>

            {speaking && (
              <button
                type="button"
                className="stop-speaking"
                onClick={() => {
                  window.speechSynthesis?.cancel();
                  setSpeaking(false);
                }}
              >
                <Square size={11} /> Stop speaking
              </button>
            )}
          </div>

          <form className="assistant-input-area" onSubmit={sendMessage}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={
                listening
                  ? "Listening... speak now"
                  : "Ask your legal question..."
              }
              rows={2}
              aria-label="Your message"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
            />

            <div className="assistant-input-actions">
              <button
                type="button"
                className={`assistant-mic ${listening ? "listening" : ""}`}
                onClick={startListening}
                title={listening ? "Stop listening" : "Speak your question"}
                aria-label={listening ? "Stop listening" : "Speak your question"}
              >
                {listening ? <Square size={16} /> : <Mic size={18} />}
              </button>

              <button
                type="submit"
                className="assistant-send"
                disabled={!input.trim() || loading}
                aria-label="Send message"
              >
                <Send size={17} />
              </button>
            </div>
          </form>

          <p className="assistant-disclaimer">
            AI can make mistakes. Verify important legal information with a
            qualified legal professional.
          </p>
        </section>
      )}

      <button
        type="button"
        className={`assistant-launcher ${isOpen ? "launcher-open" : ""}`}
        onClick={() => setIsOpen(!isOpen)}
        aria-label={
          isOpen ? "Close DraftMate Assistant" : "Open DraftMate Assistant"
        }
        aria-expanded={isOpen}
      >
        {isOpen ? (
          <X size={25} />
        ) : (
          <>
            <span className="launcher-symbol">
              <Bot size={25} strokeWidth={1.8} />
            </span>

            <span className="launcher-label">Ask DraftMate</span>

            <Mic size={17} className="launcher-mic" />
          </>
        )}
      </button>
    </div>
  );
}

export default ChatAssistant;
