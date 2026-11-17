"use client";

import { BedDouble, Bot, HeartHandshake, Home, LogOut, Menu, MessageSquare, ShieldCheck, ShoppingBag, UserRound, Wrench, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth";
import { Logo, Spinner } from "@/components/ui";

const STUDENT_NAV = [
  { href: "/dashboard", label: "Home", icon: Home },
  { href: "/profile", label: "My profile", icon: UserRound },
  { href: "/matches", label: "Matches", icon: HeartHandshake },
  { href: "/requests", label: "Requests and chat", icon: MessageSquare },
  { href: "/room", label: "My room", icon: BedDouble },
  { href: "/complaints", label: "Complaints", icon: Wrench },
  { href: "/market", label: "Marketplace", icon: ShoppingBag },
  { href: "/assistant", label: "AI assistant", icon: Bot },
];
const WARDEN_NAV = [
  { href: "/warden", label: "Warden dashboard", icon: ShieldCheck },
  { href: "/market", label: "Marketplace", icon: ShoppingBag },
  { href: "/assistant", label: "AI assistant", icon: Bot },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return <Spinner />;
  const nav = user.role === "student" ? STUDENT_NAV : WARDEN_NAV;
  const initials = user.name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="flex min-h-screen">
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-white/60 bg-white/70 px-4 py-6 backdrop-blur-2xl transition-transform md:sticky md:top-0 md:h-screen md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="mb-8 px-2"><Logo /></div>
        <nav className="flex-1 space-y-1" aria-label="Main">
          {nav.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href) || (href === "/requests" && pathname.startsWith("/chat"));
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-2xl px-3.5 py-2.5 text-[15px] transition ${
                  active ? "sky font-semibold text-white shadow-[0_10px_22px_-12px_rgb(91_46_230/0.9)]" : "text-stone-600 hover:bg-white hover:text-ink"
                }`}
              >
                <Icon className="h-[18px] w-[18px]" /> {label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-3 rounded-2xl bg-white/80 p-3 ring-1 ring-stone-200/70">
          {user.picture ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={user.picture} alt="" className="h-10 w-10 rounded-full object-cover" referrerPolicy="no-referrer" />
          ) : (
            <span className="sky grid h-10 w-10 place-items-center rounded-full text-sm font-bold text-white">{initials}</span>
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{user.name}</p>
            <p className="truncate text-xs text-stone-500">{user.email}</p>
          </div>
          <button onClick={logout} aria-label="Log out" title="Log out" className="grid h-9 w-9 place-items-center rounded-xl text-stone-400 hover:bg-rose-50 hover:text-rose-600">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-20 bg-ink/30 backdrop-blur-sm md:hidden" onClick={() => setOpen(false)} />}
      <main className="min-w-0 flex-1">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/60 bg-white/70 px-4 py-3 backdrop-blur-xl md:hidden">
          <Logo />
          <button onClick={() => setOpen(!open)} aria-label={open ? "Close menu" : "Open menu"} className="grid h-10 w-10 place-items-center rounded-xl hover:bg-white">
            {open ? <X /> : <Menu />}
          </button>
        </div>
        <div className="mx-auto max-w-5xl px-4 py-8 md:px-10 md:py-10">{children}</div>
      </main>
    </div>
  );
}
