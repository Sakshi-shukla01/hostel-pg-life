"use client";

import { Loader2, MoonStar, Sparkles, WifiOff } from "lucide-react";
import Link from "next/link";
import { useId, type ButtonHTMLAttributes, type ReactNode } from "react";
import { buttonClass, type Variant } from "@/lib/styles";

export { buttonClass };

export function Button({
  variant = "primary",
  loading = false,
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button {...props} disabled={props.disabled || loading} className={buttonClass(variant, className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Logo({ compact = false, nameOnMobile = true }: { compact?: boolean; nameOnMobile?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5" aria-label="Hostel/PG Life home">
      <span className="sky grid h-10 w-10 place-items-center rounded-2xl text-white shadow-[0_8px_20px_-8px_rgb(91_46_230/0.8)]">
        <MoonStar className="h-5 w-5" />
      </span>
      {!compact && <span className={`font-display text-xl font-bold ${nameOnMobile ? "" : "hidden sm:inline"}`}>Hostel/PG Life</span>}
    </Link>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-[2.4rem] font-bold leading-[1.05]">{title}</h1>
        {subtitle && <p className="mt-2 max-w-2xl text-[15px] text-stone-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Badge({ children, tone = "stone" }: { children: ReactNode; tone?: "stone" | "green" | "amber" | "red" | "blue" }) {
  const tones = {
    stone: "bg-stone-100 text-stone-600",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-800",
    red: "bg-rose-50 text-rose-700",
    blue: "bg-brand-50 text-brand-700",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

/** Shows whether an answer came from Gemini or the offline fallback. */
export function AiBadge({ source }: { source?: string }) {
  if (!source) return null;
  return source === "gemini" ? (
    <span className="sky inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold text-white">
      <Sparkles className="h-3 w-3" /> Gemini AI
    </span>
  ) : (
    <Badge>
      <WifiOff className="h-3 w-3" /> Offline AI
    </Badge>
  );
}

export function Empty({ icon, title, text, action }: { icon?: ReactNode; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center py-14 text-center">
      {icon && <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600">{icon}</div>}
      <p className="font-display text-xl font-semibold">{title}</p>
      {text && <p className="mt-1 max-w-sm text-sm text-stone-500">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p role="alert" className="rounded-xl bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">{error}</p>;
}

export function Notice({ children }: { children: ReactNode }) {
  return <p className="rounded-xl bg-brand-50 px-3.5 py-2.5 text-sm text-brand-700">{children}</p>;
}

export function Spinner() {
  return (
    <div className="flex justify-center py-20 text-dusk">
      <Loader2 className="h-7 w-7 animate-spin" />
    </div>
  );
}

/** Match score ring drawn with the night-to-dawn gradient. */
export function ScoreRing({ score, size = 64 }: { score: number; size?: number }) {
  const id = useId().replace(/:/g, "");
  const r = size / 2 - 5;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${score}% match`} className="shrink-0">
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#3523c9" />
          <stop offset="45%" stopColor="#8a3ffc" />
          <stop offset="80%" stopColor="#ff5f8f" />
          <stop offset="100%" stopColor="#ffb43d" />
        </linearGradient>
      </defs>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#ece8fb" strokeWidth="6" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={`url(#g${id})`}
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={`${(score / 100) * c} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="53%" textAnchor="middle" dominantBaseline="middle" fontSize={score >= 100 ? size / 4.8 : size / 4} fontWeight="700" fill="#1a1638">
        {score}%
      </text>
    </svg>
  );
}
