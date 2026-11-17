"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { saveDevCode } from "@/lib/devcode";

/** Resend a code with a 60-second wait between requests (matches the backend). */
export function useResend(email: string, purpose: "verify" | "reset") {
  const [wait, setWait] = useState(0);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  const resend = useCallback(async () => {
    setMessage(null);
    try {
      const res = await api<{ sent: boolean; dev_code?: string }>("/auth/resend-code", { body: { email, purpose } });
      saveDevCode(email, res.dev_code);
      setDevCode(res.dev_code || null);
      setMessage(`We sent a new code to ${email}.`);
      setWait(60);
    } catch (e) {
      const msg = (e as Error).message;
      const secs = Number(msg.match(/wait (\d+) seconds/)?.[1]);
      if (secs) setWait(secs);
      setMessage(msg);
    }
  }, [email, purpose]);

  return { wait, setWait, resend, devCode, setDevCode, message };
}
