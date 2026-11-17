"use client";

import { Camera, Star, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ComplaintCard } from "@/components/ComplaintCard";
import { Button, Empty, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { Complaint } from "@/lib/types";

export default function ComplaintsPage() {
  const [items, setItems] = useState<Complaint[] | null>(null);
  const [form, setForm] = useState({ title: "", description: "", room_no: "" });
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<Complaint[]>("/complaints/mine").then(setItems), []);
  useEffect(() => {
    load();
  }, [load]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => fd.append(k, v));
      if (photo) fd.append("photo", photo);
      await api("/complaints", { form: fd });
      setForm({ title: "", description: "", room_no: "" });
      setPhoto(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Complaints" subtitle="AI sorts each complaint by category and urgency. Anything unresolved for 48 hours escalates." />
      <div className="card mb-6 space-y-3">
        <div className="grid gap-3 sm:grid-cols-4">
          <input className="field sm:col-span-3" placeholder="What's wrong? e.g. Bathroom tap leaking" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input className="field" placeholder="Room no." value={form.room_no} onChange={(e) => setForm({ ...form, room_no: e.target.value })} />
        </div>
        <textarea className="field h-20" placeholder="More details (optional)" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-stone-600">
            <Camera className="h-4 w-4" /> {photo ? photo.name : "Add a photo (the AI looks at it too)"}
            <input type="file" accept="image/*" className="hidden" onChange={(e) => setPhoto(e.target.files?.[0] || null)} />
          </label>
          <Button onClick={submit} loading={busy} disabled={form.title.length < 3}>Raise complaint</Button>
        </div>
        <ErrorNote error={error} />
      </div>
      {!items ? <Spinner /> : items.length === 0 ? (
        <Empty icon={<Wrench className="h-8 w-8" />} title="No complaints" text="Everything working? Great." />
      ) : (
        <div className="space-y-3">
          {items.map((c) => (
            <ComplaintCard key={c.id} c={c}>
              {c.status === "resolved" && !c.rating && (
                <div className="flex items-center gap-1 text-sm text-stone-500">
                  Rate the fix:
                  {[1, 2, 3, 4, 5].map((s) => (
                    <button key={s} onClick={async () => { await api(`/complaints/${c.id}/rate`, { body: { stars: s } }); load(); }} aria-label={`${s} stars`}>
                      <Star className="h-4 w-4 text-amber-400 hover:fill-amber-400" />
                    </button>
                  ))}
                </div>
              )}
            </ComplaintCard>
          ))}
        </div>
      )}
    </>
  );
}
