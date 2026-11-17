"use client";

import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { OtpInput } from "@/components/OtpInput";
import { useAuth } from "@/components/auth";
import { Button, ErrorNote, Notice, Spinner } from "@/components/ui";
import { useResend } from "@/components/useResend";
import { api } from "@/lib/api";
import { readDevCode } from "@/lib/devcode";
import type { User } from "@/lib/types";

function Verify() {
  const params = useSearchParams();
  const email = params.get("email") || "";
  const router = useRouter();
  const { login } = useAuth();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { wait, setWait, resend, devCode, setDevCode, message } = useResend(email, "verify");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (params.get("resend") === "1") resend();
    else {
      setDevCode(readDevCode(email));
      setWait(60);
    }
  }, [params, email, resend, setDevCode, setWait]);

  async function verify(value = code) {
    if (value.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ token: string; user: User }>("/auth/verify-email", { body: { email, code: value } });
      login(res.token, res.user);
      router.push(res.user.role === "student" ? "/profile" : "/warden");
    } catch (e) {
      setError((e as Error).message);
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  if (!email)
    return (
      <AuthShell title="Check your email">
        <p className="text-stone-600">This link is missing the email address. <Link href="/register" className="font-semibold text-brand-600">Start again</Link>.</p>
      </AuthShell>
    );

  return (
    <AuthShell title="Check your email" subtitle={<>We sent a 6-digit code to <span className="font-semibold text-ink">{email}</span>. It expires in 10 minutes.</>}>
      <div className="space-y-5">
        <div className="sky mx-auto grid h-16 w-16 place-items-center rounded-3xl text-white lg:mx-0"><MailCheck className="h-7 w-7" /></div>
        <OtpInput value={code} onChange={setCode} onComplete={verify} disabled={busy} />
        {devCode && (
          <Notice>
            Email isn&apos;t set up on this server yet, so here is your code: <b className="tracking-widest">{devCode}</b>. Add Gmail settings to the backend .env to send real emails.
          </Notice>
        )}
        {message && !devCode && <Notice>{message}</Notice>}
        <ErrorNote error={error} />
        <Button onClick={() => verify()} loading={busy} disabled={code.length !== 6} className="w-full py-3 text-base">Verify email</Button>
        <p className="text-center text-sm text-stone-500">
          Didn&apos;t get it? Check spam, or{" "}
          {wait > 0 ? <span>ask again in {wait}s</span> : <button onClick={resend} className="font-semibold text-brand-600 hover:underline">send a new code</button>}
        </p>
        <p className="text-center text-sm"><Link href="/register" className="text-stone-500 hover:text-ink">Use a different email</Link></p>
      </div>
    </AuthShell>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Verify />
    </Suspense>
  );
}
