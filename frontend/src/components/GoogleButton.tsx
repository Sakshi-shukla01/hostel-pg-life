"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

type GoogleId = {
  initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string }) => void;
  renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
};
declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

const SCRIPT = "https://accounts.google.com/gsi/client";

function loadScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts) return resolve();
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT}"]`);
    const s = existing || document.createElement("script");
    s.addEventListener("load", () => resolve());
    s.addEventListener("error", () => reject(new Error("Couldn't load Google sign-in")));
    if (!existing) {
      s.src = SCRIPT;
      s.async = true;
      document.head.appendChild(s);
    }
  });
}

/**
 * "Continue with Google". Uses the Client ID from the backend (/auth/config),
 * so only the backend .env needs GOOGLE_CLIENT_ID.
 */
export function GoogleButton({ role = "student", hostel = "default", onError }: { role?: string; hostel?: string; onError: (msg: string) => void }) {
  const { login } = useAuth();
  const router = useRouter();
  const box = useRef<HTMLDivElement>(null);
  const extra = useRef({ role, hostel });
  const [state, setState] = useState<"loading" | "ready" | "off">("loading");

  useEffect(() => {
    extra.current = { role, hostel };
  }, [role, hostel]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const cfg = await api<{ google_client_id: string | null }>("/auth/config");
        if (!cfg.google_client_id) {
          if (alive) setState("off");
          return;
        }
        await loadScript();
        if (!alive || !box.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: cfg.google_client_id,
          callback: async ({ credential }) => {
            try {
              const res = await api<{ token: string; user: User; is_new: boolean }>("/auth/google", { body: { credential, ...extra.current } });
              login(res.token, res.user);
              router.push(res.user.role !== "student" ? "/warden" : res.is_new ? "/profile" : "/dashboard");
            } catch (e) {
              onError((e as Error).message);
            }
          },
        });
        window.google.accounts.id.renderButton(box.current, { theme: "outline", size: "large", shape: "pill", text: "continue_with", width: Math.min(box.current.offsetWidth || 360, 400) });
        setState("ready");
      } catch {
        if (alive) setState("off");
      }
    })();
    return () => {
      alive = false;
    };
  }, [login, router, onError]);

  return (
    <div>
      <div ref={box} className={`flex min-h-11 justify-center ${state === "off" ? "hidden" : ""}`} />
      {state === "off" && (
        <div className="rounded-xl border border-dashed border-stone-300 px-4 py-3 text-center text-sm text-stone-500">
          Google sign-in isn&apos;t set up yet. Add <code className="rounded bg-stone-100 px-1">GOOGLE_CLIENT_ID</code> to the backend .env (see README).
        </div>
      )}
    </div>
  );
}
