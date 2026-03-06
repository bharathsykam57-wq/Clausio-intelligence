// ConfidenceBadge Component 
"use client";
import { Confidence } from "../lib/api";

const CONFIG = {
  HIGH:   { color: "#34d399", bg: "rgba(52,211,153,0.1)",   border: "rgba(52,211,153,0.3)",   dot: "#34d399", label: "HIGH CONFIDENCE" },
  MEDIUM: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)",   border: "rgba(251,191,36,0.3)",   dot: "#fbbf24", label: "MEDIUM CONFIDENCE" },
  LOW:    { color: "#f87171", bg: "rgba(248,113,113,0.1)",  border: "rgba(248,113,113,0.3)",  dot: "#f87171", label: "LOW CONFIDENCE" },
};

export default function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const cfg = CONFIG[confidence.level] || CONFIG.MEDIUM;
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      borderRadius: 6, padding: "5px 10px", marginTop: 8,
    }}>
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: cfg.dot }} />
      <span style={{ fontSize: 10, letterSpacing: 2, color: cfg.color, fontFamily: "'JetBrains Mono', monospace" }}>
        {cfg.label}
      </span>
      <span style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", fontFamily: "'JetBrains Mono', monospace" }}>
        {(confidence.score * 100).toFixed(0)}%
      </span>
      <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>{confidence.message}</span>
    </div>
  );
}
