import { Check } from "lucide-react";
import type { ReactNode } from "react";
import { SkyTimeline } from "@/components/SkyTimeline";
import { Logo } from "@/components/ui";

const POINTS = ["Matched on sleep, food, cleanliness and noise", "Contact details stay hidden until you both say yes", "Bills, chores and complaints in one place"];

/** Split screen: the night-to-dawn sky on the left, the form on the right. */
export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      <aside className="sky relative m-3 hidden flex-col justify-between overflow-hidden rounded-[2rem] p-10 text-white lg:flex">
        <div className="[&_span.font-display]:text-white">
          <Logo />
        </div>
        <div>
          <h2 className="max-w-md font-display text-[2.6rem] font-bold leading-[1.05]">Share a room with someone on your clock.</h2>
          <ul className="mt-6 space-y-2.5">
            {POINTS.map((p) => (
              <li key={p} className="flex items-center gap-2.5 text-white/90">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-white/25"><Check className="h-3 w-3" /></span>
                {p}
              </li>
            ))}
          </ul>
        </div>
        <div className="max-w-md text-ink">
          <SkyTimeline compact />
        </div>
      </aside>

      <main className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h1 className="font-display text-4xl font-bold leading-tight">{title}</h1>
          {subtitle && <div className="mt-2 text-[15px] text-stone-500">{subtitle}</div>}
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
