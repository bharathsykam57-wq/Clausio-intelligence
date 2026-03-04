"use client";

interface Props {
  questions: string[];
  onSelect: (q: string) => void;
}

export default function FollowUpSuggestions({ questions, onSelect }: Props) {
  if (!questions || questions.length === 0) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 9, letterSpacing: 3, color: "rgba(201,168,76,0.4)", marginBottom: 6, fontFamily: "'JetBrains Mono', monospace" }}>
        FOLLOW-UP QUESTIONS
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {questions.map((q, i) => (
          <button
            key={i}
            onClick={() => onSelect(q)}
            style={{
              textAlign: "left", background: "rgba(201,168,76,0.04)",
              border: "1px solid rgba(201,168,76,0.12)", borderLeft: "2px solid rgba(201,168,76,0.3)",
              padding: "7px 12px", color: "rgba(245,240,232,0.55)", fontSize: 12,
              cursor: "pointer", borderRadius: "0 6px 6px 0",
              fontFamily: "'DM Sans', sans-serif", transition: "all 0.15s",
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.borderLeftColor = "#c9a84c";
              (e.currentTarget as HTMLElement).style.color = "rgba(245,240,232,0.9)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.borderLeftColor = "rgba(201,168,76,0.3)";
              (e.currentTarget as HTMLElement).style.color = "rgba(245,240,232,0.55)";
            }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
