import { BookOpen, Bot, HeartHandshake, Receipt, ShoppingBag, Wrench } from "lucide-react";
import Link from "next/link";
import { SkyTimeline } from "@/components/SkyTimeline";
import { Logo } from "@/components/ui";
import { buttonClass } from "@/lib/styles";

const FEATURES = [
  { icon: HeartHandshake, title: "Matches that explain themselves", text: "Sleep time, cleanliness, food, guests and noise, plus personality from your bio. Each match lists what you share and what to talk about first." },
  { icon: Receipt, title: "Bills split in seconds", text: "Photograph the electricity bill and the amount fills itself in. Everyone settles up in the fewest payments." },
  { icon: Wrench, title: "Complaints that get fixed", text: "Snap the leaking tap. It reaches the warden with the right category and priority, and escalates after 48 hours." },
  { icon: Bot, title: "An assistant that knows your room", text: "Ask “who owes me money?” or “any cooler under ₹2,000?” and get an answer from your own data." },
  { icon: BookOpen, title: "Your PG’s rulebook, searchable", text: "Gate timings, visitor rules, rent dates. Answers come straight from the rulebook your warden uploads." },
  { icon: ShoppingBag, title: "A marketplace for your building", text: "Sell the cooler to a junior instead of the kabadiwala. Listings fill themselves from a photo and scams get flagged." },
];

const STEPS = [
  { title: "Chat for two minutes", text: "Answer a few friendly questions about your day. No long forms." },
  { title: "See who fits", text: "Matches in your city and budget, ranked, with the reasons spelled out." },
  { title: "Move in and stay friends", text: "Chat, agree on house rules, then split bills and chores in the app." },
];

export default function Landing() {
  return (
    <div className="min-h-screen overflow-x-hidden">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Logo nameOnMobile={false} />
        <nav className="flex items-center gap-1 whitespace-nowrap">
          <Link href="/login" className={buttonClass("ghost")}>Log in</Link>
          <Link href="/register" className={buttonClass("primary")}>Create account</Link>
        </nav>
      </header>

      <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-10 lg:grid-cols-[1.05fr_1fr] lg:pt-16">
        <div className="animate-rise">
          <h1 className="font-display text-5xl font-extrabold leading-[0.98] text-balance sm:text-6xl lg:text-[4.2rem]">
            Find a roommate who sleeps when you do.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-stone-600">
            One of you studies till 2 AM, the other is up at 6. Hostel/PG Life matches people in hostels and PGs on how they really live, then keeps shared life
            simple: bills, chores, complaints and house rules.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/register" className={buttonClass("primary", "px-6 py-3 text-base")}>Find my roommate</Link>
            <Link href="/login" className={buttonClass("secondary", "px-6 py-3 text-base")}>Try the demo</Link>
          </div>
          <p className="mt-4 text-sm text-stone-500">Demo login: demo@coep.ac.in, password demo1234</p>
        </div>
        <SkyTimeline />
      </section>

      <section className="mx-auto grid max-w-6xl gap-10 px-5 py-16 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="lg:sticky lg:top-10 lg:self-start">
          <h2 className="font-display text-4xl font-bold leading-tight">The match is only the start.</h2>
          <p className="mt-4 max-w-sm text-stone-600">Most roommate fights are about money, mess and noise. The rest of the app is built for those days.</p>
        </div>
        <ul className="divide-y divide-stone-200/80">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <li key={title} className="flex gap-5 py-6 first:pt-0">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white/80 text-dusk shadow-sm ring-1 ring-stone-200/70">
                <Icon className="h-5 w-5" />
              </span>
              <div>
                <h3 className="font-display text-xl font-semibold">{title}</h3>
                <p className="mt-1.5 max-w-xl text-[15px] leading-relaxed text-stone-600">{text}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-16">
        <h2 className="font-display text-4xl font-bold">How it works</h2>
        <ol className="mt-8 grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="card">
              <span className="font-display text-5xl font-extrabold text-brand-100">{i + 1}</span>
              <h3 className="mt-2 font-display text-xl font-semibold">{s.title}</h3>
              <p className="mt-1.5 text-[15px] text-stone-600">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-20 pt-6">
        <div className="sky relative overflow-hidden rounded-[2rem] px-8 py-14 text-white sm:px-14">
          <h2 className="max-w-2xl font-display text-4xl font-bold leading-tight sm:text-5xl">Your next roommate is probably two floors away.</h2>
          <p className="mt-4 max-w-lg text-white/85">Free for students. Build your profile in a two-minute chat.</p>
          <Link href="/register" className="mt-8 inline-flex rounded-xl bg-white px-6 py-3 font-semibold text-ink transition hover:bg-white/90">Create my profile</Link>
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 pb-10 text-sm text-stone-500">
        <Logo />
        <p>Made for hostels and PGs in India.</p>
      </footer>
    </div>
  );
}
