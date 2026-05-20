import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Truck, Loader2, ShoppingCart, PackageCheck, FileText, Banknote, RotateCcw, Users, Lightbulb } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { cn } from "@/lib/utils";
import {
  OrdersTab,
  DeliveriesTab,
  InvoicesTab,
  PaymentsTab,
  ReturnsTab,
  ProposalTab,
} from "@/pages/SupplierOperations";
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

interface Supplier {
  id: string;
  code: string;
  name: string;
  type: string;
  ice: string | null;
  phone: string | null;
  email: string | null;
  default_discount_rate: string;
  payment_terms_days: number;
  credit_limit: string;
  is_active: boolean;
}

interface SupplierDetail extends Supplier {
  current_balance: string;
  overdue_amount: string;
}

interface SupplierInvoice {
  id: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  total_ttc: string;
  amount_paid: string;
  status: string;
}

const TABS = [
  { id: "suppliers", label: "Fournisseurs", icon: Users },
  { id: "proposal", label: "Proposition", icon: Lightbulb },
  { id: "orders", label: "Commandes", icon: ShoppingCart },
  { id: "deliveries", label: "Bons de livraison", icon: PackageCheck },
  { id: "invoices", label: "Factures", icon: FileText },
  { id: "payments", label: "Paiements", icon: Banknote },
  { id: "returns", label: "Retours", icon: RotateCcw },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function FournisseursPage() {
  const [tab, setTab] = useState<TabId>("suppliers");

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header>
        <div className="flex items-center gap-2 mb-1">
          <Truck className="h-6 w-6 text-primary" />
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Achats &amp; Fournisseurs</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Gérez vos grossistes, commandes, livraisons, factures et paiements.
        </p>
      </header>

      {/* Onglets */}
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
                  tab === t.id
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Contenu */}
      {tab === "suppliers" && <SuppliersListTab />}
      {tab === "proposal" && <ProposalTab />}
      {tab === "orders" && <OrdersTab />}
      {tab === "deliveries" && <DeliveriesTab />}
      {tab === "invoices" && <InvoicesTab />}
      {tab === "payments" && <PaymentsTab />}
      {tab === "returns" && <ReturnsTab />}
    </div>
  );
}

function SuppliersListTab() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: suppliers, isLoading } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api.get<Supplier[]>("/suppliers").then((r) => r.data),
  });

  const filtered = useMemo(() => {
    if (!suppliers) return [];
    const q = search.trim().toLowerCase();
    if (!q) return suppliers;
    return suppliers.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.code.toLowerCase().includes(q) ||
        (s.ice && s.ice.includes(q))
    );
  }, [suppliers, search]);

  const typeLabels: Record<string, string> = {
    wholesaler: "Grossiste",
    laboratory: "Laboratoire",
    colleague: "Confrère",
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Nom, code, ICE..."
            className="pl-10"
          />
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Nouveau fournisseur
        </Button>
      </div>

      <Card>
        {isLoading ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            Icon={Truck}
            title="Aucun fournisseur"
            description={
              search
                ? "Aucun résultat pour cette recherche."
                : "Ajoutez vos grossistes, laboratoires et confrères pour gérer vos commandes."
            }
            action={
              !search && (
                <Button onClick={() => setCreateOpen(true)}>
                  <Plus className="h-4 w-4 mr-1" />
                  Premier fournisseur
                </Button>
              )
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Nom</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>ICE</TableHead>
                <TableHead>Téléphone</TableHead>
                <TableHead className="text-right">Conditions</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((s) => (
                <TableRow
                  key={s.id}
                  className="cursor-pointer"
                  onClick={() => setSelectedId(s.id)}
                >
                  <TableCell className="font-mono text-xs">{s.code}</TableCell>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{typeLabels[s.type] ?? s.type}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{s.ice ?? "—"}</TableCell>
                  <TableCell className="text-sm">{s.phone ?? "—"}</TableCell>
                  <TableCell className="text-right text-sm">
                    {(parseFloat(s.default_discount_rate) * 100).toFixed(1)}% · {s.payment_terms_days}j
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="ghost">Détail</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreateSupplierDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => qc.invalidateQueries({ queryKey: ["suppliers"] })}
      />

      <SupplierDetailDialog
        supplierId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
}

// ---------- CreateSupplierDialog ----------
function CreateSupplierDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    code: "",
    name: "",
    type: "wholesaler",
    ice: "",
    phone: "",
    email: "",
    default_discount_rate: "0",
    payment_terms_days: "30",
    credit_limit: "0",
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        default_discount_rate: (parseFloat(form.default_discount_rate) / 100).toFixed(4),
        payment_terms_days: parseInt(form.payment_terms_days) || 30,
        credit_limit: form.credit_limit || "0",
        ice: form.ice || null,
        phone: form.phone || null,
        email: form.email || null,
      };
      const { data } = await api.post("/suppliers", payload);
      return data;
    },
    onSuccess: () => {
      toast.success("Fournisseur créé");
      onCreated();
      onOpenChange(false);
      setForm({
        code: "",
        name: "",
        type: "wholesaler",
        ice: "",
        phone: "",
        email: "",
        default_discount_rate: "0",
        payment_terms_days: "30",
        credit_limit: "0",
      });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau fournisseur</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Code *</Label>
            <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Type</Label>
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
              className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="wholesaler">Grossiste</option>
              <option value="laboratory">Laboratoire</option>
              <option value="colleague">Confrère</option>
            </select>
          </div>
          <div className="col-span-2 space-y-1">
            <Label className="text-xs">Nom *</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">ICE</Label>
            <Input value={form.ice} onChange={(e) => setForm({ ...form, ice: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Téléphone</Label>
            <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div className="col-span-2 space-y-1">
            <Label className="text-xs">Email</Label>
            <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Remise par défaut (%)</Label>
            <Input
              type="number"
              step="0.1"
              value={form.default_discount_rate}
              onChange={(e) => setForm({ ...form, default_discount_rate: e.target.value })}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Délai paiement (jours)</Label>
            <Input
              type="number"
              value={form.payment_terms_days}
              onChange={(e) => setForm({ ...form, payment_terms_days: e.target.value })}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!form.code || !form.name || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------- SupplierDetailDialog ----------
function SupplierDetailDialog({
  supplierId,
  onClose,
}: {
  supplierId: string | null;
  onClose: () => void;
}) {
  const { data: supplier, isLoading } = useQuery({
    queryKey: ["suppliers", supplierId],
    queryFn: () =>
      api.get<SupplierDetail>(`/suppliers/${supplierId}`).then((r) => r.data),
    enabled: !!supplierId,
  });

  const { data: invoices } = useQuery({
    queryKey: ["suppliers", supplierId, "invoices"],
    queryFn: () =>
      api.get<SupplierInvoice[]>(`/suppliers/${supplierId}/invoices`).then((r) => r.data),
    enabled: !!supplierId,
  });

  return (
    <Dialog open={!!supplierId} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        {isLoading || !supplier ? (
          <div className="py-10 text-center">
            <Loader2 className="h-6 w-6 animate-spin mx-auto" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>{supplier.name}</DialogTitle>
              <DialogDescription>
                {supplier.code} · {supplier.phone ?? "—"} · ICE: {supplier.ice ?? "—"}
              </DialogDescription>
            </DialogHeader>

            <div className="grid grid-cols-2 gap-3">
              <Card className="p-4">
                <p className="text-xs text-muted-foreground">Solde à payer</p>
                <p className="text-xl font-bold text-primary">{formatMAD(supplier.current_balance)}</p>
              </Card>
              <Card className="p-4">
                <p className="text-xs text-muted-foreground">En retard</p>
                <p className={`text-xl font-bold ${parseFloat(supplier.overdue_amount) > 0 ? "text-red-700" : "text-emerald-700"}`}>
                  {formatMAD(supplier.overdue_amount)}
                </p>
              </Card>
            </div>

            <div>
              <h3 className="font-medium text-sm mb-2">Factures</h3>
              {!invoices || invoices.length === 0 ? (
                <EmptyState
                  Icon={Truck}
                  title="Aucune facture"
                  description="Les factures fournisseur apparaîtront ici."
                  className="py-8"
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>N° facture</TableHead>
                      <TableHead>Échéance</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead className="text-right">Payé</TableHead>
                      <TableHead>Statut</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {invoices.map((inv) => (
                      <TableRow key={inv.id}>
                        <TableCell className="font-mono text-xs">{inv.invoice_number}</TableCell>
                        <TableCell className="text-sm">{formatDate(inv.due_date)}</TableCell>
                        <TableCell className="text-right text-sm">{formatMAD(inv.total_ttc)}</TableCell>
                        <TableCell className="text-right text-sm">{formatMAD(inv.amount_paid)}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              inv.status === "paid"
                                ? "success"
                                : inv.status === "overdue"
                                ? "destructive"
                                : inv.status === "partial"
                                ? "warning"
                                : "secondary"
                            }
                          >
                            {inv.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
