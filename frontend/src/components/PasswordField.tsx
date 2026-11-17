"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

function strength(pw: string) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[a-z]/i.test(pw) && /\d/.test(pw)) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw) || /[^A-Za-z0-9]/.test(pw)) s++;
  if (pw.length >= 12) s++;
  return s;
}
const LABELS = ["Too short", "Weak", "Okay", "Good", "Strong"];
const COLORS = ["bg-stone-200", "bg-rose-400", "bg-amber-400", "bg-dusk", "bg-emerald-500"];

export function PasswordField({
  label = "Password",
  value,
  onChange,
  showStrength = false,
  autoComplete = "current-password",
  id = "password",
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  showStrength?: boolean;
  autoComplete?: string;
  id?: string;
}) {
  const [show, setShow] = useState(false);
  const s = strength(value);
  const ok = value.length >= 8 && /[a-z]/i.test(value) && /\d/.test(value);
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <div className="relative">
        <input
          id={id}
          className="field"
          style={{ paddingRight: "2.75rem" }}
          type={show ? "text" : "password"}
          required
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"}
          className="absolute inset-y-0 right-0 grid w-11 place-items-center text-stone-400 hover:text-ink">
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {showStrength && (
        <div className="mt-2">
          <div className="flex gap-1.5">
            {[1, 2, 3, 4].map((n) => <span key={n} className={`h-1.5 flex-1 rounded-full transition ${s >= n ? COLORS[s] : "bg-stone-200"}`} />)}
          </div>
          <p className={`mt-1.5 text-xs ${ok ? "text-stone-500" : "text-stone-400"}`}>
            {value ? `${LABELS[s]}. ` : ""}At least 8 characters with letters and numbers.
          </p>
        </div>
      )}
    </div>
  );
}

export const passwordOk = (pw: string) => pw.length >= 8 && /[a-z]/i.test(pw) && /\d/.test(pw);
