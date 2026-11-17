"use client";

import { Bot, BookOpen, Send, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { AiBadge, Button, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

type Msg = { role: "user" | "assistant"; text: string; source?: string; steps?: { tool: string; args: Record<string, unknown> }[]; sources?: { text: string }[] };

const SUGGESTIONS = [
  "Find me a veg non-smoker roommate under ₹9000",
  "Who owes money in my room?",
  "Any cooler under ₹2500?",
  "What time does the gate close?",
  "What's the status of my complaints?",
];

export default function AssistantPage() {
  const [mode, setMode] = useState<"agent" | "rules">("agent");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // scroll only the message list, not the whole page
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [msgs]);

  async function ask(q: string) {
    if (!q.trim()) return;
    const history = msgs.map((m) => ({ role: m.role, text: m.text }));
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setText("");
    setBusy(true);
    try {
      if (mode === "agent") {
        const r = await api<{ answer: string; steps: Msg["steps"]; source: string }>("/assistant", { body: { question: q, history } });
        setMsgs((m) => [...m, { role: "assistant", text: r.answer, steps: r.steps, source: r.source }]);
      } else {
        const r = await api<{ answer: string; sources: { text: string }[]; source: string }>("/rules/ask", { body: { question: q } });
        setMsgs((m) => [...m, { role: "assistant", text: r.answer, sources: r.sources, source: r.source }]);
      }
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: (e as Error).message }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="AI assistant"
        subtitle={mode === "agent" ? "An agent that calls the app's own tools: roommate search, balances, complaints, marketplace, rules." : "Answers only from your hostel's uploaded rulebook (RAG), with sources."}
        action={
          <div className="flex rounded-xl border border-stone-300 bg-white p-1 text-sm">
            <button onClick={() => setMode("agent")} className={`flex items-center gap-1 rounded-lg px-3 py-1 ${mode === "agent" ? "bg-brand-600 text-white" : ""}`}><Bot className="h-4 w-4" /> Assistant</button>
            <button onClick={() => setMode("rules")} className={`flex items-center gap-1 rounded-lg px-3 py-1 ${mode === "rules" ? "bg-brand-600 text-white" : ""}`}><BookOpen className="h-4 w-4" /> Rules bot</button>
          </div>
        }
      />
      <div className="card flex h-[65vh] flex-col">
        <div ref={box} className="flex-1 space-y-4 overflow-y-auto">
          {msgs.length === 0 && (
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => <button key={s} onClick={() => ask(s)} className="rounded-full border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-50">{s}</button>)}
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}>
              <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${m.role === "user" ? "bg-brand-600 text-white" : "bg-stone-50"}`}>{m.text}</div>
              {m.role === "assistant" && (
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-stone-400">
                  <AiBadge source={m.source} />
                  {m.steps?.map((s, j) => <span key={j} className="flex items-center gap-1"><Wrench className="h-3 w-3" /> {s.tool}({Object.entries(s.args).map(([k, v]) => `${k}=${v}`).join(", ")})</span>)}
                  {m.sources?.length ? <details><summary className="cursor-pointer">{m.sources.length} rulebook excerpts</summary>{m.sources.map((s, j) => <p key={j} className="mt-1 max-w-xl rounded bg-stone-50 p-2 text-stone-600">[{j + 1}] {s.text}</p>)}</details> : null}
                </div>
              )}
            </div>
          ))}
          {busy && <p className="text-sm text-stone-400">Thinking…</p>}
        </div>
        <div className="mt-3 flex gap-2">
          <input className="field" placeholder={mode === "agent" ? "Ask anything about roommates, money, complaints, listings…" : "Ask about gate timings, visitors, rent, rules…"} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask(text)} />
          <Button onClick={() => ask(text)} disabled={busy}><Send className="h-4 w-4" /></Button>
        </div>
      </div>
    </>
  );
}
