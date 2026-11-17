"use client";

import { BadgeCheck, BedDouble, Flag, Inbox, MessageSquare } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Empty, ErrorNote, PageHeader, Spinner, buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import type { MatchRequest } from "@/lib/types";

export default function RequestsPage() {
  const router = useRouter();
  const [reqs, setReqs] = useState<MatchRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<MatchRequest[]>("/requests").then(setReqs).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
  }, [load]);

  async function act(id: string, action: "accept" | "reject") {
    await api(`/requests/${id}/${action}`, { method: "POST" });
    load();
  }
  async function makeRoom(r: MatchRequest) {
    try {
      await api("/rooms", { body: { name: `Room with ${r.other_user.name.split(" ")[0]}`, request_id: r.id } });
      router.push("/room");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function report(r: MatchRequest) {
    const reason = window.prompt(`Why are you reporting ${r.other_user.name}? They will also be blocked.`);
    if (!reason) return;
    await api("/reports", { body: { user_id: r.other_user.id, reason } });
    setError(`Reported and blocked ${r.other_user.name}.`);
  }

  if (!reqs) return <Spinner />;
  return (
    <>
      <PageHeader title="Requests & chat" subtitle="Contact details and chat unlock only after both people agree." />
      <ErrorNote error={error} />
      {reqs.length === 0 ? (
        <Empty icon={<Inbox className="h-8 w-8" />} title="No requests yet" text="Send a request from your matches." action={<Link href="/matches" className={buttonClass("primary")}>See matches</Link>} />
      ) : (
        <div className="space-y-3">
          {reqs.map((r) => (
            <div key={r.id} className="card flex flex-wrap items-center gap-4">
              <div className="grid h-11 w-11 place-items-center rounded-full bg-brand-50 font-semibold text-brand-700">{r.other_user.name[0]}</div>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 font-medium">
                  {r.other_user.name} {r.other_user.verified && <BadgeCheck className="h-4 w-4 text-brand-600" />}
                  <Badge tone="blue">{r.direction === "incoming" ? "Sent to you" : "You sent"}</Badge>
                  <Badge tone={r.status === "accepted" ? "green" : r.status === "rejected" ? "red" : "stone"}>{r.status}</Badge>
                </p>
                {r.message && <p className="truncate text-sm text-stone-500">“{r.message}”</p>}
                {r.other_user.email && <p className="text-xs text-stone-500">Contact: {r.other_user.email}</p>}
              </div>
              <div className="flex flex-wrap gap-2">
                {r.direction === "incoming" && r.status === "pending" && (
                  <>
                    <Button onClick={() => act(r.id, "accept")}>Accept</Button>
                    <Button variant="secondary" onClick={() => act(r.id, "reject")}>Decline</Button>
                  </>
                )}
                {r.status === "accepted" && (
                  <>
                    <Link href={`/chat/${r.id}`} className={buttonClass("secondary")}><MessageSquare className="h-4 w-4" /> Open chat</Link>
                    <Button variant="secondary" onClick={() => makeRoom(r)}><BedDouble className="h-4 w-4" /> Make our room</Button>
                  </>
                )}
                <Button variant="ghost" onClick={() => report(r)} aria-label="Report"><Flag className="h-4 w-4" /></Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
