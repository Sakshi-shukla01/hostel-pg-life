"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AuthShell } from "@/components/AuthShell";
import { GoogleButton } from "@/components/GoogleButton";
import { PasswordField, passwordOk } from "@/components/PasswordField";
import { useAuth } from "@/components/auth";
import { Button, ErrorNote } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { saveDevCode } from "@/lib/devcode";
import type { User } from "@/lib/types";

type Session = { token: string; user: User };
type Pending = { needs_verification: true; email: string; dev_code?: string };

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "student", hostel: "sunrise-pg" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const register = mode === "register";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (register && !passwordOk(form.password)) {
      setError("Password needs at least 8 characters, with letters and numbers.");
      return;
    }
    setBusy(true);
    try {
      if (register) {
        const res = await api<Pending>("/auth/register", { body: form });
        saveDevCode(res.email, res.dev_code);
        router.push(`/verify?email=${encodeURIComponent(res.email)}`);
      } else {
        const res = await api<Session>("/auth/login", { body: { email: form.email, password: form.password } });
        login(res.token, res.user);
        router.push(res.user.role === "student" ? "/dashboard" : "/warden");
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        router.push(`/verify?email=${encodeURIComponent(form.email)}&resend=1`);
        return;
      }
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title={register ? "Create your account" : "Welcome back"}
      subtitle={
        register ? (
          <>Already have one? <Link href="/login" className="font-semibold text-brand-600 hover:underline">Log in</Link></>
        ) : (
          <>New here? <Link href="/register" className="font-semibold text-brand-600 hover:underline">Create an account</Link></>
        )
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {register && (
          <div>
            <label htmlFor="name" className="label">Full name</label>
            <input id="name" className="field" required autoComplete="name" value={form.name} onChange={(e) => set("name", e.target.value)} />
          </div>
        )}
        <div>
          <label htmlFor="email" className="label">Email</label>
          <input id="email" className="field" type="email" required autoComplete="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
          {register && <p className="mt-1.5 text-xs text-stone-500">A college email (.ac.in or .edu) gets you a verified-student badge.</p>}
        </div>
        <PasswordField value={form.password} onChange={(v) => set("password", v)} showStrength={register} autoComplete={register ? "new-password" : "current-password"} />
        {!register && (
          <div className="-mt-1 text-right">
            <Link href={`/forgot${form.email ? `?email=${encodeURIComponent(form.email)}` : ""}`} className="text-sm font-medium text-brand-600 hover:underline">Forgot password?</Link>
          </div>
        )}
        {register && (
          <>
            <div>
              <span className="label">I am a</span>
              <div className="grid grid-cols-2 gap-2 rounded-xl bg-stone-100 p-1">
                {[["student", "Student or resident"], ["warden", "Warden or PG owner"]].map(([v, l]) => (
                  <button key={v} type="button" onClick={() => set("role", v)} aria-pressed={form.role === v}
                    className={`rounded-lg px-3 py-2 text-sm font-medium transition ${form.role === v ? "bg-white text-ink shadow-sm" : "text-stone-500 hover:text-ink"}`}>
                    {l}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label htmlFor="hostel" className="label">Hostel or PG code</label>
              <input id="hostel" className="field" value={form.hostel} onChange={(e) => set("hostel", e.target.value)} />
              <p className="mt-1.5 text-xs text-stone-500">Everyone in the same hostel uses the same code. Ask your warden for it.</p>
            </div>
          </>
        )}
        <ErrorNote error={error} />
        <Button type="submit" loading={busy} className="w-full py-3 text-base">{register ? "Create account" : "Log in"}</Button>
      </form>

      <div className="my-6 flex items-center gap-3 text-xs text-stone-400">
        <span className="h-px flex-1 bg-stone-200" /> or <span className="h-px flex-1 bg-stone-200" />
      </div>
      <GoogleButton role={form.role} hostel={form.hostel} onError={setError} />

      {!register && <p className="mt-8 rounded-xl bg-white/60 px-4 py-3 text-center text-xs text-stone-500">Demo accounts: demo@coep.ac.in or warden@sunrise.in, password demo1234</p>}
    </AuthShell>
  );
}
