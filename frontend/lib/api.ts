const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Source {
  title: string;
  page: number | null;
  source_key: string | null;
  url: string | null;
  similarity: number;
}

export interface Confidence {
  level: "HIGH" | "MEDIUM" | "LOW";
  score: number;
  message: string;
}

export interface Contradiction {
  has_contradiction: boolean;
  explanation: string;
  checked: boolean;
}

export interface ChatMeta {
  sources: Source[];
  query_type: "SINGLE_CHUNK" | "MULTI_HOP" | "OUT_OF_SCOPE";
  chunks_used: number;
  confidence: Confidence;
  contradiction: Contradiction;
  follow_up_questions: string[];
}

export interface ChatResponse extends ChatMeta {
  answer: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function register(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail || `Register error ${res.status}`);
  }
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail || `Login error ${res.status}`);
  }
  return res.json();
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function sendChat(
  question: string,
  history: Message[],
  filterSource?: string,
  token?: string,
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: JSON.stringify({ question, history, filter_source: filterSource || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail || `API error ${res.status}`);
  }
  return res.json();
}

export async function* streamChat(
  question: string,
  history: Message[],
  filterSource?: string,
  token?: string,
): AsyncGenerator<{ type: "token"; text: string } | { type: "metadata"; data: ChatMeta } | { type: "done" }> {
  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: JSON.stringify({ question, history, filter_source: filterSource || null }),
  });
  if (!res.ok) throw new Error(`Stream error ${res.status}`);

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastEvent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        lastEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (lastEvent === "metadata") {
          try { yield { type: "metadata", data: JSON.parse(data) }; } catch {}
          lastEvent = "";
        } else if (lastEvent === "done") {
          yield { type: "done" };
          return;
        } else {
          yield { type: "token", text: data.replace(/\\n/g, "\n") };
        }
      }
    }
  }
  yield { type: "done" };
}

// ── Misc ──────────────────────────────────────────────────────────────────────

export async function getHealth(): Promise<{ status: string; documents_indexed: number; model: string }> {
  const res = await fetch(`${API_URL}/health`);
  return res.json();
}

export async function uploadPDF(file: File): Promise<{ message: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/ingest`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload error ${res.status}`);
  return res.json();
}