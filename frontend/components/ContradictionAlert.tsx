"use client";
import { Contradiction } from "../lib/api";

export default function ContradictionAlert({ contradiction }: { contradiction: Contradiction }) {
  if (!contradiction.has_contradiction) return null;
  return (
    <div style={{
      background: "rgba(251,191,36,0.07)", border: "1px solid rgba(251,191,36,0.25)",
      borderLeft: "3px solid #fbbf24", borderRadius: "0 8px 8px 0",
      padding: "10px 14px", marginBottom: 10, display: "flex", gap: 10, alignItems: "flex-start",
    }}>
      <span style={{ fontSize: 16, flexShrink: 0 }}>⚠️</span>
      <div>
        <div style={{ fontSize: 10, letterSpacing: 2, color: "#fbbf24", marginBottom: 3, fontFamily: "'JetBrains Mono', monospace" }}>
          CONFLICTING SOURCES DETECTED
        </div>
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.6)", lineHeight: 1.5 }}>
          {contradiction.explanation || "Retrieved sources contain conflicting information. Verify with original documents."}
        </div>
      </div>
    </div>
  );
}
