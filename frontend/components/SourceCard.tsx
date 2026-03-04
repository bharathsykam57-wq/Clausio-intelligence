"use client";
import { Source } from "../lib/api";

export default function SourceCard({ source }: { source: Source }) {
  const label = source.title.length > 32 ? source.title.slice(0, 30) + "…" : source.title;
  return (
    <a
      href={source.url || "#"}
      target="_blank"
      rel="noopener noreferrer"
      title={`${source.title} — Relevance: ${(source.similarity * 100).toFixed(0)}%`}
      style={{
        display: "inline-flex", alignItems: "center", gap: 4,
        background: "rgba(201,168,76,0.08)", border: "1px solid rgba(201,168,76,0.25)",
        color: "var(--gold-light)", fontSize: 11, padding: "2px 8px",
        borderRadius: 3, margin: "2px 3px", fontFamily: "'JetBrains Mono', monospace",
        textDecoration: "none", transition: "all 0.15s",
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "rgba(201,168,76,0.6)"; }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "rgba(201,168,76,0.25)"; }}
    >
      <span style={{ opacity: 0.5 }}>§</span>
      {label}
      {source.page && <span style={{ opacity: 0.4 }}>p.{source.page}</span>}
    </a>
  );
}
