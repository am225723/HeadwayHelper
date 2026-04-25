"use client";

import { FormEvent, useState } from "react";
import { LockKeyhole } from "lucide-react";
import { API_BASE } from "@/lib/api";

export function LoginPanel({ onToken }: { onToken: (token: string) => void }) {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if (!response.ok) {
      setError("Unable to sign in. Registration is admin-controlled.");
      return;
    }
    const data = await response.json();
    localStorage.setItem("clinical-ai-token", data.access_token);
    onToken(data.access_token);
  }

  return (
    <form onSubmit={submit} className="grid gap-3 border-b border-line bg-white/75 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <LockKeyhole size={16} />
        Clinical workspace sign in
      </div>
      <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
        <input className="focus-ring rounded-md border border-line bg-white px-3 py-2" value={email} onChange={(event) => setEmail(event.target.value)} />
        <input className="focus-ring rounded-md border border-line bg-white px-3 py-2" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        <button className="focus-ring rounded-md bg-ink px-4 py-2 font-semibold text-white">Sign in</button>
      </div>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
    </form>
  );
}
