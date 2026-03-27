"use client";

import React from "react";
import DOMPurify from "isomorphic-dompurify";
import { marked } from "marked";
import { ChatMeta } from "../lib/api";
import QueryTypeBadge from "./QueryTypeBadge";
import ContradictionAlert from "./ContradictionAlert";
import ConfidenceBadge from "./ConfidenceBadge";
import SourceCard from "./SourceCard";
import FollowUpSuggestions from "./FollowUpSuggestions";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: ChatMeta;
  isStreaming?: boolean;
}

export function ThinkingDots() {
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

export default function MessageBubble({ msg, onFollowUp }: { msg: ChatMessage; onFollowUp: (q: string) => void }) {
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
            __html: DOMPurify.sanitize(marked.parse(msg.content) as string)
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
