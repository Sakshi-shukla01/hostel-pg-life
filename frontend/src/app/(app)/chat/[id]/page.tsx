"use client";

import { ArrowLeft, Send, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth";
import { Button, ErrorNote, Spinner } from "@/components/ui";
import { api, wsUrl } from "@/lib/api";
import type { Message } from "@/lib/types";

function Chat() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Message[]>(`/chat/${id}/messages`).then(setMessages).catch((e) => setError(e.message));
    const socket = new WebSocket(wsUrl(`/ws/chat/${id}`));
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.type === "message") setMessages((m) => [...m, data.message]);
      if (data.type === "error") setError(data.reason);
    };
    ws.current = socket;
    return () => socket.close();
  }, [id]);

  useEffect(() => {
    // scroll only the message list, not the whole page
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [messages]);

  function send() {
    if (!text.trim() || !ws.current || ws.current.readyState !== WebSocket.OPEN) return;
    setError(null);
    ws.current.send(JSON.stringify({ text }));
    setText("");
  }

  return (
    <div className="card flex h-[75vh] flex-col">
      <div className="mb-3 flex items-center justify-between">
        <Link href="/requests" className="flex items-center gap-1 text-sm text-stone-500"><ArrowLeft className="h-4 w-4" /> Back</Link>
        <span className={`text-xs ${connected ? "text-brand-600" : "text-stone-400"}`}>{connected ? "● Live" : "Connecting…"}</span>
      </div>
      <div ref={box} className="flex-1 space-y-2 overflow-y-auto rounded-xl bg-stone-50 p-4">
        {messages.length === 0 && <p className="text-center text-sm text-stone-400">Say hi! Talk about sleep times, food and budget before you move in.</p>}
        {messages.map((m) => {
          const mine = m.sender === user?.id;
          return (
            <div key={m.id} className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
              <p className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm ${mine ? "bg-brand-600 text-white" : "bg-white shadow-sm"}`}>{m.text}</p>
              {m.flagged && <p className="mt-1 flex items-center gap-1 text-xs text-red-600"><ShieldAlert className="h-3 w-3" /> {m.warning}</p>}
            </div>
          );
        })}
      </div>
      <ErrorNote error={error} />
      <div className="mt-3 flex gap-2">
        <input className="field" placeholder="Message…" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
        <Button onClick={send} disabled={!connected}><Send className="h-4 w-4" /></Button>
      </div>
      <p className="mt-2 text-xs text-stone-400">Messages are checked for scams (OTP, advance payment) and abuse.</p>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Chat />
    </Suspense>
  );
}
