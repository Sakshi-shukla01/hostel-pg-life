"use client";

import { Brain, FileUp } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ComplaintCard } from "@/components/ComplaintCard";
import { Badge, Button, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { Complaint } from "@/lib/types";

type Stats = { total: number; open: number; escalated: number; by_category: Record<string, number>; avg_resolution_hours: number | null; avg_rating: number | null };
type MlStatus = { weights_source: string; weights: Record<string, number>; ratings: number; ai_mode: string; latest_model: { n_ratings: number; learned_auc: number; default_auc: number; active: boolean; trained_at: string } | null };

export default function WardenPage() {
  const [items, setItems] = useState<Complaint[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [ml, setMl] = useState<MlStatus | null>(null);
  const [filter, setFilter] = useState("");
  const [rules, setRules] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [docs, setDocs] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      Promise.all([
        api<Complaint[]>(`/complaints${filter ? `?status=${filter}` : ""}`),
        api<Stats>("/complaints/stats"),
        api<MlStatus>("/ml/status"),
        api<{ docs: string[] }>("/rules/docs"),
      ])
        .then(([c, s, m, d]) => {
          setItems(c);
          setStats(s);
          setMl(m);
          setDocs(d.docs);
        })
        .catch((e: Error) => setError(e.message)),
    [filter],
  );
  useEffect(() => {
    load();
  }, [load]);

  async function update(id: string, status: string) {
    const note = status === "resolved" ? window.prompt("Add a note for the student (optional)") || "" : "";
    await api(`/complaints/${id}`, { method: "PATCH", body: { status, note } });
    load();
  }
  async function upload() {
    setBusy("rules");
    try {
      const fd = new FormData();
      if (file) fd.append("file", file);
      else fd.append("text", rules);
      const r = await api<{ chunks: number }>("/rules/upload", { form: fd });
      setMsg(`Rulebook indexed into ${r.chunks} searchable chunks.`);
      setRules("");
      setFile(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  async function train() {
    setBusy("train");
    try {
      const r = await api<{ trained: boolean; message?: string; learned_auc?: number; default_auc?: number; active?: boolean }>("/ml/train", { method: "POST" });
      setMsg(r.trained ? `Model trained. AUC learned ${r.learned_auc} vs default ${r.default_auc}. ${r.active ? "Now live for matching." : "Kept default weights (not better)."}` : r.message || "");
      load();
    } finally {
      setBusy(null);
    }
  }

  if (!stats || !ml) return error ? <ErrorNote error={error} /> : <Spinner />;
  const tiles = [
    ["Open", stats.open], ["Escalated", stats.escalated], ["Avg fix time", stats.avg_resolution_hours != null ? `${stats.avg_resolution_hours} h` : "—"], ["Avg rating", stats.avg_rating ?? "—"],
  ];
  const maxCat = Math.max(1, ...Object.values(stats.by_category));

  return (
    <>
      <PageHeader title="Warden dashboard" subtitle={`AI mode: ${ml.ai_mode === "gemini" ? "Gemini" : "offline fallback"}`} />
      {msg && <p className="mb-4 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-700">{msg}</p>}
      <ErrorNote error={error} />

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {tiles.map(([label, value]) => (
          <div key={label} className="card">
            <p className="label">{label}</p>
            <p className={`font-display text-3xl font-semibold ${label === "Escalated" && Number(value) > 0 ? "text-red-600" : ""}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <div className="card">
          <h2 className="mb-3 font-semibold">Complaints by category</h2>
          <div className="space-y-2">
            {Object.entries(stats.by_category).map(([cat, n]) => (
              <div key={cat} className="text-sm">
                <div className="flex justify-between"><span>{cat}</span><span className="text-stone-500">{n}</span></div>
                <div className="h-2 rounded-full bg-stone-100"><div className="h-2 rounded-full bg-brand-500" style={{ width: `${(n / maxCat) * 100}%` }} /></div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="mb-1 flex items-center gap-2 font-semibold"><FileUp className="h-4 w-4" /> Rulebook for the rules bot</h2>
          <p className="mb-3 text-xs text-stone-500">Indexed: {docs.join(", ") || "none yet"}</p>
          <input type="file" accept=".pdf,.txt" className="mb-2 text-sm" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <textarea className="field h-20" placeholder="…or paste the rules here" value={rules} onChange={(e) => setRules(e.target.value)} />
          <Button className="mt-2 w-full" variant="secondary" onClick={upload} loading={busy === "rules"} disabled={!file && rules.length < 30}>Upload and index</Button>
        </div>

        <div className="card">
          <h2 className="mb-1 flex items-center gap-2 font-semibold"><Brain className="h-4 w-4" /> Learning matcher</h2>
          <p className="text-xs text-stone-500">Trained on {ml.ratings} roommate ratings. Weights in use: <Badge tone={ml.weights_source === "learned" ? "green" : "stone"}>{ml.weights_source}</Badge></p>
          {ml.latest_model && <p className="mt-2 text-sm">Last model: AUC <b>{ml.latest_model.learned_auc}</b> vs default <b>{ml.latest_model.default_auc}</b> on {ml.latest_model.n_ratings} ratings</p>}
          <div className="mt-3 space-y-1">
            {Object.entries(ml.weights).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([k, w]) => (
              <div key={k} className="flex items-center gap-2 text-xs">
                <span className="w-24 truncate">{k.replace("_", " ")}</span>
                <div className="h-1.5 flex-1 rounded-full bg-stone-100"><div className="h-1.5 rounded-full bg-spark" style={{ width: `${Math.min(100, w * 2.5)}%` }} /></div>
                <span className="w-8 text-right text-stone-500">{w.toFixed(0)}</span>
              </div>
            ))}
          </div>
          <Button className="mt-3 w-full" variant="secondary" onClick={train} loading={busy === "train"}>Retrain from ratings</Button>
        </div>
      </div>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Complaints queue</h2>
        <div className="w-44"><select className="field" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option>
        </select></div>
      </div>
      <div className="space-y-3">
        {items?.map((c) => (
          <ComplaintCard key={c.id} c={c}>
            {c.status !== "resolved" && (
              <div className="flex gap-2">
                {c.status === "open" && <Button variant="secondary" onClick={() => update(c.id, "in_progress")}>Start work</Button>}
                <Button onClick={() => update(c.id, "resolved")}>Mark resolved</Button>
              </div>
            )}
          </ComplaintCard>
        ))}
      </div>
    </>
  );
}
