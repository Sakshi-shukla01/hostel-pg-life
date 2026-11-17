"use client";

import { KeyRound } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { AuthShell } from "@/components/AuthShell";
import { OtpInput } from "@/components/OtpInput";
import { PasswordField, passwordOk } from "@/components/PasswordField";
import { useAuth } from "@/components/auth";
import { Button, ErrorNote, Notice, Spinner } from "@/components/ui";
import { useResend } from "@/components/useResend";
import { api } from "@/lib/api";
import { saveDevCode } from "@/lib/devcode";
import type { User } from "@/lib/types";

function Forgot() {
  const params = useSearchParams();
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState(params.get("email") || "");
  const [step, setStep] = useState<"email" | "reset">("email");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { wait, setWait, resend, devCode, setDevCode, message } = useResend(email, "reset");

  async function sendCode(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ sent: boolean; dev_code?: string }>("/auth/forgot-password", { body: { email } });
      saveDevCode(email, res.dev_code);
      setDevCode(res.dev_code || null);
      setWait(60);
      setStep("reset");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reset(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!passwordOk(password)) return setError("Password needs at least 8 characters, with letters and numbers.");
    if (password !== confirm) return setError("The two passwords don't match.");
    setBusy(true);
    try {
      const res = await api<{ token: string; user: User }>("/auth/reset-password", { body: { email, code, new_password: password } });
      login(res.token, res.user);
      router.push(res.user.role === "student" ? "/dashboard" : "/warden");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (step === "email")
    return (
      <AuthShell title="Reset your password" subtitle="Enter your account email and we'll send you a code.">
        <form onSubmit={sendCode} className="space-y-4">
          <div className="sky grid h-16 w-16 place-items-center rounded-3xl text-white"><KeyRound className="h-7 w-7" /></div>
          <div>
            <label htmlFor="email" className="label">Email</label>
            <input id="email" className="field" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <ErrorNote error={error} />
          <Button type="submit" loading={busy} className="w-full py-3 text-base">Send code</Button>
          <p className="text-center text-sm"><Link href="/login" className="text-stone-500 hover:text-ink">Back to log in</Link></p>
        </form>
      </AuthShell>
    );

  return (
    <AuthShell title="Choose a new password" subtitle={<>If <span className="font-semibold text-ink">{email}</span> has an account, a 6-digit code is on its way.</>}>
      <form onSubmit={reset} className="space-y-4">
        <div>
          <span className="label">Code from the email</span>
          <OtpInput value={code} onChange={setCode} disabled={busy} />
        </div>
        {devCode && <Notice>Email isn&apos;t set up on this server yet, so here is your code: <b className="tracking-widest">{devCode}</b>.</Notice>}
        {message && !devCode && <Notice>{message}</Notice>}
        <PasswordField id="new-password" label="New password" value={password} onChange={setPassword} showStrength autoComplete="new-password" />
        <PasswordField id="confirm-password" label="Type it again" value={confirm} onChange={setConfirm} autoComplete="new-password" />
        <ErrorNote error={error} />
        <Button type="submit" loading={busy} disabled={code.length !== 6} className="w-full py-3 text-base">Save new password</Button>
        <p className="text-center text-sm text-stone-500">
          {wait > 0 ? <span>Ask for a new code in {wait}s</span> : <button type="button" onClick={resend} className="font-semibold text-brand-600 hover:underline">Send a new code</button>}
        </p>
      </form>
    </AuthShell>
  );
}

export default function ForgotPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Forgot />
    </Suspense>
  );
}
