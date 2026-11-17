"use client";

import { BedDouble, Camera, Check, FileSignature, RotateCw, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth";
import { AiBadge, Badge, Button, Empty, ErrorNote, PageHeader, Spinner, buttonClass } from "@/components/ui";
import { api, rupees } from "@/lib/api";
import type { Room } from "@/lib/types";

const CATS = ["rent", "electricity", "wifi", "groceries", "maid", "water", "gas", "food", "other"];

export default function RoomPage() {
  const { user } = useAuth();
  const [room, setRoom] = useState<Room | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ title: "", amount: "", category: "groceries" });
  const [scanSource, setScanSource] = useState<string>();
  const [busy, setBusy] = useState<string | null>(null);
  const [chore, setChore] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api<Room | null>("/rooms/me").then(setRoom).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
  }, [load]);

  async function run(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function scan(file: File) {
    setBusy("scan");
    setError(null);
    try {
      const fd = new FormData();
      fd.append("photo", file);
      const res = await api<{ title: string; amount: number; category: string; source: string }>("/rooms/me/scan-bill", { form: fd });
      setForm({ title: res.title, amount: String(res.amount), category: res.category });
      setScanSource(res.source);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (room === undefined) return <Spinner />;
  if (room === null)
    return <Empty icon={<BedDouble className="h-8 w-8" />} title="You're not in a room yet" text="Accept a match request, then tap “Make our room”." action={<Link href="/requests" className={buttonClass("primary")}>Go to requests</Link>} />;

  const name = (id: string) => (id === user?.id ? "You" : room.members.find((m) => m.id === id)?.name.split(" ")[0] || "?");
  const myBalance = room.balances[user?.id || ""] || 0;

  return (
    <>
      <PageHeader title={room.name} subtitle={`Shared by ${room.members.map((m) => m.name).join(" and ")}`} />
      <ErrorNote error={error} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card lg:col-span-1">
          <p className="label">Your balance</p>
          <p className={`font-display text-4xl font-semibold ${myBalance >= 0 ? "text-brand-600" : "text-red-600"}`}>
            {myBalance >= 0 ? "+" : "−"}{rupees(Math.abs(myBalance))}
          </p>
          <p className="text-sm text-stone-500">{myBalance > 0 ? "others owe you" : myBalance < 0 ? "you owe" : "all settled"}</p>
          <div className="mt-4 space-y-2">
            <p className="label">Settle up (fewest payments)</p>
            {room.payments.length === 0 && <p className="text-sm text-stone-500">Nothing to settle 🎉</p>}
            {room.payments.map((p, i) => (
              <div key={i} className="flex items-center justify-between rounded-xl bg-stone-50 px-3 py-2 text-sm">
                <span>{name(p.from_user)} → {name(p.to_user)} <b>{rupees(p.amount)}</b></span>
                {p.from_user === user?.id && (
                  <Button variant="secondary" loading={busy === `pay${i}`} onClick={() => run(`pay${i}`, () => api("/rooms/me/settle", { body: { to_user: p.to_user, amount: p.amount } }))}>Mark paid</Button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="card lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Add a shared expense</h2>
            <div className="flex items-center gap-2">
              <AiBadge source={scanSource} />
              <input ref={fileInput} type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && scan(e.target.files[0])} />
              <Button variant="secondary" loading={busy === "scan"} onClick={() => fileInput.current?.click()}><Camera className="h-4 w-4" /> Scan bill with AI</Button>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <input className="field sm:col-span-2" placeholder="What for? e.g. Electricity - Nov" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input className="field" type="number" placeholder="₹ amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            <select className="field" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</select>
          </div>
          <div className="mt-3 flex justify-end">
            <Button loading={busy === "add"} disabled={!form.title || !Number(form.amount)}
              onClick={() => run("add", async () => {
                await api("/rooms/me/expenses", { body: { title: form.title, amount: Number(form.amount), category: form.category } });
                setForm({ title: "", amount: "", category: "groceries" });
                setScanSource(undefined);
              })}>
              Add (split equally)
            </Button>
          </div>
          <div className="mt-4 divide-y divide-stone-100">
            {room.expenses.map((e) => (
              <div key={e.id} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <p className="font-medium">{e.title} <Badge>{e.category}</Badge></p>
                  <p className="text-xs text-stone-500">Paid by {name(e.paid_by)} on {new Date(e.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</p>
                </div>
                <div className="flex items-center gap-3">
                  <b>{rupees(e.amount)}</b>
                  <button onClick={() => run(`del${e.id}`, () => api(`/rooms/me/expenses/${e.id}`, { method: "DELETE" }))} className="text-stone-400 hover:text-red-600" aria-label="Delete"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="mb-3 font-semibold">Chore rotation</h2>
          <div className="space-y-2">
            {room.chores.map((c) => (
              <div key={c.id} className="flex items-center justify-between rounded-xl bg-stone-50 px-3 py-2 text-sm">
                <div>
                  <p className="font-medium">{c.task}</p>
                  <p className="text-xs text-stone-500"><b>{c.assigned_to === user?.id ? "Your" : `${name(c.assigned_to)}'s`}</b> turn, done {c.done_count} times so far</p>
                </div>
                {c.assigned_to === user?.id && (
                  <Button variant="secondary" loading={busy === c.id} onClick={() => run(c.id, () => api(`/rooms/me/chores/${c.id}/done`, { method: "POST" }))}><Check className="h-4 w-4" /> Done</Button>
                )}
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <input className="field" placeholder="New chore" value={chore} onChange={(e) => setChore(e.target.value)} />
            <Button variant="secondary" disabled={!chore} onClick={() => run("chore", async () => { await api("/rooms/me/chores", { body: { task: chore } }); setChore(""); })}><RotateCw className="h-4 w-4" /></Button>
          </div>
        </div>

        <div className="card lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Roommate agreement</h2>
            <div className="flex items-center gap-2">
              <AiBadge source={room.agreement?.source} />
              <Button variant="secondary" loading={busy === "agree"} onClick={() => run("agree", () => api("/rooms/me/agreement/generate", { method: "POST" }))}>
                <FileSignature className="h-4 w-4" /> {room.agreement ? "Regenerate" : "Write with AI"}
              </Button>
            </div>
          </div>
          {room.agreement ? (
            <>
              <pre className="whitespace-pre-wrap rounded-xl bg-stone-50 p-4 font-sans text-sm leading-relaxed">{room.agreement.text}</pre>
              <div className="mt-3 flex items-center justify-between text-sm">
                <span className="text-stone-500">Agreed by: {room.agreement.agreed_by.map(name).join(", ") || "nobody yet"}</span>
                {!room.agreement.agreed_by.includes(user?.id || "") && <Button onClick={() => run("accept", () => api("/rooms/me/agreement/accept", { method: "POST" }))}>I agree</Button>}
              </div>
            </>
          ) : (
            <p className="text-sm text-stone-500">The AI writes fair house rules from both your habits: quiet hours, guests, cleaning, AC and bills.</p>
          )}
        </div>

        <div className="card lg:col-span-3">
          <h2 className="font-semibold">Rate your roommate</h2>
          <p className="mb-3 text-sm text-stone-500">After a month together, your rating trains the learning matcher, so future matches get better for everyone.</p>
          <div className="flex flex-wrap gap-6">
            {room.members.filter((m) => m.id !== user?.id).map((m) => (
              <div key={m.id} className="flex items-center gap-3 text-sm">
                <span className="font-medium">{m.name}</span>
                {room.rated.includes(m.id) ? <Badge tone="green">Rated, thanks!</Badge> : (
                  <div className="flex">
                    {[1, 2, 3, 4, 5].map((s) => (
                      <button key={s} aria-label={`${s} stars`} onClick={() => run("rate", () => api("/rooms/me/rate", { body: { to_user: m.id, stars: s } }))}>
                        <Star className="h-5 w-5 text-amber-400 hover:fill-amber-400" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
