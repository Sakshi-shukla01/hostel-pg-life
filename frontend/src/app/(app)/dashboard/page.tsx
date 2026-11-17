"use client";

import { ArrowRight, BedDouble, Bot, HeartHandshake, UserRound, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth";
import { AiBadge, PageHeader, ScoreRing, Spinner, buttonClass } from "@/components/ui";
import { api, rupees } from "@/lib/api";
import type { Complaint, Match, Profile, Room } from "@/lib/types";

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<{ profile: Profile | null; matches: Match[]; room: Room | null; complaints: Complaint[]; ai: string } | null>(null);

  useEffect(() => {
    (async () => {
      const [profile, room, complaints, health] = await Promise.all([
        api<Profile | null>("/profile/me"),
        api<Room | null>("/rooms/me"),
        api<Complaint[]>("/complaints/mine"),
        api<{ ai_mode: string }>("/health"),
      ]);
      const matches = profile ? await api<Match[]>("/matches").catch(() => []) : [];
      setData({ profile, matches, room, complaints, ai: health.ai_mode });
    })();
  }, []);

  if (!data) return <Spinner />;
  const hour = new Date().getHours();
  const greeting = hour < 5 ? "Up late" : hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const balance = data.room?.balances[user?.id || ""] ?? 0;
  const open = data.complaints.filter((c) => c.status !== "resolved").length;

  return (
    <>
      <PageHeader title={`${greeting}, ${user?.name.split(" ")[0]}`} subtitle="Your matches, money and room in one place." action={<AiBadge source={data.ai} />} />
      {!data.profile && (
        <div className="card mb-6 flex flex-wrap items-center justify-between gap-4 border-brand-100 bg-brand-50">
          <div className="flex items-center gap-3"><UserRound className="h-6 w-6 text-brand-700" /><p>Build your profile in a 2-minute AI chat to get roommate matches.</p></div>
          <Link href="/profile" className={buttonClass("primary")}>Start</Link>
        </div>
      )}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="card md:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-semibold"><HeartHandshake className="h-4 w-4" /> Top matches</h2>
            <Link href="/matches" className="flex items-center gap-1 text-sm text-brand-700">All <ArrowRight className="h-3 w-3" /></Link>
          </div>
          {data.matches.length === 0 ? <p className="text-sm text-stone-500">No matches yet.</p> : (
            <div className="space-y-3">
              {data.matches.slice(0, 3).map((m) => (
                <div key={m.user_id} className="flex items-center gap-4">
                  <ScoreRing score={m.score} size={48} />
                  <div className="min-w-0">
                    <p className="font-medium">{m.name}</p>
                    <p className="truncate text-sm text-stone-500">{m.reasons[0] || m.area}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="space-y-6">
          <Link href="/room" className="card block hover:border-brand-500">
            <p className="label flex items-center gap-1"><BedDouble className="h-3 w-3" /> Room balance</p>
            {data.room ? (
              <p className={`font-display text-3xl font-semibold ${balance >= 0 ? "text-brand-600" : "text-red-600"}`}>{balance >= 0 ? "+" : "−"}{rupees(Math.abs(balance))}</p>
            ) : <p className="text-sm text-stone-500">No room yet</p>}
          </Link>
          <Link href="/complaints" className="card block hover:border-brand-500">
            <p className="label flex items-center gap-1"><Wrench className="h-3 w-3" /> Open complaints</p>
            <p className="font-display text-3xl font-semibold">{open}</p>
          </Link>
          <Link href="/assistant" className="sky block rounded-[1.75rem] p-6 text-white shadow-[0_18px_40px_-20px_rgb(91_46_230/0.8)] transition hover:brightness-110">
            <Bot className="mb-2 h-6 w-6" />
            <p className="font-medium">Ask the AI assistant</p>
            <p className="text-sm text-white/85">“Who owes me money?” “Any cooler under ₹2000?”</p>
          </Link>
        </div>
      </div>
    </>
  );
}
