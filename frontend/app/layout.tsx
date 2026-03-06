// Layout Component for the Next.js application
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LexIA — EU Legal AI Assistant",
  description: "RAG-powered assistant for EU AI Act & GDPR/RGPD compliance",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
