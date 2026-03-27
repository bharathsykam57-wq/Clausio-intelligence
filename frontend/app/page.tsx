"use client";

import { useState, useEffect } from "react";
import { getHealth } from "../lib/api";
import AuthForm from "../components/AuthForm";
import ChatWindow from "../components/ChatWindow";
import FileUpload from "../components/FileUpload";

export default function Home() {
  const [token, setTokenState] = useState<string | null>(null);
  const [docsCount, setDocsCount] = useState<number | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    const savedToken = localStorage.getItem("clausio_token");
    if (savedToken) setTokenState(savedToken);
  }, []);

  const setToken = (t: string | null) => {
    if (t) localStorage.setItem("clausio_token", t);
    else localStorage.removeItem("clausio_token");
    setTokenState(t);
  };

  useEffect(() => {
    getHealth().then(d => setDocsCount(d.documents_indexed)).catch(() => {});
  }, []);

  if (!token) {
    return <AuthForm onAuth={(t) => setToken(t)} />;
  }

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
              <FileUpload token={token} />
              <button onClick={() => setToken(null)} style={{
                background: "transparent", border: "1px solid rgba(255,255,255,0.08)",
                color: "rgba(255,255,255,0.3)", fontSize: 11, padding: "5px 12px", borderRadius: 4,
                cursor: "pointer", fontFamily: "'JetBrains Mono',monospace", letterSpacing: 1,
              }}>SIGN OUT</button>
            </div>
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

      <ChatWindow token={token} filter={filter} />
    </div>
  );
}
