"use client";

import { useState } from "react";
import { login, register } from "../lib/api";

export default function AuthForm({
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
