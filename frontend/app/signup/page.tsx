"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setMessage(""); setBusy(true);
    try {
      const supabase = createSupabaseBrowserClient();
      const { error } = await supabase.auth.signUp({ email: email.trim(), password });
      setMessage(error ? "Sign-up failed. Check your details and try again." : "If registration is enabled, check your email to confirm your account.");
    } catch { setMessage("Authentication is not configured. Contact the administrator."); }
    finally { setBusy(false); }
  }

  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
    <h1 className="text-3xl font-semibold">Create your account</h1>
    <p className="mt-2 text-sm text-faint">Use your work email to get started.</p>
    <form onSubmit={submit} className="mt-8 space-y-5">
      <label className="block text-sm">Email<input className="mt-2 w-full rounded-lg border border-line bg-canvas px-3 py-2" type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} /></label>
      <label className="block text-sm">Password<input className="mt-2 w-full rounded-lg border border-line bg-canvas px-3 py-2" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={e => setPassword(e.target.value)} /></label>
      {message && <p role="status" className="text-sm">{message}</p>}
      <button className="w-full rounded-lg bg-white px-4 py-2 font-medium text-black disabled:opacity-60" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
    </form>
    <p className="mt-5 text-sm"><Link href="/login" className="underline">Back to sign in</Link></p>
  </main>;
}
