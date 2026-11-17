"use client";

import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";

/** Six boxes for a 6-digit code: auto-advance, backspace goes back, paste fills all. */
export function OtpInput({ value, onChange, onComplete, disabled }: { value: string; onChange: (v: string) => void; onComplete?: (v: string) => void; disabled?: boolean }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = Array.from({ length: 6 }, (_, i) => value[i] || "");

  function set(next: string) {
    const clean = next.replace(/\D/g, "").slice(0, 6);
    onChange(clean);
    if (clean.length === 6) onComplete?.(clean);
  }

  function type(i: number, raw: string) {
    const d = raw.replace(/\D/g, "").slice(-1);
    if (!d) return;
    const arr = [...digits];
    arr[i] = d;
    set(arr.join(""));
    refs.current[Math.min(i + 1, 5)]?.focus();
  }

  function key(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace") {
      e.preventDefault();
      const arr = [...digits];
      if (arr[i]) arr[i] = "";
      else if (i > 0) {
        arr[i - 1] = "";
        refs.current[i - 1]?.focus();
      }
      onChange(arr.join("").slice(0, 6));
    }
    if (e.key === "ArrowLeft") refs.current[Math.max(i - 1, 0)]?.focus();
    if (e.key === "ArrowRight") refs.current[Math.min(i + 1, 5)]?.focus();
  }

  function paste(e: ClipboardEvent<HTMLInputElement>) {
    e.preventDefault();
    set(e.clipboardData.getData("text"));
    refs.current[5]?.focus();
  }

  return (
    <div className="flex justify-between gap-2" role="group" aria-label="6-digit code">
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          value={d}
          disabled={disabled}
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          aria-label={`Digit ${i + 1}`}
          maxLength={1}
          onChange={(e) => type(i, e.target.value)}
          onKeyDown={(e) => key(i, e)}
          onPaste={paste}
          onFocus={(e) => e.target.select()}
          className={`h-14 w-full min-w-0 rounded-2xl border bg-white/90 text-center font-display text-2xl font-bold outline-none transition focus:border-dusk focus:ring-4 focus:ring-dusk/15 ${d ? "border-dusk/50" : "border-stone-200"}`}
        />
      ))}
    </div>
  );
}
