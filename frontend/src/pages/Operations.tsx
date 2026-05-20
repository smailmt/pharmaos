/**
 * Pages opérationnelles légères :
 * - Ordonnancier (registre des ordonnances)
 * - Charges (frais d'exploitation)
 * - Échanges (entre pharmacies confrères)
 * - Inventaire (sessions de comptage)
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardList,
  Banknote,
  ArrowLeftRight,
  ListChecks,
  Plus,
  Loader2,
  Search,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD, formatDateTime } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { toast } from "@/components/ui/toast";
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

// =============================================================
// ORDONNANCIER
// =============================================================
interface PrescriptionLog {
  id: string;
  sale_id: string | null;
  sequential_number: number;
  prescription_number: string | null;
  prescription_date: string | null;
  prescriber_name: string | null;
  patient_name: string | null;
  patient_cin: string | null;
  dispensed_items: Array<{ product_id: string; name: string | null; quantity: number }>;
  created_at: string;
}

export function OrdonnancierPage() {
  const [search, setSearch] = useState("");

  const { data: logs, isLoading } = useQuery({
    queryKey: ["prescription-log", search],
    queryFn: () =>
      api
        .get<PrescriptionLog[]>(
          `/operations/prescription-log${search ? `?search=${encodeURIComponent(search)}` : ""}`
        )
        .then((r) => r.data),
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-4">
      <header>
        <div className="flex items-center gap-2 mb-1">
          <ClipboardList className="h-6 w-6 text-primary" />
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Ordonnancier</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Registre des dispensations sur ordonnance — obligatoire pour les médicaments des listes I et II.
        </p>
      </header>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Patient, prescripteur, n° ordonnance…"
          className="pl-10"
        />
      </div>

      <Card>
        {isLoading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : !logs || logs.length === 0 ? (
          <EmptyState
            Icon={ClipboardList}
            title="Aucune ordonnance enregistrée"
            description="Les ventes avec ordonnance apparaîtront ici automatiquement."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-16">N°</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Patient</TableHead>
                <TableHead>Prescripteur</TableHead>
                <TableHead>N° ordonnance</TableHead>
                <TableHead className="text-right">Médicaments</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="font-mono text-xs">#{l.sequential_number}</TableCell>
                  <TableCell className="text-sm">{formatDateTime(l.created_at)}</TableCell>
                  <TableCell>{l.patient_name || "—"}</TableCell>
                  <TableCell>{l.prescriber_name || "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{l.prescription_number || "—"}</TableCell>
                  <TableCell className="text-right">
                    <Badge variant="outline">{l.dispensed_items.length}</Badge>
                  </TableCell>
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
// CHARGES
// =============================================================
interface Expense {
  id: string;
  expense_date: string;
  category: string;
  amount: string;
  description: string;
  payment_method: string;
  is_recurring: boolean;
}

interface ExpenseSummary {
  category: string;
  total_amount: string;
  count: number;
}

const EXPENSE_CATEGORIES = [
  { value: "rent", label: "Loyer" },
  { value: "utilities", label: "Électricité / Eau" },
  { value: "salaries", label: "Salaires" },
  { value: "supplies", label: "Fournitures" },
  { value: "taxes", label: "Impôts & taxes" },
  { value: "insurance", label: "Assurances" },
  { value: "maintenance", label: "Entretien" },
  { value: "marketing", label: "Marketing" },
  { value: "other", label: "Autre" },
];

export function ChargesPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const { data: expenses, isLoading } = useQuery({
    queryKey: ["expenses"],
    queryFn: () => api.get<Expense[]>("/operations/expenses?days=90").then((r) => r.data),
  });

  const { data: summary } = useQuery({
    queryKey: ["expenses-summary"],
    queryFn: () =>
      api.get<ExpenseSummary[]>("/operations/expenses/summary?days=30").then((r) => r.data),
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Banknote className="h-6 w-6 text-primary" />
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Charges</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Frais d'exploitation : loyer, salaires, électricité, fournitures…
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Nouvelle charge
        </Button>
      </header>

      {/* Résumé 30j */}
      <Card>
        <CardHeader>
          <CardTitle>Résumé 30 derniers jours</CardTitle>
        </CardHeader>
        <CardContent>
          {!summary || summary.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">Aucune charge.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {summary.map((s) => {
                const label = EXPENSE_CATEGORIES.find((c) => c.value === s.category)?.label ?? s.category;
                return (
                  <div key={s.category} className="border rounded-md p-3">
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="text-lg font-semibold">{formatMAD(s.total_amount)}</p>
                    <p className="text-xs text-muted-foreground">{s.count} entrées</p>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Détail (90 derniers jours)</CardTitle>
        </CardHeader>
        {isLoading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : !expenses || expenses.length === 0 ? (
          <EmptyState
            Icon={Banknote}
            title="Aucune charge enregistrée"
            description="Enregistrez vos charges pour suivre votre rentabilité."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Catégorie</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Paiement</TableHead>
                <TableHead className="text-right">Montant</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {expenses.map((e) => (
                <TableRow key={e.id}>
                  <TableCell>{e.expense_date}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {EXPENSE_CATEGORIES.find((c) => c.value === e.category)?.label ?? e.category}
                    </Badge>
                  </TableCell>
                  <TableCell>{e.description}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{e.payment_method}</TableCell>
                  <TableCell className="text-right font-semibold">{formatMAD(e.amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreateExpenseDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          qc.invalidateQueries({ queryKey: ["expenses"] });
          qc.invalidateQueries({ queryKey: ["expenses-summary"] });
        }}
      />
    </div>
  );
}

function CreateExpenseDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [category, setCategory] = useState("rent");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/operations/expenses", {
        category,
        amount: parseFloat(amount || "0").toFixed(2),
        description,
        payment_method: paymentMethod,
      }),
    onSuccess: () => {
      toast.success("Charge enregistrée");
      setAmount("");
      setDescription("");
      onCreated();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle charge</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Catégorie</Label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {EXPENSE_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label>Montant (MAD)</Label>
            <Input
              type="number"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label>Description</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ex: Loyer juin 2026"
            />
          </div>
          <div className="space-y-1">
            <Label>Moyen de paiement</Label>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="cash">Espèces</option>
              <option value="card">Carte</option>
              <option value="check">Chèque</option>
              <option value="transfer">Virement</option>
            </select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!amount || !description || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================
// ÉCHANGES CONFRÈRES
// =============================================================
interface Exchange {
  id: string;
  exchange_date: string;
  direction: "in" | "out";
  partner_name: string;
  partner_phone: string | null;
  product_name: string;
  quantity: number;
  unit_value: string;
  total_value: string;
  status: "pending" | "settled" | "cancelled";
}

interface PartnerBalance {
  partner_name: string;
  in_count: number;
  in_value: string;
  out_count: number;
  out_value: string;
  net_balance: string;
}

export function EchangesPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const { data: exchanges, isLoading } = useQuery({
    queryKey: ["exchanges"],
    queryFn: () => api.get<Exchange[]>("/operations/exchanges").then((r) => r.data),
  });

  const { data: balances } = useQuery({
    queryKey: ["exchange-balances"],
    queryFn: () =>
      api.get<PartnerBalance[]>("/operations/exchanges/balances").then((r) => r.data),
  });

  const settleMutation = useMutation({
    mutationFn: (id: string) => api.post(`/operations/exchanges/${id}/settle`),
    onSuccess: () => {
      toast.success("Échange réglé");
      qc.invalidateQueries({ queryKey: ["exchanges"] });
      qc.invalidateQueries({ queryKey: ["exchange-balances"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ArrowLeftRight className="h-6 w-6 text-primary" />
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Échanges confrères</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Suivi des produits échangés avec d'autres pharmacies (dépannages, prêts).
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Nouvel échange
        </Button>
      </header>

      {balances && balances.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Soldes par pharmacie</CardTitle>
            <CardDescription>Positif = ils nous doivent. Négatif = on leur doit.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {balances.map((b) => {
                const net = parseFloat(b.net_balance);
                return (
                  <div key={b.partner_name} className="border rounded-md p-3">
                    <p className="font-medium text-sm">{b.partner_name}</p>
                    <div className="flex items-baseline gap-2 mt-1">
                      <span
                        className={`text-lg font-bold ${
                          net > 0 ? "text-emerald-600" : net < 0 ? "text-red-600" : ""
                        }`}
                      >
                        {net > 0 ? <TrendingUp className="h-4 w-4 inline" /> : net < 0 ? <TrendingDown className="h-4 w-4 inline" /> : null}
                        {formatMAD(net)}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Reçus : {b.in_count} · Donnés : {b.out_count}
                    </p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Tous les échanges</CardTitle>
        </CardHeader>
        {isLoading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : !exchanges || exchanges.length === 0 ? (
          <EmptyState
            Icon={ArrowLeftRight}
            title="Aucun échange enregistré"
            description="Suivez les produits prêtés ou empruntés entre pharmacies."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Sens</TableHead>
                <TableHead>Confrère</TableHead>
                <TableHead>Produit</TableHead>
                <TableHead className="text-right">Qté</TableHead>
                <TableHead className="text-right">Valeur</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {exchanges.map((e) => (
                <TableRow key={e.id}>
                  <TableCell>{e.exchange_date}</TableCell>
                  <TableCell>
                    <Badge variant={e.direction === "in" ? "secondary" : "outline"} className="text-[10px]">
                      {e.direction === "in" ? "Reçu" : "Donné"}
                    </Badge>
                  </TableCell>
                  <TableCell>{e.partner_name}</TableCell>
                  <TableCell>{e.product_name}</TableCell>
                  <TableCell className="text-right">{e.quantity}</TableCell>
                  <TableCell className="text-right">{formatMAD(e.total_value)}</TableCell>
                  <TableCell>
                    {e.status === "settled" ? (
                      <Badge variant="success" className="text-[10px]">
                        Réglé
                      </Badge>
                    ) : (
                      <Badge variant="warning" className="text-[10px]">
                        En attente
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {e.status === "pending" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => settleMutation.mutate(e.id)}
                      >
                        Régler
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreateExchangeDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          qc.invalidateQueries({ queryKey: ["exchanges"] });
          qc.invalidateQueries({ queryKey: ["exchange-balances"] });
        }}
      />
    </div>
  );
}

function CreateExchangeDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [direction, setDirection] = useState<"in" | "out">("in");
  const [partnerName, setPartnerName] = useState("");
  const [productName, setProductName] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unitValue, setUnitValue] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/operations/exchanges", {
        direction,
        partner_name: partnerName,
        product_name: productName,
        quantity: parseInt(quantity || "1"),
        unit_value: parseFloat(unitValue || "0").toFixed(2),
      }),
    onSuccess: () => {
      toast.success("Échange enregistré");
      setPartnerName("");
      setProductName("");
      setQuantity("1");
      setUnitValue("");
      onCreated();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvel échange</DialogTitle>
          <DialogDescription>Enregistrer un prêt entre pharmacies confrères.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Sens</Label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setDirection("in")}
                className={`p-3 rounded-md border-2 text-sm ${
                  direction === "in" ? "border-primary bg-primary/5" : "border-input"
                }`}
              >
                <strong>Reçu</strong>
                <br />
                <span className="text-xs text-muted-foreground">Le confrère nous prête</span>
              </button>
              <button
                onClick={() => setDirection("out")}
                className={`p-3 rounded-md border-2 text-sm ${
                  direction === "out" ? "border-primary bg-primary/5" : "border-input"
                }`}
              >
                <strong>Donné</strong>
                <br />
                <span className="text-xs text-muted-foreground">Nous prêtons au confrère</span>
              </button>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Nom de la pharmacie confrère</Label>
            <Input value={partnerName} onChange={(e) => setPartnerName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Produit</Label>
            <Input value={productName} onChange={(e) => setProductName(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Quantité</Label>
              <Input type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Valeur unitaire (MAD)</Label>
              <Input
                type="number"
                step="0.01"
                value={unitValue}
                onChange={(e) => setUnitValue(e.target.value)}
              />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!partnerName || !productName || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================
// INVENTAIRE
// =============================================================
interface InventorySession {
  id: string;
  name: string;
  status: "in_progress" | "completed" | "cancelled";
  started_at: string;
  completed_at: string | null;
  items_counted: number;
  discrepancies_count: number;
  total_value_difference: string;
}

export function InventairePage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const { data: sessions, isLoading } = useQuery({
    queryKey: ["inventory-sessions"],
    queryFn: () =>
      api.get<InventorySession[]>("/operations/inventory-sessions").then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (name: string) =>
      api.post<InventorySession>("/operations/inventory-sessions", { name, scope: "full" }),
    onSuccess: () => {
      toast.success("Session démarrée");
      qc.invalidateQueries({ queryKey: ["inventory-sessions"] });
      setCreateOpen(false);
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-4">
      <header className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ListChecks className="h-6 w-6 text-primary" />
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Inventaire</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Sessions de comptage physique du stock — aligne le stock théorique sur la réalité.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Nouvel inventaire
        </Button>
      </header>

      <Card>
        {isLoading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : !sessions || sessions.length === 0 ? (
          <EmptyState
            Icon={ListChecks}
            title="Aucun inventaire"
            description="Démarrez votre premier inventaire pour vérifier la cohérence du stock."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nom</TableHead>
                <TableHead>Démarré</TableHead>
                <TableHead className="text-right">Comptés</TableHead>
                <TableHead className="text-right">Écarts</TableHead>
                <TableHead className="text-right">Valeur écart</TableHead>
                <TableHead>Statut</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell className="text-sm">{formatDateTime(s.started_at)}</TableCell>
                  <TableCell className="text-right">{s.items_counted}</TableCell>
                  <TableCell className="text-right">
                    {s.discrepancies_count > 0 ? (
                      <Badge variant="warning" className="text-[10px]">
                        {s.discrepancies_count}
                      </Badge>
                    ) : (
                      "0"
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {parseFloat(s.total_value_difference) !== 0
                      ? formatMAD(s.total_value_difference)
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {s.status === "completed" ? (
                      <Badge variant="success" className="text-[10px]">
                        Terminé
                      </Badge>
                    ) : s.status === "in_progress" ? (
                      <Badge variant="secondary" className="text-[10px]">
                        En cours
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px]">
                        Annulé
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Dialog open={createOpen} onOpenChange={(v) => !v && setCreateOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouveau session d'inventaire</DialogTitle>
            <DialogDescription>
              Démarrer une session de comptage. Vous pourrez ajouter les produits comptés un par un.
            </DialogDescription>
          </DialogHeader>
          <Button
            onClick={() => createMutation.mutate(`Inventaire ${new Date().toLocaleDateString("fr-FR")}`)}
            disabled={createMutation.isPending}
            className="w-full"
          >
            {createMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Démarrer
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
