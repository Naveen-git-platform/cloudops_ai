"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setBusy(true);
    try {
      const client = createSupabaseBrowserClient();
      const result = await client.auth.signInWithPassword({ email: email.trim(), password });
      if (result.error) setMessage("Sign-in failed. Check your details and try again.");
      else window.location.assign("/");
    } catch {
      setMessage("Authentication is not configured. Contact your administrator.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
    <h1 className="text-3xl font-semibold">Sign in to CloudOps AI</h1>
    <form onSubmit={submit} className="mt-8 space-y-5">
      <label className="block text-sm">Email<input className="mt-2 w-full rounded-lg border border-line bg-canvas px-3 py-2" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>
      <label className="block text-sm">Password<input className="mt-2 w-full rounded-lg border border-line bg-canvas px-3 py-2" type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} /></label>
      {message && <p role="alert" className="text-sm text-red-400">{message}</p>}
      <button className="w-full rounded-lg bg-white px-4 py-2 font-medium text-black disabled:opacity-60" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form>
    <div className="mt-5 flex justify-between text-sm"><Link href="/signup" className="underline">Create account</Link><Link href="/forgot-password" className="underline">Forgot password?</Link></div>
  </main>;
}
