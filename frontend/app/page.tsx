"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { streamChat, login, register, Source, ChatMeta, Message } from "../lib/api";
import ConfidenceBadge from "../components/ConfidenceBadge";
import ContradictionAlert from "../components/ContradictionAlert";
import FollowUpSuggestions from "../components/FollowUpSuggestions";
import SourceCard from "../components/SourceCard";
import QueryTypeBadge from "../components/QueryTypeBadge";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SUGGESTED = [
  "What obligations do providers of high-risk AI systems have?",
  "Which AI applications are prohibited under the EU AI Act?",
  "What are the rights of data subjects under GDPR?",
  "Compare GDPR consent requirements with EU AI Act obligations",
];

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: ChatMeta;
  isStreaming?: boolean;
}

function ThinkingDots() {
  return (
    <div style={{ display: "flex", gap: 5, padding: "4px 0", alignItems: "center" }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 7, height: 7, borderRadius: "50%", background: "var(--gold)",
          animation: `pulse-gold 1.4s ease ${i * 0.2}s infinite`,
        }} />
      ))}
    </div>
  );
}

// ── Auth Form ─────────────────────────────────────────────────────────────────

function AuthForm({
  onAuth,
}: {
  onAuth: (token: string) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!email || !password) return;
    setLoading(true);
    setError("");
    try {
      const res = mode === "login"
        ? await login(email, password)
        : await register(email, password);
      onAuth(res.access_token);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    }
    setLoading(false);
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{
        width: "100%", maxWidth: 400, padding: "40px 36px",
        background: "rgba(255,255,255,0.02)", border: "1px solid rgba(201,168,76,0.2)",
        borderRadius: 12,
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 10, letterSpacing: 5, color: "rgba(201,168,76,0.6)", fontFamily: "'JetBrains Mono',monospace", marginBottom: 8 }}>
            EU LEGAL INTELLIGENCE
          </div>
          <h1 style={{ fontFamily: "'Playfair Display',Georgia,serif", fontSize: 36, fontWeight: 400, color: "var(--parchment)", lineHeight: 1 }}>
            Lex<span style={{ color: "var(--gold)", fontStyle: "italic" }}>IA</span>
          </h1>
          <p style={{ fontSize: 12, color: "rgba(245,240,232,0.3)", marginTop: 6 }}>EU AI Act · GDPR/RGPD</p>
        </div>

        {/* Mode toggle */}
        <div style={{ display: "flex", marginBottom: 24, background: "rgba(255,255,255,0.03)", borderRadius: 6, padding: 3 }}>
          {(["login", "register"] as const).map(m => (
            <button key={m} onClick={() => { setMode(m); setError(""); }} style={{
              flex: 1, padding: "7px 0", borderRadius: 4, border: "none", cursor: "pointer",
              fontSize: 11, letterSpacing: 2, fontFamily: "'JetBrains Mono',monospace",
              background: mode === m ? "rgba(201,168,76,0.15)" : "transparent",
              color: mode === m ? "var(--gold-light)" : "rgba(255,255,255,0.3)",
              transition: "all 0.15s",
            }}>
              {m.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Inputs */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSubmit()}
            style={{
              background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 6, padding: "11px 14px", color: "var(--parchment)", fontSize: 14,
              fontFamily: "'DM Sans',sans-serif", outline: "none",
            }}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSubmit()}
            style={{
              background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 6, padding: "11px 14px", color: "var(--parchment)", fontSize: 14,
              fontFamily: "'DM Sans',sans-serif", outline: "none",
            }}
          />
        </div>

        {/* Error */}
        {error && (
          <div style={{ fontSize: 12, color: "#e07070", marginBottom: 14, fontFamily: "'JetBrains Mono',monospace" }}>
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={loading || !email || !password}
          style={{
            width: "100%", padding: "12px 0", borderRadius: 6, border: "none",
            background: loading || !email || !password ? "rgba(201,168,76,0.1)" : "rgba(201,168,76,0.85)",
            color: loading || !email || !password ? "rgba(201,168,76,0.3)" : "var(--ink)",
            fontSize: 12, letterSpacing: 2, fontFamily: "'JetBrains Mono',monospace",
            cursor: loading || !email || !password ? "not-allowed" : "pointer",
            transition: "all 0.2s",
          }}
        >
          {loading ? "..." : mode === "login" ? "SIGN IN" : "CREATE ACCOUNT"}
        </button>
      </div>
    </div>
  );
}

// ── Message Bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg, onFollowUp }: { msg: ChatMessage; onFollowUp: (q: string) => void }) {
  const isUser = msg.role === "user";
  return (
    <div className="animate-fade-up" style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start", marginBottom: 28 }}>

      {/* Role + query type */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 10, letterSpacing: 3, color: isUser ? "rgba(201,168,76,0.5)" : "rgba(245,240,232,0.25)", fontFamily: "'JetBrains Mono', monospace" }}>
          {isUser ? "YOU" : "LEXIA"}
        </span>
        {!isUser && msg.meta?.query_type && <QueryTypeBadge queryType={msg.meta.query_type} />}
      </div>

      {/* Contradiction alert */}
      {!isUser && msg.meta?.contradiction && (
        <div style={{ maxWidth: "80%", width: "100%" }}>
          <ContradictionAlert contradiction={msg.meta.contradiction} />
        </div>
      )}

      {/* Bubble */}
      <div style={{
        maxWidth: "80%",
        background: isUser ? "linear-gradient(135deg, rgba(201,168,76,0.12), rgba(201,168,76,0.06))" : "rgba(255,255,255,0.03)",
        border: isUser ? "1px solid rgba(201,168,76,0.3)" : "1px solid rgba(255,255,255,0.07)",
        borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
        padding: "13px 17px",
      }}>
        {msg.isStreaming && !msg.content ? (
          <ThinkingDots />
        ) : (
          <div className="answer-prose" dangerouslySetInnerHTML={{
            __html: msg.content
              .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
              .replace(/`([^`]+)`/g, "<code>$1</code>")
              .replace(/\n/g, "<br/>"),
          }} />
        )}
      </div>

      {/* Metadata */}
      {!isUser && msg.meta && !msg.isStreaming && (
        <div style={{ maxWidth: "80%", marginTop: 8 }}>
          <ConfidenceBadge confidence={msg.meta.confidence} />
          {msg.meta.sources && msg.meta.sources.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 9, letterSpacing: 3, color: "rgba(201,168,76,0.4)", marginBottom: 4, fontFamily: "'JetBrains Mono', monospace" }}>
                SOURCES RETRIEVED
              </div>
              <div style={{ display: "flex", flexWrap: "wrap" }}>
                {msg.meta.sources.map((s, i) => <SourceCard key={i} source={s} />)}
              </div>
            </div>
          )}
          <FollowUpSuggestions questions={msg.meta.follow_up_questions} onSelect={onFollowUp} />
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [docsCount, setDocsCount] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [uploadMsg, setUploadMsg] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API_URL}/health`).then(r => r.json()).then(d => setDocsCount(d.documents_indexed)).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Show auth form when not logged in ──
  if (!token) {
    return <AuthForm onAuth={(t) => setToken(t)} />;
  }

  const getHistory = (): Message[] =>
    messages.filter(m => !m.isStreaming).map(m => ({ role: m.role, content: m.content })).slice(-8);

  const send = async (text?: string) => {
    const q = (text || input).trim();
    if (!q || loading) return;
    setInput("");
    setLoading(true);

    const userMsg: ChatMessage = { id: Date.now().toString(), role: "user", content: q };
    const assistantId = (Date.now() + 1).toString();
    const assistantMsg: ChatMessage = { id: assistantId, role: "assistant", content: "", isStreaming: true };
    setMessages(prev => [...prev, userMsg, assistantMsg]);

    try {
      let fullText = "";
      for await (const event of streamChat(q, getHistory(), filter || undefined, token)) {
        if (event.type === "token") {
          fullText += event.text;
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: fullText } : m));
        } else if (event.type === "metadata") {
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, meta: event.data, isStreaming: false } : m));
        } else if (event.type === "done") {
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, isStreaming: false } : m));
          break;
        }
      }
    } catch {
      setMessages(prev => prev.map(m => m.id === assistantId ? {
        ...m, content: "Backend unavailable. Start the backend with `docker-compose up`.", isStreaming: false,
      } : m));
    }

    setLoading(false);
    inputRef.current?.focus();
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadMsg("Uploading...");
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API_URL}/ingest`, { method: "POST", body: form });
      const data = await res.json() as { message: string };
      setUploadMsg(data.message);
      setTimeout(() => setUploadMsg(""), 5000);
    } catch {
      setUploadMsg("Upload failed.");
      setTimeout(() => setUploadMsg(""), 3000);
    }
    e.target.value = "";
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", maxWidth: 840, margin: "0 auto", padding: "0 24px" }}>

      {/* Header */}
      <header style={{ padding: "28px 0 16px", borderBottom: "1px solid rgba(201,168,76,0.15)" }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, letterSpacing: 5, color: "rgba(201,168,76,0.6)", fontFamily: "'JetBrains Mono',monospace", marginBottom: 6 }}>
              RAG · HYDE · QUERY ROUTING · EVAL-DRIVEN
            </div>
            <h1 style={{ fontFamily: "'Playfair Display',Georgia,serif", fontSize: 34, fontWeight: 400, letterSpacing: 1, color: "var(--parchment)", lineHeight: 1 }}>
              Lex<span style={{ color: "var(--gold)", fontStyle: "italic" }}>IA</span>
              <span style={{ fontSize: 13, fontFamily: "'JetBrains Mono',monospace", color: "rgba(255,255,255,0.2)", marginLeft: 10, fontStyle: "normal", verticalAlign: "middle" }}>v2</span>
            </h1>
            <p style={{ fontSize: 12, color: "rgba(245,240,232,0.35)", marginTop: 5, fontWeight: 300 }}>EU AI Act · GDPR/RGPD · Legal Intelligence</p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <div style={{ fontSize: 11, fontFamily: "'JetBrains Mono',monospace", color: "rgba(201,168,76,0.6)", display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: docsCount ? "var(--gold)" : "#555" }} />
              {docsCount !== null ? `${docsCount.toLocaleString()} chunks indexed` : "Connecting..."}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => fileRef.current?.click()} style={{
                background: "rgba(201,168,76,0.07)", border: "1px solid rgba(201,168,76,0.2)",
                color: "var(--gold-light)", fontSize: 11, padding: "5px 12px", borderRadius: 4,
                cursor: "pointer", fontFamily: "'JetBrains Mono',monospace", letterSpacing: 1,
              }}>+ UPLOAD PDF</button>
              <button onClick={() => setToken(null)} style={{
                background: "transparent", border: "1px solid rgba(255,255,255,0.08)",
                color: "rgba(255,255,255,0.3)", fontSize: 11, padding: "5px 12px", borderRadius: 4,
                cursor: "pointer", fontFamily: "'JetBrains Mono',monospace", letterSpacing: 1,
              }}>SIGN OUT</button>
            </div>
            <input ref={fileRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={handleUpload} />
            {uploadMsg && <div style={{ fontSize: 10, color: "var(--gold)", fontFamily: "'JetBrains Mono',monospace" }}>{uploadMsg}</div>}
          </div>
        </div>

        {/* Filter tabs */}
        <div style={{ marginTop: 14, display: "flex", gap: 6 }}>
          {[{ key: "", label: "All" }, { key: "eu_ai_act", label: "EU AI Act" }, { key: "rgpd_fr", label: "RGPD" }].map(opt => (
            <button key={opt.key} onClick={() => setFilter(opt.key)} style={{
              fontSize: 10, letterSpacing: 2, padding: "4px 12px", borderRadius: 3, cursor: "pointer",
              border: `1px solid ${filter === opt.key ? "rgba(201,168,76,0.5)" : "rgba(255,255,255,0.08)"}`,
              background: filter === opt.key ? "rgba(201,168,76,0.1)" : "transparent",
              color: filter === opt.key ? "var(--gold-light)" : "rgba(255,255,255,0.35)",
              fontFamily: "'JetBrains Mono',monospace", transition: "all 0.15s",
            }}>{opt.label}</button>
          ))}
        </div>
      </header>

      {/* Messages */}
      <main style={{ flex: 1, overflowY: "auto", padding: "28px 0 12px" }}>
        {messages.length === 0 && (
          <div>
            <p style={{ fontFamily: "'Playfair Display',Georgia,serif", fontSize: 17, fontStyle: "italic", color: "rgba(245,240,232,0.28)", marginBottom: 28, lineHeight: 1.7 }}>
              "An AI system that provides advice in a professional capacity is classified as high-risk under Annex III."
              <br /><span style={{ fontSize: 11, fontStyle: "normal", opacity: 0.5 }}>— EU Artificial Intelligence Act</span>
            </p>
            <div style={{ fontSize: 10, letterSpacing: 3, color: "rgba(201,168,76,0.4)", marginBottom: 10, fontFamily: "'JetBrains Mono',monospace" }}>SUGGESTED</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {SUGGESTED.map((q, i) => (
                <button key={i} onClick={() => send(q)} style={{
                  textAlign: "left", background: "rgba(255,255,255,0.02)", borderRadius: "0 6px 6px 0",
                  border: "1px solid rgba(255,255,255,0.06)", borderLeft: "2px solid rgba(201,168,76,0.25)",
                  padding: "9px 14px", color: "rgba(245,240,232,0.55)", fontSize: 13, cursor: "pointer",
                  fontFamily: "'DM Sans',sans-serif", transition: "all 0.15s",
                }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderLeftColor = "var(--gold)"; (e.currentTarget as HTMLElement).style.color = "var(--parchment)"; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderLeftColor = "rgba(201,168,76,0.25)"; (e.currentTarget as HTMLElement).style.color = "rgba(245,240,232,0.55)"; }}
                >{q}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} onFollowUp={send} />)}
        <div ref={bottomRef} />
      </main>

      {/* Input */}
      <footer style={{ borderTop: "1px solid rgba(201,168,76,0.12)", padding: "14px 0 22px" }}>
        <div style={{
          display: "flex", gap: 10, alignItems: "flex-end",
          background: "rgba(255,255,255,0.025)", border: "1px solid rgba(201,168,76,0.18)",
          borderRadius: 8, padding: "10px 14px",
        }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="Ask about the EU AI Act, GDPR obligations, prohibited AI practices…"
            rows={1}
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              color: "var(--parchment)", fontSize: 14, fontFamily: "'DM Sans',sans-serif",
              fontWeight: 300, resize: "none", lineHeight: 1.6,
            }}
          />
          <button onClick={() => send()} disabled={loading || !input.trim()} style={{
            width: 38, height: 38, borderRadius: 6, border: "none", flexShrink: 0,
            background: loading || !input.trim() ? "rgba(201,168,76,0.08)" : "rgba(201,168,76,0.85)",
            color: loading || !input.trim() ? "rgba(201,168,76,0.3)" : "var(--ink)",
            cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16, fontWeight: 600, transition: "all 0.2s",
          }}>
            {loading
              ? <div style={{ width: 14, height: 14, borderRadius: "50%", border: "2px solid rgba(201,168,76,0.3)", borderTopColor: "var(--gold)" }} className="animate-spin" />
              : "↑"}
          </button>
        </div>
        <div style={{ textAlign: "center", marginTop: 8, fontSize: 10, color: "rgba(255,255,255,0.15)", fontFamily: "'JetBrains Mono',monospace", letterSpacing: 1 }}>
          MISTRAL · PGVECTOR · HYDE · QUERY ROUTING · RAGAS EVAL
        </div>
      </footer>
    </div>
  );
}
