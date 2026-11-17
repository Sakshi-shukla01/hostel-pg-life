"use client";

import { Armchair, BadgeCheck, Bike, BookOpen, Camera, Fan, Laptop, Package, Search, ShieldAlert, ShoppingBag, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth";
import { AiBadge, Badge, Button, Empty, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api, fileUrl, rupees } from "@/lib/api";
import type { Listing } from "@/lib/types";

const CATS = ["books", "electronics", "appliances", "furniture", "cycles", "other"];
const CAT_ICON = { books: BookOpen, electronics: Laptop, appliances: Fan, furniture: Armchair, cycles: Bike, other: Package };
const CAT_TINT: Record<string, string> = { books: "bg-amber-50 text-amber-600", electronics: "bg-sky-50 text-sky-600", appliances: "bg-teal-50 text-teal-600", furniture: "bg-orange-50 text-orange-600", cycles: "bg-lime-50 text-lime-700", other: "bg-stone-100 text-stone-500" };
const EMPTY = { title: "", description: "", price: "", category: "other", condition: "good", location: "" };

export default function MarketPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<Listing[] | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [selling, setSelling] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [photo, setPhoto] = useState<File | null>(null);
  const [fillSource, setFillSource] = useState<string>();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (cat) params.set("category", cat);
    return api<Listing[]>(`/market?${params}`).then(setItems);
  }, [q, cat]);
  useEffect(() => {
    load();
  }, [load]);

  async function autofill() {
    setBusy("fill");
    setError(null);
    try {
      const fd = new FormData();
      fd.append("hint", form.title);
      if (photo) fd.append("photo", photo);
      const r = await api<{ title: string; category: string; condition: string; description: string; suggested_price: number; source: string }>("/market/autofill", { form: fd });
      setForm({ ...form, title: r.title, category: r.category, condition: r.condition, description: r.description, price: String(r.suggested_price) });
      setFillSource(r.source);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function publish() {
    setBusy("post");
    setError(null);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => fd.append(k, v));
      if (photo) fd.append("photo", photo);
      const created = await api<Listing>("/market", { form: fd });
      setNotice(created.status === "under_review" ? `Your listing is under review: ${created.flag_reason}` : "Listing is live!");
      setForm(EMPTY);
      setPhoto(null);
      setSelling(false);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function interested(l: Listing) {
    const r = await api<{ seller_name: string; seller_email: string }>(`/market/${l.id}/interested`, { method: "POST" });
    setNotice(`${r.seller_name} has been told you're interested. Contact: ${r.seller_email}`);
  }

  return (
    <>
      <PageHeader title="Marketplace" subtitle="Buy and sell used stuff with students near you." action={<Button onClick={() => setSelling(!selling)}><ShoppingBag className="h-4 w-4" /> Sell something</Button>} />
      {notice && <p className="mb-4 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-700">{notice}</p>}

      {selling && (
        <div className="card mb-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">New listing</h2>
            <AiBadge source={fillSource} />
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-stone-300 px-4 py-2 text-sm text-stone-600">
              <Camera className="h-4 w-4" /> {photo ? photo.name : "Add a photo"}
              <input type="file" accept="image/*" className="hidden" onChange={(e) => setPhoto(e.target.files?.[0] || null)} />
            </label>
            <Button variant="secondary" onClick={autofill} loading={busy === "fill"} disabled={!photo && !form.title}><Sparkles className="h-4 w-4" /> Fill with AI</Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <input className="field sm:col-span-2" placeholder="Title, e.g. Air cooler" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input className="field" type="number" placeholder="Price ₹" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
            <select className="field" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATS.map((c) => <option key={c}>{c}</option>)}</select>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            <textarea className="field h-20 sm:col-span-3" placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <div className="space-y-3">
              <select className="field" value={form.condition} onChange={(e) => setForm({ ...form, condition: e.target.value })}>{["new", "like new", "good", "fair"].map((c) => <option key={c}>{c}</option>)}</select>
              <input className="field" placeholder="Pickup location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            </div>
          </div>
          <ErrorNote error={error} />
          <div className="flex justify-end"><Button onClick={publish} loading={busy === "post"} disabled={!form.title || form.price === ""}>Publish</Button></div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-stone-400" />
          <input className="field" style={{ paddingLeft: "2.25rem" }} placeholder="Search cooler, books, cycle…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="w-48"><select className="field" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">All categories</option>
          {CATS.map((c) => <option key={c}>{c}</option>)}
        </select></div>
      </div>

      {!items ? <Spinner /> : items.length === 0 ? <Empty icon={<ShoppingBag className="h-8 w-8" />} title="Nothing here yet" /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((l) => {
            const img = fileUrl(l.photo_url);
            return (
              <div key={l.id} className="card flex flex-col p-0">
                {img ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={img} alt={l.title} className="h-40 w-full rounded-t-2xl object-cover" />
                ) : (
                  (() => {
                    const Icon = CAT_ICON[l.category as keyof typeof CAT_ICON] || Package;
                    return <div className={`grid h-40 place-items-center rounded-t-2xl ${CAT_TINT[l.category] || CAT_TINT.other}`}><Icon className="h-12 w-12" strokeWidth={1.5} /></div>;
                  })()
                )}
                <div className="flex flex-1 flex-col p-4">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium">{l.title}</p>
                    <p className="font-display text-lg font-semibold text-brand-700">{rupees(l.price)}</p>
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-stone-500">{l.description}</p>
                  <div className="mt-2 flex flex-wrap gap-1"><Badge>{l.category}</Badge><Badge>{l.condition}</Badge></div>
                  <p className="mt-2 flex items-center gap-1 text-xs text-stone-500">
                    {l.seller_name} {l.seller_verified && <BadgeCheck className="h-3 w-3 text-brand-600" />}<span className="text-stone-400">in {l.location}</span>
                  </p>
                  <div className="mt-auto pt-3">
                    {l.seller === user?.id ? (
                      <Button variant="secondary" className="w-full" onClick={async () => { await api(`/market/${l.id}/sold`, { method: "POST" }); load(); }}>Mark sold</Button>
                    ) : (
                      <Button variant="secondary" className="w-full" onClick={() => interested(l)}>I&apos;m interested</Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-6 flex items-center gap-1 text-xs text-stone-400"><ShieldAlert className="h-3 w-3" /> New listings are checked by AI for scams. Never pay in advance or share an OTP.</p>
    </>
  );
}
