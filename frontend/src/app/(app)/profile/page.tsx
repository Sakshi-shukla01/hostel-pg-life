"use client";

import { Bot, ListChecks, Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth";
import { AiBadge, Button, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { Answers, Profile } from "@/lib/types";

const DEFAULT_ANSWERS: Answers = {
  sleep_time: "23:30", wake_time: "07:30", study_style: "silent", cleanliness: 3, food: "veg", smoking: false,
  drinking: false, guests: 1, noise: 3, ac: "either", personality: "ambivert",
};
const DEFAULT: Profile = {
  city: "Pune", area: "", gender: "female", gender_pref: "same", budget_min: 6000, budget_max: 9000, move_in: null,
  room_type: "2-sharing", college_or_office: "", bio: "", interests: [], answers: DEFAULT_ANSWERS, dealbreakers: [],
};
const DEALBREAKERS = [
  ["smoking", "Smoking"], ["drinking", "Drinking"], ["food", "Food habits"], ["sleep_time", "Sleep time"], ["guests", "Guests"], ["cleanliness", "Cleanliness"],
] as const;

type ChatMsg = { role: "user" | "assistant"; text: string };
type Turn = { reply: string; profile: Partial<Answers> & { bio?: string }; done: boolean; source: string };

export default function ProfilePage() {
  const router = useRouter();
  const { user, refresh } = useAuth();
  const [hostel, setHostel] = useState(user?.hostel || "default");
  const [p, setP] = useState<Profile>(DEFAULT);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"chat" | "form">("chat");
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const [collected, setCollected] = useState<Turn["profile"]>({});
  const [input, setInput] = useState("");
  const [source, setSource] = useState<string>();
  const [thinking, setThinking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Profile | null>("/profile/me")
      .then((existing) => {
        if (existing) {
          setP({ ...DEFAULT, ...existing, answers: { ...DEFAULT_ANSWERS, ...existing.answers } });
          setMode("form");
        } else {
          turn([]); // new user: the AI starts the conversation
        }
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // scroll only the message list, not the whole page
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [chat]);

  async function turn(history: ChatMsg[]) {
    setThinking(true);
    try {
      const res = await api<Turn>("/ai/onboarding", { body: { history, profile: collected } });
      setCollected(res.profile);
      setSource(res.source);
      setChat([...history, { role: "assistant", text: res.reply }]);
      const { bio, ...answers } = res.profile;
      setP((prev) => ({ ...prev, bio: bio ?? prev.bio, answers: { ...prev.answers, ...answers } }));
      if (res.done) setMode("form");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setThinking(false);
    }
  }

  function send() {
    if (!input.trim()) return;
    const next = [...chat, { role: "user" as const, text: input.trim() }];
    setChat(next);
    setInput("");
    turn(next);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      if (hostel.trim() && hostel.trim().toLowerCase() !== user?.hostel) {
        await api("/auth/me", { method: "PATCH", body: { hostel } });
        await refresh();
      }
      await api("/profile", { method: "PUT", body: { ...p, move_in: p.move_in || null } });
      router.push("/matches");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const setA = <K extends keyof Answers>(k: K, v: Answers[K]) => setP({ ...p, answers: { ...p.answers, [k]: v } });
  if (loading) return <Spinner />;

  return (
    <>
      <PageHeader
        title="Your roommate profile"
        subtitle="Chat with the AI or fill the form. Both build the same profile."
        action={
          <div className="flex rounded-xl border border-stone-300 bg-white p-1 text-sm">
            <button onClick={() => { setMode("chat"); if (chat.length === 0) turn([]); }} className={`flex items-center gap-1 rounded-lg px-3 py-1 ${mode === "chat" ? "bg-brand-600 text-white" : ""}`}><Bot className="h-4 w-4" /> AI chat</button>
            <button onClick={() => setMode("form")} className={`flex items-center gap-1 rounded-lg px-3 py-1 ${mode === "form" ? "bg-brand-600 text-white" : ""}`}><ListChecks className="h-4 w-4" /> Form</button>
          </div>
        }
      />

      {mode === "chat" && (
        <div className="card mb-6">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-medium">Onboarding chat</p>
            <AiBadge source={source} />
          </div>
          <div ref={box} className="h-80 space-y-3 overflow-y-auto rounded-xl bg-stone-50 p-4">
            {chat.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : ""}`}>
                <p className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${m.role === "user" ? "bg-brand-600 text-white" : "bg-white shadow-sm"}`}>{m.text}</p>
              </div>
            ))}
            {thinking && <p className="text-sm text-stone-400">Typing…</p>}
          </div>
          <div className="mt-3 flex gap-2">
            <input className="field" placeholder="Type your answer…" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
            <Button onClick={send} disabled={thinking}><Send className="h-4 w-4" /></Button>
          </div>
          <p className="mt-2 text-xs text-stone-500">{Object.keys(collected).length} of 12 answers collected. Your answers also appear in the form.</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card space-y-4">
          <h2 className="font-semibold">Where and when</h2>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">City</label><input className="field" value={p.city} onChange={(e) => setP({ ...p, city: e.target.value })} /></div>
            <div><label className="label">Area</label><input className="field" placeholder="e.g. Kothrud" value={p.area} onChange={(e) => setP({ ...p, area: e.target.value })} /></div>
            <div><label className="label">Budget min (₹/month)</label><input className="field" type="number" value={p.budget_min} onChange={(e) => setP({ ...p, budget_min: Number(e.target.value) })} /></div>
            <div><label className="label">Budget max</label><input className="field" type="number" value={p.budget_max} onChange={(e) => setP({ ...p, budget_max: Number(e.target.value) })} /></div>
            <div><label className="label">I am</label>
              <select className="field" value={p.gender} onChange={(e) => setP({ ...p, gender: e.target.value as Profile["gender"] })}><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></select></div>
            <div><label className="label">Roommate gender</label>
              <select className="field" value={p.gender_pref} onChange={(e) => setP({ ...p, gender_pref: e.target.value as Profile["gender_pref"] })}><option value="same">Same as me</option><option value="any">Any</option></select></div>
            <div><label className="label">Move-in date</label><input className="field" type="date" value={p.move_in || ""} onChange={(e) => setP({ ...p, move_in: e.target.value })} /></div>
            <div><label className="label">Room type</label>
              <select className="field" value={p.room_type} onChange={(e) => setP({ ...p, room_type: e.target.value as Profile["room_type"] })}><option>2-sharing</option><option>3-sharing</option><option value="flat">Flat</option></select></div>
          </div>
          <div><label className="label">Hostel or PG code</label><input className="field" value={hostel} onChange={(e) => setHostel(e.target.value)} />
            <p className="mt-1.5 text-xs text-stone-500">Links you to your hostel&apos;s warden, complaints and rulebook.</p></div>
          <div><label className="label">College / office</label><input className="field" value={p.college_or_office} onChange={(e) => setP({ ...p, college_or_office: e.target.value })} /></div>
          <div><label className="label">About you (used for personality matching)</label>
            <textarea className="field h-24" value={p.bio} placeholder="Final year CSE, love cricket and coding, quiet person…" onChange={(e) => setP({ ...p, bio: e.target.value })} /></div>
          <div><label className="label">Interests (comma separated)</label>
            <input className="field" value={p.interests.join(", ")} onChange={(e) => setP({ ...p, interests: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} /></div>
        </div>

        <div className="card space-y-4">
          <h2 className="font-semibold">Daily habits</h2>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Sleep time</label><input className="field" type="time" value={p.answers.sleep_time} onChange={(e) => setA("sleep_time", e.target.value)} /></div>
            <div><label className="label">Wake time</label><input className="field" type="time" value={p.answers.wake_time} onChange={(e) => setA("wake_time", e.target.value)} /></div>
            <div><label className="label">Study style</label>
              <select className="field" value={p.answers.study_style} onChange={(e) => setA("study_style", e.target.value as Answers["study_style"])}><option value="silent">Silent</option><option value="music">With music</option><option value="library">Library</option></select></div>
            <div><label className="label">Food</label>
              <select className="field" value={p.answers.food} onChange={(e) => setA("food", e.target.value as Answers["food"])}><option value="veg">Veg</option><option value="nonveg">Non-veg</option><option value="eggetarian">Eggetarian</option><option value="flexible">Flexible</option></select></div>
            <div><label className="label">AC / fan</label>
              <select className="field" value={p.answers.ac} onChange={(e) => setA("ac", e.target.value as Answers["ac"])}><option value="ac">AC</option><option value="fan">Fan</option><option value="either">Either</option></select></div>
            <div><label className="label">Personality</label>
              <select className="field" value={p.answers.personality} onChange={(e) => setA("personality", e.target.value as Answers["personality"])}><option value="introvert">Introvert</option><option value="ambivert">In between</option><option value="extrovert">Extrovert</option></select></div>
          </div>
          {([["cleanliness", "Cleanliness (1 messy – 5 very neat)", 1, 5], ["noise", "Noise: calls, music (1 quiet – 5 loud)", 1, 5], ["guests", "Guests (0 never – 3 often)", 0, 3]] as const).map(([k, label, min, max]) => (
            <div key={k}>
              <label className="label">{label}: {p.answers[k]}</label>
              <input type="range" min={min} max={max} className="w-full accent-brand-600" value={p.answers[k]} onChange={(e) => setA(k, Number(e.target.value))} />
            </div>
          ))}
          <div className="flex gap-6 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={p.answers.smoking} onChange={(e) => setA("smoking", e.target.checked)} /> I smoke</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={p.answers.drinking} onChange={(e) => setA("drinking", e.target.checked)} /> I drink</label>
          </div>
          <div>
            <label className="label">Dealbreakers: must match exactly (max 3)</label>
            <div className="flex flex-wrap gap-2">
              {DEALBREAKERS.map(([k, label]) => {
                const on = p.dealbreakers.includes(k);
                return (
                  <button key={k} type="button"
                    onClick={() => setP({ ...p, dealbreakers: on ? p.dealbreakers.filter((x) => x !== k) : p.dealbreakers.length < 3 ? [...p.dealbreakers, k] : p.dealbreakers })}
                    className={`rounded-full border px-3 py-1 text-xs ${on ? "border-red-300 bg-red-50 text-red-700" : "border-stone-300"}`}>{label}</button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      <div className="mt-6 flex items-center justify-end gap-3">
        <ErrorNote error={error} />
        <Button onClick={save} loading={saving}>Save and see my matches</Button>
      </div>
    </>
  );
}
