"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const client = createSupabaseBrowserClient();
      const result = await client.auth.updateUser({ password });
      if (result.error) setMessage("Unable to update the password. Request a new recovery link and try again.");
      else window.location.assign("/login?reset=success");
    } catch { setMessage("Authentication is not configured. Contact your administrator."); }
    finally { setBusy(false); }
  }
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
    <h1 className="text-3xl font-semibold">Choose a new password</h1>
    <form onSubmit={submit} className="mt-8 space-y-5">
      <label className="block text-sm">New password<input className="mt-2 w-full rounded-lg border border-line bg-canvas px-3 py-2" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={event => setPassword(event.target.value)} /></label>
      {message && <p role="alert" className="text-sm">{message}</p>}
      <button className="w-full rounded-lg bg-white px-4 py-2 font-medium text-black disabled:opacity-60" disabled={busy}>{busy ? "Updating…" : "Update password"}</button>
    </form>
    <p className="mt-5 text-sm"><Link href="/login" className="underline">Back to sign in</Link></p>
  </main>;
}
