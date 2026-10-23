"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const client = createSupabaseBrowserClient();
      const result = await client.auth.resetPasswordForEmail(email.trim(), { redirectTo: window.location.origin + "/reset-password" });
      setMessage(result.error ? "Unable to send a recovery email. Try again later." : "If an account exists for this email, a recovery link has been sent.");
    } catch { setMessage("Authentication is not configured. Contact your administrator."); }
    finally { setBusy(false); }
  }
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
    <h1 className="text-3xl font-semibold">Reset your password</h1>
    <p className="mt-2 text-sm text-faint">We’ll send a recovery link if an account exists.</p>
    <form onSubmit={submit} className="mt-8 space-y-5">
      <label className="block text-sm">Email<input className="mt-2 w-full rounded-lg border border-line bg-canvas px-3 py-2" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>
      {message && <p role="status" className="text-sm">{message}</p>}
      <button className="w-full rounded-lg bg-white px-4 py-2 font-medium text-black disabled:opacity-60" disabled={busy}>{busy ? "Sending…" : "Send recovery link"}</button>
    </form>
    <p className="mt-5 text-sm"><Link href="/login" className="underline">Back to sign in</Link></p>
  </main>;
}
