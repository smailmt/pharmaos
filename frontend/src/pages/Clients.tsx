import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Wallet, AlertTriangle, Loader2, MessageSquare, Phone, Mail, Send } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";
import type { Client, ClientDetail, ThirdPartyPayer } from "@/types/api";

export function ClientsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [showOverdueOnly, setShowOverdueOnly] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: clients, isLoading } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<Client[]>("/clients").then((r) => r.data),
  });

  const { data: payers } = useQuery({
    queryKey: ["payers"],
    queryFn: () => api.get<ThirdPartyPayer[]>("/third-party/payers").then((r) => r.data),
  });

  const filtered = useMemo(() => {
    if (!clients) return [];
    let list = clients;
    if (showOverdueOnly) {
      list = list.filter((c) => c.risk_score >= 30);
    }
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (c) =>
          c.full_name.toLowerCase().includes(q) ||
          (c.phone && c.phone.includes(q)) ||
          (c.cin && c.cin.toLowerCase().includes(q))
      );
    }
    return list;
  }, [clients, search, showOverdueOnly]);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Clients</h1>
          <p className="text-sm text-muted-foreground">
            {clients?.length ?? 0} clients ·{" "}
            {clients?.filter((c) => c.credit_enabled).length ?? 0} avec crédit
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Nouveau client
        </Button>
      </header>

      <div className="flex gap-2 flex-wrap">
        <Button
          variant={showOverdueOnly ? "default" : "outline"}
          size="sm"
          onClick={() => setShowOverdueOnly((v) => !v)}
          className="gap-1.5"
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          À risque
        </Button>
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Nom, téléphone, CIN..."
            className="pl-10"
          />
        </div>
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom</TableHead>
              <TableHead>Téléphone</TableHead>
              <TableHead>CIN</TableHead>
              <TableHead>Tiers payant</TableHead>
              <TableHead className="text-right">Plafond crédit</TableHead>
              <TableHead className="text-right">Risque</TableHead>
              <TableHead className="text-right">Fidélité</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin mx-auto" />
                </TableCell>
              </TableRow>
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                  Aucun client
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((c) => {
                const payer = payers?.find((p) => p.id === c.third_party_payer_id);
                return (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => setSelectedId(c.id)}
                  >
                    <TableCell className="font-medium">{c.full_name}</TableCell>
                    <TableCell className="text-sm">{c.phone ?? "—"}</TableCell>
                    <TableCell className="text-sm font-mono">{c.cin ?? "—"}</TableCell>
                    <TableCell>
                      {payer ? <Badge variant="outline">{payer.code}</Badge> : "—"}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {c.credit_enabled ? formatMAD(c.credit_limit) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant={c.risk_score >= 50 ? "destructive" : c.risk_score >= 30 ? "warning" : "secondary"}>
                        {c.risk_score}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right text-sm">{c.loyalty_points} pts</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="ghost">Détail</Button>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Card>

      <CreateClientDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        payers={payers ?? []}
        onCreated={() => qc.invalidateQueries({ queryKey: ["clients"] })}
      />

      <ClientDetailDialog clientId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}

// ---------- CreateClientDialog ----------
function CreateClientDialog({
  open,
  onOpenChange,
  payers,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  payers: ThirdPartyPayer[];
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    full_name: "",
    phone: "",
    cin: "",
    email: "",
    credit_enabled: false,
    credit_limit: "0",
    third_party_payer_id: "",
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const payload: any = {
        full_name: form.full_name,
        phone: form.phone || null,
        cin: form.cin || null,
        email: form.email || null,
        credit_enabled: form.credit_enabled,
        credit_limit: form.credit_limit || "0",
        third_party_payer_id: form.third_party_payer_id || null,
      };
      const { data } = await api.post("/clients", payload);
      return data;
    },
    onSuccess: () => {
      toast.success("Client créé");
      onCreated();
      onOpenChange(false);
      setForm({
        full_name: "",
        phone: "",
        cin: "",
        email: "",
        credit_enabled: false,
        credit_limit: "0",
        third_party_payer_id: "",
      });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Nouveau client</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label className="text-xs">Nom complet *</Label>
            <Input
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Téléphone</Label>
              <Input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">CIN</Label>
              <Input
                value={form.cin}
                onChange={(e) => setForm({ ...form, cin: e.target.value })}
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Email</Label>
            <Input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Tiers payant</Label>
            <select
              value={form.third_party_payer_id}
              onChange={(e) => setForm({ ...form, third_party_payer_id: e.target.value })}
              className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">— Aucun —</option>
              {payers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.name}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 cursor-pointer pt-2">
            <input
              type="checkbox"
              checked={form.credit_enabled}
              onChange={(e) => setForm({ ...form, credit_enabled: e.target.checked })}
            />
            <span className="text-sm">Autoriser le crédit</span>
          </label>
          {form.credit_enabled && (
            <div className="space-y-1">
              <Label className="text-xs">Plafond crédit (MAD)</Label>
              <Input
                type="number"
                step="0.01"
                value={form.credit_limit}
                onChange={(e) => setForm({ ...form, credit_limit: e.target.value })}
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!form.full_name || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------- ClientDetailDialog ----------
function ClientDetailDialog({
  clientId,
  onClose,
}: {
  clientId: string | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");

  const { data: client, isLoading } = useQuery({
    queryKey: ["clients", clientId],
    queryFn: () => api.get<ClientDetail>(`/clients/${clientId}`).then((r) => r.data),
    enabled: !!clientId,
  });

  const { data: dueDates } = useQuery({
    queryKey: ["clients", clientId, "due-dates"],
    queryFn: () => api.get(`/clients/${clientId}/credit/due-dates`).then((r) => r.data),
    enabled: !!clientId,
  });

  const paymentMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post("/clients/credit/payments", {
        client_id: clientId,
        amount: paymentAmount,
        payment_method: paymentMethod,
      });
      return data;
    },
    onSuccess: () => {
      toast.success("Paiement enregistré");
      setPaymentAmount("");
      qc.invalidateQueries({ queryKey: ["clients"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={!!clientId} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        {isLoading || !client ? (
          <div className="py-10 text-center">
            <Loader2 className="h-6 w-6 animate-spin mx-auto" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>{client.full_name}</DialogTitle>
              <DialogDescription>
                {client.phone ?? "—"} · CIN: {client.cin ?? "—"}
              </DialogDescription>
            </DialogHeader>

            <div className="grid grid-cols-3 gap-3">
              <Card className="p-4">
                <p className="text-xs text-muted-foreground">Solde dû</p>
                <p className="text-xl font-bold text-primary">{formatMAD(client.current_balance)}</p>
              </Card>
              <Card className="p-4">
                <p className="text-xs text-muted-foreground">En retard</p>
                <p className={`text-xl font-bold ${parseFloat(client.overdue_amount) > 0 ? "text-red-700" : "text-emerald-700"}`}>
                  {formatMAD(client.overdue_amount)}
                </p>
              </Card>
              <Card className="p-4">
                <p className="text-xs text-muted-foreground">Disponible</p>
                <p className="text-xl font-bold">{formatMAD(client.available_credit)}</p>
              </Card>
            </div>

            {client.credit_enabled && (
              <Card className="p-4 space-y-3 bg-muted/30">
                <div className="flex items-center gap-2">
                  <Wallet className="h-4 w-4" />
                  <p className="font-medium text-sm">Encaisser un paiement</p>
                </div>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="Montant"
                    value={paymentAmount}
                    onChange={(e) => setPaymentAmount(e.target.value)}
                    className="flex-1"
                  />
                  <select
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                  >
                    <option value="cash">Espèces</option>
                    <option value="card">Carte</option>
                    <option value="check">Chèque</option>
                    <option value="transfer">Virement</option>
                  </select>
                  <Button
                    onClick={() => paymentMutation.mutate()}
                    disabled={!paymentAmount || paymentMutation.isPending}
                  >
                    Encaisser
                  </Button>
                </div>
              </Card>
            )}

            <div>
              <h3 className="font-medium text-sm mb-2">Échéancier</h3>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Échéance</TableHead>
                    <TableHead className="text-right">Montant</TableHead>
                    <TableHead className="text-right">Reste</TableHead>
                    <TableHead>Statut</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(dueDates as any[] | undefined)?.length ? (
                    (dueDates as any[]).map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="text-sm">{formatDate(d.due_date)}</TableCell>
                        <TableCell className="text-right text-sm">{formatMAD(d.amount)}</TableCell>
                        <TableCell className="text-right text-sm">{formatMAD(d.amount_remaining)}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              d.status === "paid"
                                ? "success"
                                : d.is_overdue
                                ? "destructive"
                                : d.status === "partial"
                                ? "warning"
                                : "secondary"
                            }
                          >
                            {d.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground py-4">
                        Aucune échéance
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            <ReminderSection clientId={clientId!} clientName={client.full_name} clientPhone={client.phone} />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------- ReminderSection ----------
interface CreditReminder {
  id: string;
  channel: string;
  message: string | null;
  sent_at: string;
  created_at: string;
}

function ReminderSection({
  clientId,
  clientName,
  clientPhone,
}: {
  clientId: string;
  clientName: string;
  clientPhone: string | null;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const { data: reminders } = useQuery({
    queryKey: ["reminders", clientId],
    queryFn: () =>
      api.get<CreditReminder[]>(`/clients/${clientId}/credit/reminders`).then((r) => r.data),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-medium text-sm">Relances</h3>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setOpen(true)}
          disabled={!clientPhone}
          title={!clientPhone ? "Renseignez un numéro de téléphone pour envoyer des relances" : undefined}
        >
          <Send className="h-3.5 w-3.5 mr-1" />
          Envoyer une relance
        </Button>
      </div>

      {!reminders || reminders.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">Aucune relance envoyée.</p>
      ) : (
        <div className="space-y-1.5">
          {reminders.map((r) => (
            <div
              key={r.id}
              className="flex items-start gap-2 text-xs p-2 rounded bg-muted/30"
            >
              <ChannelIcon channel={r.channel} />
              <div className="flex-1 min-w-0">
                <p className="font-medium">
                  {r.channel} · {formatDate(r.sent_at)}
                </p>
                {r.message && (
                  <p className="text-muted-foreground line-clamp-2 mt-0.5">{r.message}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <SendReminderDialog
        open={open}
        onClose={() => setOpen(false)}
        clientId={clientId}
        clientName={clientName}
        clientPhone={clientPhone}
        onSent={() => {
          qc.invalidateQueries({ queryKey: ["reminders", clientId] });
          setOpen(false);
        }}
      />
    </div>
  );
}

function ChannelIcon({ channel }: { channel: string }) {
  const cls = "h-3.5 w-3.5 shrink-0 mt-0.5";
  if (channel === "whatsapp")
    return <MessageSquare className={`${cls} text-emerald-600`} />;
  if (channel === "sms") return <Phone className={`${cls} text-blue-600`} />;
  if (channel === "email") return <Mail className={`${cls} text-purple-600`} />;
  return <Phone className={`${cls} text-muted-foreground`} />;
}

function SendReminderDialog({
  open,
  onClose,
  clientId,
  clientName,
  clientPhone,
  onSent,
}: {
  open: boolean;
  onClose: () => void;
  clientId: string;
  clientName: string;
  clientPhone: string | null;
  onSent: () => void;
}) {
  const [channel, setChannel] = useState<"whatsapp" | "sms" | "email" | "phone">("whatsapp");
  const [customMessage, setCustomMessage] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.post(`/clients/${clientId}/credit/reminders`, {
        channel,
        message: customMessage || null,
      }),
    onSuccess: () => {
      toast.success(
        channel === "whatsapp" || channel === "sms"
          ? "Relance envoyée"
          : "Relance enregistrée",
        channel === "whatsapp"
          ? "Message WhatsApp envoyé au client."
          : channel === "sms"
          ? "SMS envoyé au client."
          : undefined
      );
      setCustomMessage("");
      onSent();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  const channelInfo: Record<string, { label: string; desc: string; icon: typeof MessageSquare }> = {
    whatsapp: {
      label: "WhatsApp",
      desc: clientPhone ? `Envoi via Twilio au ${clientPhone}` : "Téléphone manquant",
      icon: MessageSquare,
    },
    sms: {
      label: "SMS",
      desc: clientPhone ? `Envoi via Twilio au ${clientPhone}` : "Téléphone manquant",
      icon: Phone,
    },
    email: {
      label: "E-mail",
      desc: "Trace uniquement (envoi e-mail non encore implémenté)",
      icon: Mail,
    },
    phone: {
      label: "Appel téléphonique",
      desc: "Trace manuelle (vous appelez vous-même)",
      icon: Phone,
    },
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Envoyer une relance</DialogTitle>
          <DialogDescription>
            Pour {clientName}
            {clientPhone ? ` · ${clientPhone}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Canal</Label>
            <div className="grid grid-cols-2 gap-2">
              {(["whatsapp", "sms", "email", "phone"] as const).map((c) => {
                const info = channelInfo[c];
                const Icon = info.icon;
                const disabled = (c === "whatsapp" || c === "sms") && !clientPhone;
                return (
                  <button
                    key={c}
                    onClick={() => setChannel(c)}
                    disabled={disabled}
                    className={`p-2.5 rounded-md border-2 text-left text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                      channel === c
                        ? "border-primary bg-primary/5"
                        : "border-input hover:bg-accent/30"
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <Icon className="h-4 w-4" />
                      <span className="font-medium">{info.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground mt-1">{channelInfo[channel].desc}</p>
          </div>

          <div className="space-y-1">
            <Label>
              Message personnalisé{" "}
              <span className="text-muted-foreground font-normal">(optionnel)</span>
            </Label>
            <textarea
              value={customMessage}
              onChange={(e) => setCustomMessage(e.target.value)}
              rows={3}
              placeholder="Laissez vide pour utiliser le message standard généré automatiquement."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
            />
          </div>

          {(channel === "whatsapp" || channel === "sms") && (
            <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 text-xs text-amber-900">
              <strong>Note :</strong> si Twilio n'est pas configuré côté serveur, la relance est
              enregistrée en mode "preview" (pas d'envoi réel).
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            <Send className="h-4 w-4 mr-1" />
            Envoyer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
