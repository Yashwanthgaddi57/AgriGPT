"use client";

import * as React from "react";
import { Bot, Mic, MicOff, Send, Trash2, User, Volume2, VolumeX, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Markdown } from "@/components/chat/Markdown";
import {
  useChatMessages,
  useChatSessions,
  useDeleteChatSession,
  useSendMessage,
  sendMessageStream,
} from "@/hooks/use-api";
import { trackEvent, EVENTS } from "@/lib/events";
import { apiErrorMessage } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import type { ChatMessage } from "@/types";
import { cn, formatDate } from "@/lib/utils";
import { useLang } from "@/lib/i18n";

const SUGGESTIONS = [
  "🌱 What should I do today?",
  "🌧️ Will rain affect my crop?",
  "💰 Should I sell now?",
  "🐛 What is wrong with my plant?",
  "💧 When should I irrigate?",
  "🌾 What crop should I grow this season?",
];

const AGENT_LABELS: Record<string, string> = {
  crop_recommendation: "Crop Agent",
  disease_detection: "Disease Agent",
  weather: "Weather Agent",
  market: "Market Agent",
  profit_optimization: "Profit Agent",
  general_advice: "Farm Advisor",
  crop: "Crop Agent",
  profit: "Profit Agent",
  advisor: "Farm Advisor",
};

/* Minimal typings for the Web Speech API (not in TS DOM lib by default). */
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: unknown) => void) | null;
  start: () => void;
  stop: () => void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognition(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition || w.webkitSpeechRecognition) as SpeechRecognitionCtor | null;
}

const SPEECH_LOCALES: Record<string, string> = {
  en: "en-IN",
  hi: "hi-IN",
  te: "te-IN",
  ta: "ta-IN",
  kn: "kn-IN",
  mr: "mr-IN",
};

export default function CopilotPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { data: sessions } = useChatSessions();
  const [sessionId, setSessionId] = React.useState<string | null>(null);
  const { data: messages } = useChatMessages(sessionId);
  const send = useSendMessage();
  const deleteSession = useDeleteChatSession();
  const [input, setInput] = React.useState("");
  const bottomRef = React.useRef<HTMLDivElement>(null);
  const { lang } = useLang();

  // Voice input
  const [listening, setListening] = React.useState(false);
  const recognitionRef = React.useRef<SpeechRecognitionLike | null>(null);
  const speechSupported = React.useMemo(() => Boolean(getSpeechRecognition()), []);

  // Text-to-speech
  const [ttsEnabled, setTtsEnabled] = React.useState(false);

  // Optimistic display: server messages + pending user message + streaming answer
  const [pending, setPending] = React.useState<ChatMessage[]>([]);
  const [streamText, setStreamText] = React.useState("");
  const [streamAgent, setStreamAgent] = React.useState<string | null>(null);
  const [isStreaming, setIsStreaming] = React.useState(false);
  const [sendError, setSendError] = React.useState<string | null>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending, streamText]);

  const speak = React.useCallback(
    (text: string) => {
      if (!ttsEnabled || typeof window === "undefined" || !window.speechSynthesis) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(
        // Strip markdown symbols for cleaner speech.
        text.replace(/[*_#`>|]/g, "").slice(0, 1200)
      );
      utterance.lang = SPEECH_LOCALES[lang] ?? "en-IN";
      window.speechSynthesis.speak(utterance);
      trackEvent(EVENTS.ttsUsed);
    },
    [ttsEnabled, lang]
  );

  const toggleListening = () => {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const Ctor = getSpeechRecognition();
    if (!Ctor) {
      return;
    }
    const recognition = new Ctor();
    recognition.lang = SPEECH_LOCALES[lang] ?? "en-IN";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (e) => {
      const transcript = e.results?.[0]?.[0]?.transcript ?? "";
      if (transcript) {
        setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
        trackEvent(EVENTS.voiceInputUsed);
      }
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  };

  const doSend = async (text: string) => {
    const content = text.trim();
    if (!content || send.isPending || isStreaming) return;
    setInput("");
    const optimistic: ChatMessage = {
      id: `tmp-${Date.now()}`,
      role: "user",
      content,
      agent: null,
      created_at: new Date().toISOString(),
    };
    setPending([optimistic]);
    setStreamText("");
    setStreamAgent(null);
    setIsStreaming(true);
    setSendError(null);

    let liveSessionId = sessionId;
    let finalText = "";
    let streamFailure: string | null = null;
    try {
      await sendMessageStream(
        { content, session_id: sessionId, language: lang },
        (e) => {
          if (e.type === "meta" && e.session_id) {
            liveSessionId = e.session_id;
            if (!sessionId) setSessionId(e.session_id);
          } else if (e.type === "agent" && e.agent) {
            setStreamAgent(e.agent);
          } else if (e.type === "delta" && e.text) {
            finalText += e.text;
            setStreamText((prev) => prev + e.text);
          } else if (e.type === "error") {
            // The service degrades to an SSE error event rather than throwing.
            streamFailure = e.message || "The copilot hit an error. Please try again.";
          } else if (e.type === "done") {
            if (!liveSessionId && e.session_id) setSessionId(e.session_id);
          }
        }
      );
      if (streamFailure) throw new Error(streamFailure);
      speak(finalText);
    } catch (e) {
      // Never fail silently: a swallowed error (e.g. the 429 daily-quota
      // response) makes the copilot look broken with zero feedback.
      const message = apiErrorMessage(e);
      setSendError(message);
      toast({ title: "Copilot couldn't answer", description: message, variant: "destructive" });
    } finally {
      // The answer lives only in `streamText` until the server's message list
      // contains it. Refetch before clearing, or the reply vanishes the moment
      // the stream ends.
      if (liveSessionId) {
        await queryClient.invalidateQueries({ queryKey: ["chat"] });
      }
      setPending([]);
      setStreamText("");
      setStreamAgent(null);
      setIsStreaming(false);
    }
  };

  const serverMessages = messages ?? [];
  // Hide the optimistic bubble once the server returns that same message — the
  // new session's first fetch otherwise renders the question twice.
  const pendingToShow = pending.filter(
    (p) => !serverMessages.some((m) => m.role === p.role && m.content === p.content)
  );
  const all: ChatMessage[] = [...serverMessages, ...pendingToShow];
  const showThinking = (send.isPending || isStreaming) && !streamText;

  return (
    <div className="flex h-[calc(100vh-12rem)] flex-col space-y-3 sm:h-[calc(100vh-8rem)] lg:flex-row lg:space-x-4 lg:space-y-0">
      {/* Sessions sidebar: collapsible on mobile (select), fixed on desktop */}
      <div className="hidden w-64 shrink-0 flex-col rounded-xl border bg-card lg:flex">
        <div className="border-b p-3">
          <Button className="w-full" onClick={() => setSessionId(null)}>
            New conversation
          </Button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {(sessions ?? []).map((s) => (
            <div
              key={s.id}
              className={cn(
                "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-accent",
                sessionId === s.id && "bg-accent"
              )}
            >
              <button className="min-w-0 flex-1 truncate text-left" onClick={() => setSessionId(s.id)}>
                {s.title}
              </button>
              <button
                className="opacity-0 transition-opacity hover:text-red-600 group-hover:opacity-100"
                onClick={() => {
                  if (sessionId === s.id) setSessionId(null);
                  deleteSession.mutate(s.id);
                }}
                aria-label="Delete conversation"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Mobile session switcher */}
      <div className="lg:hidden">
        <select
          value={sessionId ?? ""}
          onChange={(e) => setSessionId(e.target.value || null)}
          className="h-9 w-full rounded-md border border-input bg-card px-3 text-sm"
          aria-label="Conversation"
        >
          <option value="">+ New conversation</option>
          {(sessions ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </div>

      {/* Chat pane */}
      <Card className="flex min-h-0 w-full min-w-0 flex-1 flex-col">
        <CardContent className="flex min-h-0 flex-1 flex-col p-0">
          {/* Toolbar */}
          <div className="flex items-center justify-between border-b px-4 py-2">
            <span className="text-xs text-muted-foreground">
              Replies in your selected language ({lang.toUpperCase()})
            </span>
            <button
              onClick={() => setTtsEnabled((v) => !v)}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                ttsEnabled ? "border border-leaf-500 bg-leaf-50 text-leaf-700" : "text-muted-foreground"
              )}
              aria-pressed={ttsEnabled}
            >
              {ttsEnabled ? <Volume2 className="h-3.5 w-3.5" /> : <VolumeX className="h-3.5 w-3.5" />}
              {ttsEnabled ? "Voice replies on" : "Voice replies off"}
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {all.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
                <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-leaf-600 text-white">
                  <Bot className="h-7 w-7" />
                </span>
                <div>
                  <h3 className="font-medium">Your AI Farm Copilot</h3>
                  <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
                    {speechSupported
                      ? "Ask by text or 🎤 voice — it knows your farm profile, recent scans and market views."
                      : "🎤 Voice input isn't supported in this browser — type your question instead. It knows your farm profile, recent scans and market views."}
                  </p>
                </div>
                <div className="grid w-full max-w-lg gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => doSend(s)}
                      className="min-h-[44px] rounded-lg border p-3 text-left text-sm transition-colors hover:border-leaf-400 hover:bg-leaf-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">{formatDate(new Date())}</p>
              </div>
            )}

            {all.map((m) => (
              <div key={m.id} className={cn("flex gap-3", m.role === "user" ? "justify-end" : "justify-start")}>
                {m.role !== "user" && (
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-leaf-600 text-white">
                    <Bot className="h-4 w-4" />
                  </span>
                )}
                <div
                  className={cn(
                    "max-w-[88%] rounded-2xl px-3.5 py-2.5 sm:max-w-[85%]",
                    m.role === "user"
                      ? "bg-leaf-600 text-white"
                      : "border bg-card"
                  )}
                >
                  {m.agent && m.role === "assistant" && (
                    <Badge variant="secondary" className="mb-1.5 text-[10px]">
                      {AGENT_LABELS[m.agent] ?? m.agent}
                    </Badge>
                  )}
                  {m.role === "user" ? (
                    <div className="whitespace-pre-wrap text-sm leading-relaxed">{m.content}</div>
                  ) : (
                    <>
                      <Markdown>{m.content}</Markdown>
                      {ttsEnabled && (
                        <button
                          onClick={() => speak(m.content)}
                          className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
                          aria-label="Read answer aloud"
                        >
                          <Volume2 className="h-3 w-3" /> Listen
                        </button>
                      )}
                    </>
                  )}
                </div>
                {m.role === "user" && (
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
                    <User className="h-4 w-4" />
                  </span>
                )}
              </div>
            ))}

            {showThinking && (
              <div className="flex gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-leaf-600 text-white">
                  <Bot className="h-4 w-4" />
                </span>
                <div className="flex items-center gap-2 rounded-2xl border bg-card px-4 py-3 text-sm text-muted-foreground">
                  <div className="thinking-dots flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-leaf-500" />
                    <span className="h-1.5 w-1.5 rounded-full bg-leaf-500" />
                    <span className="h-1.5 w-1.5 rounded-full bg-leaf-500" />
                  </div>
                  AgriGPT is thinking…
                </div>
              </div>
            )}

            {streamText && (
              <div className="flex gap-3 justify-start">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-leaf-600 text-white">
                  <Bot className="h-4 w-4" />
                </span>
                <div className="max-w-[85%] rounded-2xl border bg-card px-4 py-2.5">
                  {streamAgent && (
                    <Badge variant="secondary" className="mb-1.5 text-[10px]">
                      {AGENT_LABELS[streamAgent] ?? streamAgent}
                    </Badge>
                  )}
                  <Markdown>{streamText}</Markdown>
                  <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-leaf-500 align-middle" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t p-3">
            {sendError && (
              <div className="mb-2 flex items-start justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                <span>{sendError}</span>
                <button
                  type="button"
                  onClick={() => setSendError(null)}
                  aria-label="Dismiss error"
                  className="shrink-0 opacity-70 transition-opacity hover:opacity-100"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                doSend(input);
              }}
              className="flex items-end gap-2"
            >
              {speechSupported && (
                <Button
                  type="button"
                  size="icon"
                  variant={listening ? "default" : "outline"}
                  onClick={toggleListening}
                  aria-label={listening ? "Stop listening" : "Ask by voice"}
                  title={listening ? "Stop listening" : "Ask by voice"}
                  className={cn(
                    "h-12 w-12 shrink-0 md:h-11 md:w-11 tap-subtle",
                    listening && "voice-active"
                  )}
                >
                  {listening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                </Button>
              )}
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={listening ? "Listening… speak now" : "Ask about crops, disease, prices, weather…"}
                rows={1}
                className="max-h-32 min-h-[44px] resize-none"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    doSend(input);
                  }
                }}
              />
              <Button
                type="submit"
                size="icon"
                disabled={send.isPending || isStreaming || !input.trim()}
                className="h-12 w-12 shrink-0 md:h-11 md:w-11"
                aria-label="Send question"
              >
                <Send className="h-5 w-5" />
              </Button>
            </form>
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              AI answers are decision support — verify high-stakes decisions with local experts.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
