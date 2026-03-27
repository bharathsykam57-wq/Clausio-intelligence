"use client";

import React, { useState, useRef, useEffect } from "react";
import { streamChat, Message } from "../lib/api";
import MessageBubble, { ChatMessage } from "./MessageBubble";

const SUGGESTED = [
  "What obligations do providers of high-risk AI systems have?",
  "Which AI applications are prohibited under the EU AI Act?",
  "What are the rights of data subjects under GDPR?",
  "Compare GDPR consent requirements with EU AI Act obligations",
];

export default function ChatWindow({ 
  token, 
  filter 
}: { 
  token: string;
  filter: string;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

  return (
    <>
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
    </>
  );
}
