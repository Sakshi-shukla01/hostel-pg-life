// Plain style helpers: safe to use in server and client components.
export type Variant = "primary" | "secondary" | "ghost" | "danger";

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-55";

const VARIANTS: Record<Variant, string> = {
  primary: "sky text-white shadow-[0_10px_24px_-10px_rgb(91_46_230/0.7)] hover:brightness-110",
  secondary: "border border-stone-200 bg-white/85 text-ink hover:border-dusk/40 hover:bg-white",
  ghost: "text-stone-600 hover:bg-white/70",
  danger: "bg-red-600 text-white hover:bg-red-700",
};

/** Button look for <button> and <Link> (a button can't sit inside a link). */
export function buttonClass(variant: Variant = "primary", className = "") {
  return `${BASE} ${VARIANTS[variant]} ${className}`;
}
