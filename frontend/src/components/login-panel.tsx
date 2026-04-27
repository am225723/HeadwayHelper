"use client";

import { FormEvent, useState } from "react";
import { LockKeyhole } from "lucide-react";
import { API_BASE } from "@/lib/api";

export function LoginPanel({ onToken }: { onToken: (token: string) => void }) {
  const [email, setEmail] = useState("aleix@drzelisko.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
    } catch {
      setError("Unable to reach the backend. Make sure the FastAPI server is running on port 8000.");
      return;
    }
    if (!response.ok) {
      setError("Unable to sign in. Check credentials or create the admin account through the backend setup flow.");
      return;
    }
    const data = await response.json();
    localStorage.setItem("clinical-ai-token", data.access_token);
    onToken(data.access_token);
  }

  return (
    <form onSubmit={submit} className="mx-auto mt-6 grid max-w-xl gap-4 rounded-2xl border border-line bg-white/95 p-5 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-moss">
            <LockKeyhole size={16} />
            Secure clinical workspace
          </div>
          <p className="mt-1 text-sm text-muted">Sign in with an administrator-provisioned account.</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
        <label className="grid gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
          Email
          <input className="focus-ring rounded-xl border border-line bg-cream px-3 py-2.5 text-sm text-ink placeholder:text-muted/60" value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="grid gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
          Password
          <input className="focus-ring rounded-xl border border-line bg-cream px-3 py-2.5 text-sm text-ink placeholder:text-muted/60" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button className="focus-ring self-end rounded-xl bg-moss px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-moss/90">Sign in</button>
      </div>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
    </form>
  );
}
