"use client";

import React, { useState, useRef } from "react";
import { uploadPDF } from "../lib/api";

export default function FileUpload({ token }: { token: string | null }) {
  const [uploadMsg, setUploadMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadMsg("Uploading...");
    try {
      const data = await uploadPDF(file, token || undefined);
      setUploadMsg(data.message);
      setTimeout(() => setUploadMsg(""), 5000);
    } catch {
      setUploadMsg("Upload failed.");
      setTimeout(() => setUploadMsg(""), 3000);
    }
    e.target.value = "";
  };

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <button onClick={() => fileRef.current?.click()} style={{
        background: "rgba(201,168,76,0.07)", border: "1px solid rgba(201,168,76,0.2)",
        color: "var(--gold-light)", fontSize: 11, padding: "5px 12px", borderRadius: 4,
        cursor: "pointer", fontFamily: "'JetBrains Mono',monospace", letterSpacing: 1,
      }}>+ UPLOAD PDF</button>
      
      <input 
        ref={fileRef} 
        type="file" 
        accept=".pdf" 
        style={{ display: "none" }} 
        onChange={handleUpload} 
      />
      
      {uploadMsg && (
        <div style={{ fontSize: 10, color: "var(--gold)", fontFamily: "'JetBrains Mono',monospace", marginLeft: 8 }}>
          {uploadMsg}
        </div>
      )}
    </div>
  );
}
