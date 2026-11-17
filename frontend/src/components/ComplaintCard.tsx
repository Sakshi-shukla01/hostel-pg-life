"use client";

import { AlertOctagon } from "lucide-react";
import type { ReactNode } from "react";
import { AiBadge, Badge } from "@/components/ui";
import { fileUrl } from "@/lib/api";
import type { Complaint } from "@/lib/types";

const PRIORITY_TONE = { high: "red", medium: "amber", low: "stone" } as const;
const STATUS_TONE = { open: "blue", in_progress: "amber", resolved: "green" } as const;

export function ComplaintCard({ c, children }: { c: Complaint; children?: ReactNode }) {
  const photo = fileUrl(c.photo_url);
  return (
    <div className={`card ${c.escalated ? "border-red-300" : ""}`}>
      <div className="flex flex-wrap items-start gap-4">
        {photo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={photo} alt="" className="h-20 w-20 rounded-xl object-cover" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{c.title}</p>
            <Badge tone={STATUS_TONE[c.status]}>{c.status.replace("_", " ")}</Badge>
            <Badge tone={PRIORITY_TONE[c.priority]}>{c.priority} priority</Badge>
            <Badge>{c.category}</Badge>
            {c.escalated && <Badge tone="red"><AlertOctagon className="h-3 w-3" /> Escalated (48h+)</Badge>}
          </div>
          <p className="mt-1 text-sm text-stone-600">{c.ai_summary}</p>
          <p className="mt-1 flex items-center gap-2 text-xs text-stone-400">
            <span>{c.raiser_name}, room {c.room_no || "not given"}</span>
            <span>{new Date(c.created_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}</span>
            <AiBadge source={c.ai_source} />
          </p>
          {c.notes.map((n, i) => <p key={i} className="mt-1 text-xs text-stone-500">💬 {n.by}: {n.text}</p>)}
        </div>
      </div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
