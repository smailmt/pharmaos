/**
 * PharmaBot — Chat conversationnel avec Claude.
 *
 * Assistant pour le pharmacien : questions cliniques (posologie, contre-indications,
 * effets indésirables), conseil patient (allaitement, grossesse, pédiatrie),
 * pharmacovigilance, DCI marocaines.
 */
import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Bot,
  Send,
  Loader2,
  User as UserIcon,
  Sparkles,
  AlertTriangle,
  Trash2,
} from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

const SUGGESTED_QUESTIONS = [
  "Posologie du paracétamol chez l'enfant de 2 ans ?",
  "Doliprane et grossesse, c'est compatible ?",
  "Quels sont les effets indésirables du Ventoline ?",
  "Quelles précautions pour la ciprofloxacine chez la femme enceinte ?",
  "Différence entre Augmentin et Clamoxyl ?",
  "Conseils pour un patient diabétique avec rhume ?",
];

export function PharmabotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll bas
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Focus initial
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const mutation = useMutation({
    mutationFn: async (message: string) => {
      // On envoie l'historique sans le timestamp (que le serveur ne connaît pas)
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const { data } = await api.post<{ reply: string }>(
        "/ai/chat",
        { message, history },
        { timeout: 30_000 }
      );
      return data.reply;
    },
    onSuccess: (reply) => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply, timestamp: Date.now() },
      ]);
    },
    onError: (err) => toast.error("Erreur PharmaBot", extractErrorMessage(err)),
  });

  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || mutation.isPending) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: trimmed, timestamp: Date.now() },
    ]);
    setInput("");
    mutation.mutate(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const clearChat = () => {
    if (messages.length === 0) return;
    if (confirm("Effacer toute la conversation ?")) setMessages([]);
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-4xl flex flex-col h-[calc(100vh-4rem)]">
      <header className="mb-4 flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Bot className="h-6 w-6 text-primary" />
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">PharmaBot</h1>
            <Badge variant="secondary" className="text-[10px]">
              <Sparkles className="h-3 w-3 mr-1" />
              IA Claude
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Assistant pour vos questions cliniques (posologie, contre-indications, conseil patient).
          </p>
        </div>
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearChat}>
            <Trash2 className="h-4 w-4 mr-1" />
            Nouvelle conversation
          </Button>
        )}
      </header>

      <Card className="flex-1 flex flex-col overflow-hidden">
        {/* Zone messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-8 max-w-xl mx-auto">
              <div className="rounded-full bg-primary/10 p-4 mb-4">
                <Bot className="h-10 w-10 text-primary" />
              </div>
              <h2 className="text-lg font-semibold mb-1">Bonjour 👋</h2>
              <p className="text-sm text-muted-foreground mb-6">
                Je suis PharmaBot, votre assistant pour les questions cliniques et le conseil patient.
                Posez-moi une question pour commencer.
              </p>
              <div className="w-full">
                <p className="text-xs text-muted-foreground mb-2 text-left">
                  Exemples de questions :
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="text-left text-sm p-2.5 rounded-md border bg-background hover:bg-accent/30 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <MessageBubble key={i} message={msg} />
              ))}
              {mutation.isPending && (
                <div className="flex items-start gap-3">
                  <div className="rounded-full bg-primary/10 p-2 shrink-0">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                  <div className="bg-muted/50 rounded-lg p-3 text-sm flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span className="text-muted-foreground">PharmaBot réfléchit…</span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer disclaimer + input */}
        <div className="border-t bg-muted/30 px-4 py-2">
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground mb-2">
            <AlertTriangle className="h-3 w-3 shrink-0" />
            <span>
              Réponses informatives — ne remplace pas un avis médical. Toujours vérifier les sources officielles (RCP, Vidal Maroc).
            </span>
          </div>
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Posez votre question… (Maj+Entrée pour aller à la ligne)"
              rows={1}
              className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[40px] max-h-32"
              disabled={mutation.isPending}
            />
            <Button
              onClick={() => send(input)}
              disabled={!input.trim() || mutation.isPending}
              className="shrink-0"
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`rounded-full p-2 shrink-0 ${
          isUser ? "bg-muted" : "bg-primary/10"
        }`}
      >
        {isUser ? (
          <UserIcon className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>
      <div
        className={`rounded-lg p-3 text-sm max-w-[85%] whitespace-pre-wrap leading-relaxed ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted/50"
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}
