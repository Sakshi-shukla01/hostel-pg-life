"use client";

import { AlertTriangle, BadgeCheck, CheckCircle2, HeartHandshake, MapPin, Moon, Sparkles, Sun, Utensils } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AiBadge, Badge, Button, Empty, ErrorNote, PageHeader, ScoreRing, Spinner, buttonClass } from "@/components/ui";
import { api, rupees } from "@/lib/api";
import type { Match } from "@/lib/types";

export default function MatchesPage() {
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Match[]>("/matches").then(setMatches).catch((e) => setError(e.message));
  }, []);

  if (error?.includes("profile"))
    return <Empty icon={<HeartHandshake className="h-8 w-8" />} title="Create your profile first" text="The AI needs your habits to find matches." action={<Link href="/profile" className={buttonClass("primary")}>Build my profile</Link>} />;
  if (!matches) return error ? <ErrorNote error={error} /> : <Spinner />;

  const first = matches[0];
  return (
    <>
      <PageHeader
        title="Your matches"
        subtitle={first ? `Each score is 70% daily habits and 30% personality. Personality uses ${first.embedding_source === "gemini" ? "Gemini" : "local"} embeddings, and habit weights are ${first.weights_source === "learned" ? "learned from roommate ratings" : "the defaults"}.` : undefined}
      />
      {matches.length === 0 ? (
        <Empty icon={<HeartHandshake className="h-8 w-8" />} title="No matches yet" text="Nobody in your city passes your filters yet. Try widening your budget or removing a dealbreaker." />
      ) : (
        <div className="space-y-4">{matches.map((m) => <MatchCard key={m.user_id} m={m} />)}</div>
      )}
    </>
  );
}

function MatchCard({ m }: { m: Match }) {
  const [summary, setSummary] = useState<{ text: string; source: string } | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [status, setStatus] = useState(m.request_status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function why() {
    setLoadingSummary(true);
    try {
      setSummary(await api(`/matches/${m.user_id}/summary`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingSummary(false);
    }
  }
  async function connect() {
    setBusy(true);
    try {
      await api("/requests", { body: { to_user: m.user_id, message: "Hi! The app says we'd make good roommates. Want to chat?" } });
      setStatus("pending");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="flex flex-wrap items-start gap-5">
        <ScoreRing score={m.score} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold">{m.name}</h3>
            {m.verified && <Badge tone="green"><BadgeCheck className="h-3 w-3" /> Verified student</Badge>}
          </div>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-3 text-sm text-stone-500">
            <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {m.area || "—"}</span>
            <span>{m.college_or_office}</span>
            <span>{rupees(m.budget_min)}–{rupees(m.budget_max)}</span>
          </p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-stone-600">
            <span className="flex items-center gap-1"><Moon className="h-3 w-3" /> sleeps {m.answers.sleep_time}</span>
            <span className="flex items-center gap-1"><Sun className="h-3 w-3" /> wakes {m.answers.wake_time}</span>
            <span className="flex items-center gap-1"><Utensils className="h-3 w-3" /> {m.answers.food}</span>
            <span className="rounded-full bg-brand-50 px-2 py-0.5 text-brand-700">Habits {m.habits_score}%</span>
            <span className="rounded-full bg-rose-50 px-2 py-0.5 text-rose-700">Personality {m.personality_score}%</span>
          </div>
          {m.bio && <p className="mt-2 line-clamp-2 text-sm text-stone-700">{m.bio}</p>}
        </div>
        <div className="flex flex-col gap-2">
          {status ? <Badge tone={status === "accepted" ? "green" : "stone"}>Request {status}</Badge> : <Button onClick={connect} loading={busy}>Send request</Button>}
          <Button variant="secondary" onClick={why} loading={loadingSummary}><Sparkles className="h-4 w-4" /> Why we match</Button>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <ul className="space-y-1 text-sm">
          {m.reasons.map((r) => <li key={r} className="flex items-start gap-2 text-brand-700"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> {r}</li>)}
        </ul>
        <ul className="space-y-1 text-sm">
          {m.conflicts.map((c) => <li key={c} className="flex items-start gap-2 text-amber-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {c}</li>)}
        </ul>
      </div>
      {summary && (
        <div className="mt-4 rounded-xl bg-amber-50/60 p-4 text-sm">
          <div className="mb-1"><AiBadge source={summary.source} /></div>
          {summary.text}
        </div>
      )}
      <ErrorNote error={error} />
    </div>
  );
}
