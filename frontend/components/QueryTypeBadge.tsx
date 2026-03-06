// QueryTypeBadge Component
"use client";

const CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  SINGLE_CHUNK: { label: "SINGLE CHUNK",  color: "#60a5fa", bg: "rgba(59,130,246,0.1)" },
  MULTI_HOP:    { label: "MULTI-HOP · HyDE", color: "#c084fc", bg: "rgba(168,85,247,0.1)" },
  OUT_OF_SCOPE: { label: "OUT OF SCOPE",  color: "#f87171", bg: "rgba(248,113,113,0.1)" },
};

export default function QueryTypeBadge({ queryType }: { queryType: string }) {
  const cfg = CONFIG[queryType] || CONFIG.SINGLE_CHUNK;
  return (
    <span style={{
      fontSize: 9, letterSpacing: 2, padding: "2px 8px", borderRadius: 4,
      background: cfg.bg, color: cfg.color, fontFamily: "'JetBrains Mono', monospace",
      border: `1px solid ${cfg.color}44`,
    }}>
      {cfg.label}
    </span>
  );
}
