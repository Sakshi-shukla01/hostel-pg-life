import { Moon } from "lucide-react";

/** Hours shown: 8 PM to noon (16 hours), the window where roommate fights happen. */
const START = 20;
const SPAN = 16;
const pct = (h: number) => (((h - START + 24) % 24) / SPAN) * 100;
const TICKS = [
  { h: 20, label: "8 pm" },
  { h: 0, label: "12 am" },
  { h: 4, label: "4 am" },
  { h: 8, label: "8 am" },
  { h: 12, label: "12 pm" },
];

type Sleeper = { name: string; initial: string; from: number; to: number; fromLabel: string; toLabel: string; faded?: boolean };

const PEOPLE: Sleeper[] = [
  { name: "You", initial: "P", from: 1, to: 8, fromLabel: "1:00", toLabel: "8:00" },
  { name: "Ananya", initial: "A", from: 0.5, to: 8, fromLabel: "12:30", toLabel: "8:00" },
  { name: "Rohan", initial: "R", from: 22, to: 5.5, fromLabel: "10:00", toLabel: "5:30", faded: true },
];

/**
 * The one animated moment on the landing page: sleep windows slide onto a
 * night-to-morning sky, the overlap shows, then the match result rises in.
 */
export function SkyTimeline({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`card ${compact ? "p-5" : "p-6 sm:p-7"} w-full`} aria-label="Example: two roommates with similar sleep times">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <p className="font-display text-lg font-semibold">Who sleeps when</p>
        <p className="text-xs text-stone-500">8 pm to noon</p>
      </div>

      <div className="space-y-3">
        {PEOPLE.map((p, i) => {
          const left = pct(p.from);
          const width = ((p.to - p.from + 24) % 24) / SPAN * 100;
          return (
            <div key={p.name} className={`flex items-center gap-3 ${p.faded ? "opacity-45" : ""}`}>
              <div className="flex w-[5.75rem] shrink-0 items-center gap-2">
                <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold text-white ${p.faded ? "bg-stone-400" : "sky"}`}>{p.initial}</span>
                <span className="text-sm font-medium">{p.name}</span>
              </div>
              <div className="sky relative h-10 flex-1 overflow-hidden rounded-xl">
                <div className="absolute inset-0 bg-white/55" />
                <div
                  className="absolute inset-y-1.5 flex origin-left animate-grow items-center gap-1.5 rounded-lg bg-ink px-2.5 text-[11px] font-semibold text-white shadow-lg"
                  style={{ left: `${left}%`, width: `${width}%`, animationDelay: `${0.25 + i * 0.22}s` }}
                >
                  <Moon className="h-3 w-3 shrink-0" />
                  <span className="truncate">{p.fromLabel} to {p.toLabel}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-2 flex pl-[6.5rem] text-[11px] text-stone-400">
        <div className="relative h-4 flex-1">
          {TICKS.map((t) => (
            <span key={t.label} className="absolute whitespace-nowrap -translate-x-1/2 first:translate-x-0 last:-translate-x-full" style={{ left: `${pct(t.h) || (t.h === 12 ? 100 : 0)}%` }}>
              {t.label}
            </span>
          ))}
        </div>
      </div>

      {!compact && (
        <div className="mt-5 flex animate-rise items-center gap-4 rounded-2xl bg-white/80 p-4" style={{ animationDelay: "1.3s" }}>
          <span className="sky grid h-14 w-14 shrink-0 place-items-center rounded-2xl font-display text-lg font-bold text-white">92%</span>
          <p className="text-sm leading-snug text-stone-600">
            <span className="font-semibold text-ink">You and Ananya</span> sleep within 30 minutes of each other, are both vegetarian and both study in silence.
            Rohan wakes at 5:30, so he isn&apos;t suggested.
          </p>
        </div>
      )}
    </div>
  );
}
