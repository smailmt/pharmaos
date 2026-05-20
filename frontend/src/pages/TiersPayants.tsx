/**
 * Tiers Payants — gestion des organismes de couverture (CNOPS, CNSS, mutuelles).
 *
 * Workflow : Payeurs → Demandes (claims générées aux ventes) → Bordereaux
 * (regroupement périodique) → Paiements (règlement de l'organisme).
 *
 * Tout le backend existe dans /third-party/* — cette page l'expose.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield,
  Users,
  FileText,
  Layers,
  Banknote,
  Plus,
  Loader2,
  Send,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD, formatDate, cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { Term } from "@/components/Term";
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";

// ---------- Types ----------
interface Payer {
  id: string;
  code: string;
  name: string;
  type: string;
  default_coverage_rate: string;
  payment_terms_days: number;
  requires_prescription: boolean;
  is_active: boolean;
}
interface Claim {
  id: string;
  payer_id: string;
  sale_id: string;
  bordereau_id: string | null;
  claim_date: string;
  prescription_number: string | null;
  total_amount: string;
  coverage_rate: string;
  payer_share: string;
  client_share: string;
  status: string;
}
interface Bordereau {
  id: string;
  payer_id: string;
  bordereau_number: string;
  period_start: string;
  period_end: string;
  submitted_at: string | null;
  total_amount: string;
  amount_paid: string;
  status: string;
}

const CLAIM_STATUS: Record<string, { label: string; variant: "secondary" | "success" | "warning" | "outline" | "destructive" }> = {
  pending: { label: "En attente", variant: "warning" },
  in_bordereau: { label: "Dans bordereau", variant: "secondary" },
  submitted: { label: "Soumise", variant: "secondary" },
  paid: { label: "Payée", variant: "success" },
  rejected: { label: "Rejetée", variant: "destructive" },
  draft: { label: "Brouillon", variant: "outline" },
};

function ClaimStatusBadge({ status }: { status: string }) {
  const info = CLAIM_STATUS[status] ?? { label: status, variant: "outline" as const };
  return <Badge variant={info.variant} className="text-[10px]">{info.label}</Badge>;
}

const TABS = [
  { id: "payers", label: "Organismes", icon: Users },
  { id: "claims", label: "Demandes", icon: FileText },
  { id: "bordereaux", label: "Bordereaux", icon: Layers },
  { id: "payments", label: "Paiements", icon: Banknote },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function TiersPayantsPage() {
  const [tab, setTab] = useState<TabId>("payers");

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header>
        <div className="flex items-center gap-2 mb-1">
          <Shield className="h-6 w-6 text-primary" />
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Tiers Payants</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Gérez les organismes (<Term code="CNOPS" />, <Term code="CNSS" />, mutuelles), les{" "}
          <Term code="Tiers payant">demandes de remboursement</Term> et les <Term code="Bordereau">bordereaux</Term>.
        </p>
      </header>

      <div className="border-b overflow-x-auto">
        <div className="flex gap-1 min-w-max">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
                  tab === t.id ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {tab === "payers" && <PayersTab />}
      {tab === "claims" && <ClaimsTab />}
      {tab === "bordereaux" && <BordereauxTab />}
      {tab === "payments" && <PaymentsTab />}
    </div>
  );
}

// Hook partagé payeurs
function usePayers() {
  const { data } = useQuery({
    queryKey: ["tp-payers"],
    queryFn: () => api.get<Payer[]>("/third-party/payers").then((r) => r.data),
  });
  return data ?? [];
}

// =============================================================
// PAYEURS
// =============================================================
function PayersTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const { data: payers, isLoading } = useQuery({
    queryKey: ["tp-payers"],
    queryFn: () => api.get<Payer[]>("/third-party/payers").then((r) => r.data),
  });

  const typeLabels: Record<string, string> = {
    public: "Public",
    private: "Privé",
    mutual: "Mutuelle",
    insurance: "Assurance",
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Nouvel organisme
        </Button>
      </div>
      <Card>
        {isLoading ? (
          <SkeletonRows />
        ) : !payers || payers.length === 0 ? (
          <EmptyState Icon={Users} title="Aucun organisme" description="Ajoutez CNOPS, CNSS ou des mutuelles pour gérer le tiers payant." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Nom</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Taux couverture</TableHead>
                <TableHead className="text-right">Délai paiement</TableHead>
                <TableHead>Ordonnance</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payers.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-mono text-xs">{p.code}</TableCell>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell><Badge variant="outline" className="text-[10px]">{typeLabels[p.type] ?? p.type}</Badge></TableCell>
                  <TableCell className="text-right">{(parseFloat(p.default_coverage_rate) * 100).toFixed(0)}%</TableCell>
                  <TableCell className="text-right">{p.payment_terms_days} j</TableCell>
                  <TableCell>{p.requires_prescription ? "Requise" : "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreatePayerDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => {
        setCreateOpen(false);
        qc.invalidateQueries({ queryKey: ["tp-payers"] });
      }} />
    </div>
  );
}

function CreatePayerDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState("public");
  const [coverageRate, setCoverageRate] = useState("80");
  const [paymentTerms, setPaymentTerms] = useState("60");
  const [requiresPrescription, setRequiresPrescription] = useState(true);

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/third-party/payers", {
        code,
        name,
        type,
        default_coverage_rate: (parseFloat(coverageRate || "0") / 100).toFixed(4),
        payment_terms_days: parseInt(paymentTerms || "60"),
        requires_prescription: requiresPrescription,
        requires_authorization: false,
        bordereau_frequency: "monthly",
        rules: {},
      }),
    onSuccess: () => {
      toast.success("Organisme créé");
      setCode(""); setName("");
      onCreated();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvel organisme de couverture</DialogTitle>
          <DialogDescription>Ex: CNOPS, CNSS, mutuelle privée…</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Code</Label>
              <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="CNOPS" />
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <select value={type} onChange={(e) => setType(e.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
                <option value="public">Public</option>
                <option value="private">Privé</option>
                <option value="mutual">Mutuelle</option>
                <option value="insurance">Assurance</option>
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Nom complet</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Caisse Nationale des Organismes de Prévoyance Sociale" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Taux de couverture (%)</Label>
              <Input type="number" value={coverageRate} onChange={(e) => setCoverageRate(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Délai paiement (jours)</Label>
              <Input type="number" value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={requiresPrescription} onChange={(e) => setRequiresPrescription(e.target.checked)} />
            Ordonnance obligatoire pour le remboursement
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={!code || !name || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================
// DEMANDES (claims)
// =============================================================
function ClaimsTab() {
  const payers = usePayers();
  const [payerFilter, setPayerFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const { data: claims, isLoading } = useQuery({
    queryKey: ["tp-claims", payerFilter, statusFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (payerFilter) params.set("payer_id", payerFilter);
      if (statusFilter) params.set("status", statusFilter);
      return api.get<Claim[]>(`/third-party/claims?${params}`).then((r) => r.data);
    },
  });

  const payerName = (id: string) => payers.find((p) => p.id === id)?.name ?? "—";

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        <select value={payerFilter} onChange={(e) => setPayerFilter(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm">
          <option value="">Tous les organismes</option>
          {payers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm">
          <option value="">Tous les statuts</option>
          <option value="pending">En attente</option>
          <option value="in_bordereau">Dans bordereau</option>
          <option value="paid">Payées</option>
          <option value="rejected">Rejetées</option>
        </select>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-md p-3 text-xs text-blue-900">
        Les demandes sont créées automatiquement lors d'une vente avec tiers payant. Regroupez-les ensuite en bordereaux.
      </div>

      <Card>
        {isLoading ? (
          <SkeletonRows />
        ) : !claims || claims.length === 0 ? (
          <EmptyState Icon={FileText} title="Aucune demande" description="Les demandes de remboursement apparaîtront ici après les ventes en tiers payant." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Organisme</TableHead>
                <TableHead>N° ordonnance</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead className="text-right">Part organisme</TableHead>
                <TableHead className="text-right">Part client</TableHead>
                <TableHead>Statut</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {claims.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>{formatDate(c.claim_date)}</TableCell>
                  <TableCell>{payerName(c.payer_id)}</TableCell>
                  <TableCell className="font-mono text-xs">{c.prescription_number || "—"}</TableCell>
                  <TableCell className="text-right">{formatMAD(c.total_amount)}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(c.payer_share)}</TableCell>
                  <TableCell className="text-right text-muted-foreground">{formatMAD(c.client_share)}</TableCell>
                  <TableCell><ClaimStatusBadge status={c.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

// =============================================================
// BORDEREAUX
// =============================================================
function BordereauxTab() {
  const qc = useQueryClient();
  const payers = usePayers();
  const [createOpen, setCreateOpen] = useState(false);

  const { data: bordereaux, isLoading } = useQuery({
    queryKey: ["tp-bordereaux"],
    queryFn: () => api.get<Bordereau[]>("/third-party/bordereaux").then((r) => r.data),
  });

  const submitMutation = useMutation({
    mutationFn: (id: string) => api.post(`/third-party/bordereaux/${id}/submit`),
    onSuccess: () => {
      toast.success("Bordereau soumis");
      qc.invalidateQueries({ queryKey: ["tp-bordereaux"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  const payerName = (id: string) => payers.find((p) => p.id === id)?.name ?? "—";

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Générer un bordereau
        </Button>
      </div>
      <Card>
        {isLoading ? (
          <SkeletonRows />
        ) : !bordereaux || bordereaux.length === 0 ? (
          <EmptyState Icon={Layers} title="Aucun bordereau" description="Regroupez les demandes en attente en bordereau périodique." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>N° bordereau</TableHead>
                <TableHead>Organisme</TableHead>
                <TableHead>Période</TableHead>
                <TableHead className="text-right">Montant</TableHead>
                <TableHead className="text-right">Payé</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {bordereaux.map((b) => (
                <TableRow key={b.id}>
                  <TableCell className="font-mono text-xs">{b.bordereau_number}</TableCell>
                  <TableCell>{payerName(b.payer_id)}</TableCell>
                  <TableCell className="text-sm">{formatDate(b.period_start)} → {formatDate(b.period_end)}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(b.total_amount)}</TableCell>
                  <TableCell className="text-right text-muted-foreground">{formatMAD(b.amount_paid)}</TableCell>
                  <TableCell>
                    {b.submitted_at ? (
                      <Badge variant="secondary" className="text-[10px]"><CheckCircle2 className="h-3 w-3 mr-0.5" />Soumis</Badge>
                    ) : (
                      <Badge variant="warning" className="text-[10px]"><Clock className="h-3 w-3 mr-0.5" />Brouillon</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {!b.submitted_at && (
                      <Button size="sm" variant="ghost" onClick={() => submitMutation.mutate(b.id)}>
                        <Send className="h-3.5 w-3.5 mr-1" /> Soumettre
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreateBordereauDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => {
        setCreateOpen(false);
        qc.invalidateQueries({ queryKey: ["tp-bordereaux"] });
        qc.invalidateQueries({ queryKey: ["tp-claims"] });
      }} />
    </div>
  );
}

function CreateBordereauDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const payers = usePayers();
  const [payerId, setPayerId] = useState("");
  const today = new Date();
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
  const lastOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().slice(0, 10);
  const [periodStart, setPeriodStart] = useState(firstOfMonth);
  const [periodEnd, setPeriodEnd] = useState(lastOfMonth);

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/third-party/bordereaux", {
        payer_id: payerId,
        period_start: periodStart,
        period_end: periodEnd,
        claim_ids: null, // null = toutes les demandes pending de la période
      }),
    onSuccess: () => {
      toast.success("Bordereau généré", "Les demandes en attente de la période ont été regroupées.");
      setPayerId("");
      onCreated();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Générer un bordereau</DialogTitle>
          <DialogDescription>Regroupe les demandes en attente d'un organisme sur une période.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Organisme</Label>
            <select value={payerId} onChange={(e) => setPayerId(e.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
              <option value="">— Choisir —</option>
              {payers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Début période</Label>
              <Input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Fin période</Label>
              <Input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={!payerId || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Générer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================
// PAIEMENTS
// =============================================================
interface TPPayment {
  id: string;
  bordereau_id: string;
  payment_date: string;
  amount: string;
  payment_method: string;
  reference: string | null;
}

function PaymentsTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const { data: payments, isLoading } = useQuery({
    queryKey: ["tp-payments"],
    queryFn: () => api.get<TPPayment[]>("/third-party/payments").then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Enregistrer un paiement
        </Button>
      </div>
      <Card>
        {isLoading ? (
          <SkeletonRows />
        ) : !payments || payments.length === 0 ? (
          <EmptyState Icon={Banknote} title="Aucun paiement" description="Enregistrez les règlements reçus des organismes." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Méthode</TableHead>
                <TableHead>Référence</TableHead>
                <TableHead className="text-right">Montant</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{formatDate(p.payment_date)}</TableCell>
                  <TableCell className="text-sm">{p.payment_method}</TableCell>
                  <TableCell className="font-mono text-xs">{p.reference || "—"}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(p.amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreateTPPaymentDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => {
        setCreateOpen(false);
        qc.invalidateQueries({ queryKey: ["tp-payments"] });
        qc.invalidateQueries({ queryKey: ["tp-bordereaux"] });
      }} />
    </div>
  );
}

function CreateTPPaymentDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { data: bordereaux } = useQuery({
    queryKey: ["tp-bordereaux"],
    queryFn: () => api.get<Bordereau[]>("/third-party/bordereaux").then((r) => r.data),
    enabled: open,
  });
  const [bordereauId, setBordereauId] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("transfer");
  const [reference, setReference] = useState("");

  const submittedBordereaux = (bordereaux ?? []).filter((b) => b.submitted_at);

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/third-party/payments", {
        bordereau_id: bordereauId,
        amount: parseFloat(amount || "0").toFixed(2),
        payment_method: method,
        reference: reference || null,
        rejected_claim_ids: null,
        rejection_reasons: null,
      }),
    onSuccess: () => {
      toast.success("Paiement enregistré");
      setBordereauId(""); setAmount(""); setReference("");
      onCreated();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Enregistrer un paiement d'organisme</DialogTitle>
          <DialogDescription>Règlement reçu pour un bordereau soumis.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Bordereau</Label>
            <select value={bordereauId} onChange={(e) => {
              setBordereauId(e.target.value);
              const b = submittedBordereaux.find((x) => x.id === e.target.value);
              if (b) setAmount((parseFloat(b.total_amount) - parseFloat(b.amount_paid)).toFixed(2));
            }} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
              <option value="">— Choisir un bordereau soumis —</option>
              {submittedBordereaux.map((b) => (
                <option key={b.id} value={b.id}>{b.bordereau_number} — {formatMAD(b.total_amount)}</option>
              ))}
            </select>
            {submittedBordereaux.length === 0 && (
              <p className="text-xs text-amber-600">Aucun bordereau soumis. Soumettez un bordereau d'abord.</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Montant (MAD)</Label>
              <Input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Méthode</Label>
              <select value={method} onChange={(e) => setMethod(e.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
                <option value="transfer">Virement</option>
                <option value="check">Chèque</option>
                <option value="cash">Espèces</option>
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Référence (optionnel)</Label>
            <Input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="N° virement, réf paiement…" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={!bordereauId || !amount || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Helper
function SkeletonRows() {
  return (
    <div className="p-4 space-y-2">
      {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
    </div>
  );
}
