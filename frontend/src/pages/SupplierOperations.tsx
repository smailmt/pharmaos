/**
 * Onglets opérationnels fournisseurs : Commandes (BC), Bons de livraison (BL),
 * Factures, Paiements, Retours.
 *
 * Tout le backend existe déjà dans /suppliers/* — ces composants l'exposent au front.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Loader2,
  Trash2,
  PackageCheck,
  FileText,
  Banknote,
  RotateCcw,
  ShoppingCart,
  Send,
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  Download,
  TrendingDown,
  Pencil,
} from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
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

interface SupplierLite {
  id: string;
  name: string;
}
interface ProductLite {
  id: string;
  name: string;
  code: string;
  purchase_price_ht: string;
}

const STATUS_LABELS: Record<string, { label: string; variant: "secondary" | "success" | "warning" | "outline" | "destructive" }> = {
  draft: { label: "Brouillon", variant: "outline" },
  sent: { label: "Envoyé", variant: "secondary" },
  received: { label: "Reçu", variant: "success" },
  partial: { label: "Partiel", variant: "warning" },
  pending: { label: "En attente", variant: "warning" },
  paid: { label: "Payée", variant: "success" },
  cancelled: { label: "Annulé", variant: "outline" },
};

function StatusBadge({ status }: { status: string }) {
  const info = STATUS_LABELS[status] ?? { label: status, variant: "outline" as const };
  return <Badge variant={info.variant} className="text-[10px]">{info.label}</Badge>;
}

// Hook partagé pour charger fournisseurs + produits
function useSuppliersAndProducts() {
  const { data: suppliers } = useQuery({
    queryKey: ["suppliers-lite"],
    queryFn: () => api.get<SupplierLite[]>("/suppliers").then((r) => r.data),
  });
  const { data: products } = useQuery({
    queryKey: ["products-lite"],
    queryFn: () => api.get<ProductLite[]>("/products?limit=500").then((r) => r.data),
  });
  return { suppliers: suppliers ?? [], products: products ?? [] };
}

// =============================================================
// COMMANDES (Bons de commande)
// =============================================================
interface PurchaseOrderItem {
  product_id: string;
  quantity_ordered: number;
  unit_price_ht: string;
}

interface PurchaseOrder {
  id: string;
  order_number: string;
  supplier_id: string;
  order_date: string;
  expected_delivery_date: string | null;
  sent_at: string | null;
  total_ttc: string;
  status: string;
  items: PurchaseOrderItem[];
}

export function OrdersTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editOrder, setEditOrder] = useState<PurchaseOrder | null>(null);
  const { suppliers } = useSuppliersAndProducts();

  const { data: orders, isLoading } = useQuery({
    queryKey: ["purchase-orders"],
    queryFn: () => api.get<PurchaseOrder[]>("/suppliers/orders").then((r) => r.data),
  });

  const sendMutation = useMutation({
    mutationFn: (id: string) => api.post(`/suppliers/orders/${id}/send`),
    onSuccess: () => {
      toast.success("Commande envoyée");
      qc.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/suppliers/orders/${id}`),
    onSuccess: () => {
      toast.success("Commande supprimée");
      qc.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  const supplierName = (id: string) => suppliers.find((s) => s.id === id)?.name ?? "—";

  const refresh = () => qc.invalidateQueries({ queryKey: ["purchase-orders"] });

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Nouvelle commande
        </Button>
      </div>
      <Card>
        {isLoading ? (
          <SkeletonRows />
        ) : !orders || orders.length === 0 ? (
          <EmptyState
            Icon={ShoppingCart}
            title="Aucune commande"
            description="Créez un bon de commande pour vos grossistes ou laboratoires."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>N° commande</TableHead>
                <TableHead>Fournisseur</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Livraison prévue</TableHead>
                <TableHead className="text-right">Total TTC</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((o) => (
                <TableRow key={o.id}>
                  <TableCell className="font-mono text-xs">{o.order_number}</TableCell>
                  <TableCell>{supplierName(o.supplier_id)}</TableCell>
                  <TableCell>{formatDate(o.order_date)}</TableCell>
                  <TableCell>{o.expected_delivery_date ? formatDate(o.expected_delivery_date) : "—"}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(o.total_ttc)}</TableCell>
                  <TableCell><StatusBadge status={o.status} /></TableCell>
                  <TableCell className="text-right">
                    {o.status === "draft" ? (
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setEditOrder(o)}>
                          <Pencil className="h-3.5 w-3.5 mr-1" /> Modifier
                        </Button>
                        <Button size="sm" variant="ghost" className="text-red-500 hover:text-red-700"
                          onClick={() => { if (confirm("Supprimer cette commande ?")) deleteMutation.mutate(o.id); }}>
                          <Trash2 className="h-3.5 w-3.5 mr-1" /> Supprimer
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => sendMutation.mutate(o.id)}>
                          <Send className="h-3.5 w-3.5 mr-1" /> Envoyer
                        </Button>
                      </div>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreateOrderDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => {
        setCreateOpen(false);
        refresh();
      }} />

      {editOrder && (
        <EditOrderDialog
          order={editOrder}
          onClose={() => setEditOrder(null)}
          onSaved={() => { setEditOrder(null); refresh(); }}
        />
      )}
    </div>
  );
}

function CreateOrderDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { suppliers, products } = useSuppliersAndProducts();
  const [supplierId, setSupplierId] = useState("");
  const [lines, setLines] = useState<Array<{ product_id: string; quantity_ordered: number; unit_price_ht: string }>>([]);

  const addLine = () => setLines([...lines, { product_id: "", quantity_ordered: 1, unit_price_ht: "0" }]);
  const updateLine = (i: number, patch: Partial<(typeof lines)[number]>) =>
    setLines(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const removeLine = (i: number) => setLines(lines.filter((_, idx) => idx !== i));

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/suppliers/orders", {
        supplier_id: supplierId,
        items: lines.map((l) => ({
          product_id: l.product_id,
          quantity_ordered: l.quantity_ordered,
          unit_price_ht: parseFloat(l.unit_price_ht || "0").toFixed(4),
          discount_rate: "0",
          vat_rate: "0.07",
        })),
      }),
    onSuccess: () => {
      toast.success("Commande créée");
      setSupplierId("");
      setLines([]);
      onCreated();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle commande</DialogTitle>
          <DialogDescription>Créer un bon de commande fournisseur.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Fournisseur</Label>
            <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
              <option value="">— Choisir —</option>
              {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <Label>Produits</Label>
              <Button size="sm" variant="outline" onClick={addLine}><Plus className="h-3 w-3 mr-1" /> Ligne</Button>
            </div>
            {lines.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-2">Aucune ligne. Cliquez "Ligne" pour ajouter un produit.</p>
            ) : (
              <div className="space-y-2">
                {lines.map((line, i) => (
                  <div key={i} className="flex gap-2 items-end">
                    <div className="flex-1">
                      <select
                        value={line.product_id}
                        onChange={(e) => {
                          const p = products.find((x) => x.id === e.target.value);
                          updateLine(i, { product_id: e.target.value, unit_price_ht: p?.purchase_price_ht ?? "0" });
                        }}
                        className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                      >
                        <option value="">— Produit —</option>
                        {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </div>
                    <div className="w-20">
                      <Input type="number" value={line.quantity_ordered} min={1}
                        onChange={(e) => updateLine(i, { quantity_ordered: parseInt(e.target.value || "1") })}
                        placeholder="Qté" />
                    </div>
                    <div className="w-28">
                      <Input type="number" step="0.01" value={line.unit_price_ht}
                        onChange={(e) => updateLine(i, { unit_price_ht: e.target.value })}
                        placeholder="PA HT" />
                    </div>
                    <Button size="icon" variant="ghost" onClick={() => removeLine(i)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={!supplierId || lines.length === 0 || lines.some((l) => !l.product_id) || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Créer la commande
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditOrderDialog({ order, onClose, onSaved }: { order: PurchaseOrder; onClose: () => void; onSaved: () => void }) {
  const { products } = useSuppliersAndProducts();
  const [lines, setLines] = useState<Array<{ product_id: string; quantity_ordered: number; unit_price_ht: string }>>(
    order.items.map((it) => ({
      product_id: it.product_id,
      quantity_ordered: it.quantity_ordered,
      unit_price_ht: String(it.unit_price_ht),
    }))
  );

  const addLine = () => setLines([...lines, { product_id: "", quantity_ordered: 1, unit_price_ht: "0" }]);
  const updateLine = (i: number, patch: Partial<(typeof lines)[number]>) =>
    setLines(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const removeLine = (i: number) => setLines(lines.filter((_, idx) => idx !== i));

  const mutation = useMutation({
    mutationFn: () =>
      api.put(`/suppliers/orders/${order.id}`, {
        items: lines.map((l) => ({
          product_id: l.product_id,
          quantity_ordered: l.quantity_ordered,
          unit_price_ht: parseFloat(l.unit_price_ht || "0").toFixed(4),
          discount_rate: "0",
          vat_rate: "0.07",
        })),
      }),
    onSuccess: () => {
      toast.success("Commande mise à jour");
      onSaved();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Modifier la commande {order.order_number}</DialogTitle>
          <DialogDescription>Modifiez les lignes de ce bon de commande (brouillon).</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label>Produits</Label>
              <Button size="sm" variant="outline" onClick={addLine}><Plus className="h-3 w-3 mr-1" /> Ligne</Button>
            </div>
            {lines.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-2">Aucune ligne. Cliquez "Ligne" pour ajouter un produit.</p>
            ) : (
              <div className="space-y-2">
                {lines.map((line, i) => (
                  <div key={i} className="flex gap-2 items-end">
                    <div className="flex-1">
                      <select
                        value={line.product_id}
                        onChange={(e) => {
                          const p = products.find((x) => x.id === e.target.value);
                          updateLine(i, { product_id: e.target.value, unit_price_ht: p?.purchase_price_ht ?? "0" });
                        }}
                        className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                      >
                        <option value="">— Produit —</option>
                        {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </div>
                    <div className="w-20">
                      <Input type="number" value={line.quantity_ordered} min={1}
                        onChange={(e) => updateLine(i, { quantity_ordered: parseInt(e.target.value || "1") })}
                        placeholder="Qté" />
                    </div>
                    <div className="w-28">
                      <Input type="number" step="0.01" value={line.unit_price_ht}
                        onChange={(e) => updateLine(i, { unit_price_ht: e.target.value })}
                        placeholder="PA HT" />
                    </div>
                    <Button size="icon" variant="ghost" onClick={() => removeLine(i)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={lines.length === 0 || lines.some((l) => !l.product_id) || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================
// BONS DE LIVRAISON (BL)
// =============================================================
interface DeliveryNote {
  id: string;
  delivery_number: string;
  supplier_id: string;
  delivery_date: string;
  total_ttc: string;
  has_discrepancies: boolean;
  status: string;
}

export function DeliveriesTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const { suppliers } = useSuppliersAndProducts();

  const { data: deliveries, isLoading } = useQuery({
    queryKey: ["deliveries"],
    queryFn: () => api.get<DeliveryNote[]>("/suppliers/deliveries").then((r) => r.data),
  });

  const supplierName = (id: string) => suppliers.find((s) => s.id === id)?.name ?? "—";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Réceptionner un bon de livraison incrémente automatiquement le stock.
        </p>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Réceptionner un BL
        </Button>
      </div>
      <Card>
        {isLoading ? (
          <SkeletonRows />
        ) : !deliveries || deliveries.length === 0 ? (
          <EmptyState
            Icon={PackageCheck}
            title="Aucun bon de livraison"
            description="Réceptionnez vos livraisons pour mettre à jour le stock."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>N° BL</TableHead>
                <TableHead>Fournisseur</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="text-right">Total TTC</TableHead>
                <TableHead>Écarts</TableHead>
                <TableHead>Statut</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {deliveries.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="font-mono text-xs">{d.delivery_number}</TableCell>
                  <TableCell>{supplierName(d.supplier_id)}</TableCell>
                  <TableCell>{formatDate(d.delivery_date)}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(d.total_ttc)}</TableCell>
                  <TableCell>
                    {d.has_discrepancies ? (
                      <Badge variant="warning" className="text-[10px]">
                        <AlertTriangle className="h-3 w-3 mr-0.5" /> Écarts
                      </Badge>
                    ) : (
                      <Badge variant="success" className="text-[10px]">
                        <CheckCircle2 className="h-3 w-3 mr-0.5" /> Conforme
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell><StatusBadge status={d.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <ReceiveDeliveryDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => {
        setCreateOpen(false);
        qc.invalidateQueries({ queryKey: ["deliveries"] });
        qc.invalidateQueries({ queryKey: ["products"] });
      }} />
    </div>
  );
}

function ReceiveDeliveryDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { suppliers, products } = useSuppliersAndProducts();
  const [supplierId, setSupplierId] = useState("");
  const [deliveryNumber, setDeliveryNumber] = useState("");
  const [lines, setLines] = useState<Array<{
    product_id: string; quantity_received: number; unit_price_ht: string;
    lot_number: string; expiration_date: string; sale_price_ttc: string;
  }>>([]);

  const addLine = () => setLines([...lines, { product_id: "", quantity_received: 1, unit_price_ht: "0", lot_number: "", expiration_date: "", sale_price_ttc: "" }]);
  const updateLine = (i: number, patch: Partial<(typeof lines)[number]>) =>
    setLines(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const removeLine = (i: number) => setLines(lines.filter((_, idx) => idx !== i));

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/suppliers/deliveries", {
        supplier_id: supplierId,
        delivery_number: deliveryNumber,
        items: lines.map((l) => ({
          product_id: l.product_id,
          quantity_ordered: l.quantity_received,
          quantity_received: l.quantity_received,
          unit_price_ht: parseFloat(l.unit_price_ht || "0").toFixed(4),
          discount_rate: "0",
          vat_rate: "0.07",
          lot_number: l.lot_number || null,
          expiration_date: l.expiration_date || null,
          sale_price_ttc: l.sale_price_ttc ? parseFloat(l.sale_price_ttc).toFixed(4) : null,
        })),
      }),
    onSuccess: () => {
      toast.success("BL réceptionné", "Le stock a été mis à jour.");
      setSupplierId(""); setDeliveryNumber(""); setLines([]);
      onCreated();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Réceptionner un bon de livraison</DialogTitle>
          <DialogDescription>Le stock sera incrémenté automatiquement à la validation.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Fournisseur</Label>
              <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
                <option value="">— Choisir —</option>
                {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Label>N° du BL</Label>
              <Input value={deliveryNumber} onChange={(e) => setDeliveryNumber(e.target.value)} placeholder="Ex: BL-2026-0042" />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <Label>Produits reçus</Label>
              <Button size="sm" variant="outline" onClick={addLine}><Plus className="h-3 w-3 mr-1" /> Ligne</Button>
            </div>
            {lines.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-2">Ajoutez les produits reçus avec leur lot et péremption.</p>
            ) : (
              <div className="space-y-2">
                {lines.map((line, i) => (
                  <div key={i} className="grid grid-cols-12 gap-2 items-end border-b pb-2">
                    <div className="col-span-3">
                      <Label className="text-[10px]">Produit</Label>
                      <select value={line.product_id}
                        onChange={(e) => {
                          const p = products.find((x) => x.id === e.target.value);
                          updateLine(i, { product_id: e.target.value, unit_price_ht: p?.purchase_price_ht ?? "0" });
                        }}
                        className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm">
                        <option value="">—</option>
                        {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </div>
                    <div className="col-span-1">
                      <Label className="text-[10px]">Qté</Label>
                      <Input type="number" min={1} value={line.quantity_received}
                        onChange={(e) => updateLine(i, { quantity_received: parseInt(e.target.value || "1") })} />
                    </div>
                    <div className="col-span-2">
                      <Label className="text-[10px]">PA HT</Label>
                      <Input type="number" step="0.01" value={line.unit_price_ht}
                        onChange={(e) => updateLine(i, { unit_price_ht: e.target.value })} />
                    </div>
                    <div className="col-span-2">
                      <Label className="text-[10px]">PPV (boîte)</Label>
                      <Input type="number" step="0.01" value={line.sale_price_ttc}
                        onChange={(e) => updateLine(i, { sale_price_ttc: e.target.value })}
                        placeholder="auto" />
                    </div>
                    <div className="col-span-2">
                      <Label className="text-[10px]">Lot</Label>
                      <Input value={line.lot_number}
                        onChange={(e) => updateLine(i, { lot_number: e.target.value })} placeholder="Lot" />
                    </div>
                    <div className="col-span-1">
                      <Label className="text-[10px]">Périm.</Label>
                      <Input type="date" value={line.expiration_date}
                        onChange={(e) => updateLine(i, { expiration_date: e.target.value })} />
                    </div>
                    <div className="col-span-1">
                      <Button size="icon" variant="ghost" onClick={() => removeLine(i)}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={!supplierId || !deliveryNumber || lines.length === 0 || lines.some((l) => !l.product_id) || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Valider la réception
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================
// FACTURES
// =============================================================
interface SupplierInvoice {
  id: string;
  invoice_number: string;
  supplier_id: string;
  invoice_date: string;
  due_date: string | null;
  total_ttc: string;
  amount_paid: string;
  status: string;
}

export function InvoicesTab() {
  const qc = useQueryClient();
  const { suppliers } = useSuppliersAndProducts();

  const { data: invoices, isLoading } = useQuery({
    queryKey: ["supplier-invoices"],
    queryFn: () => api.get<SupplierInvoice[]>("/suppliers/invoices").then((r) => r.data),
  });

  const supplierName = (id: string) => suppliers.find((s) => s.id === id)?.name ?? "—";

  return (
    <div className="space-y-4">
      <Card>
        {isLoading ? (
          <SkeletonRows />
        ) : !invoices || invoices.length === 0 ? (
          <EmptyState
            Icon={FileText}
            title="Aucune facture"
            description="Les factures fournisseur enregistrées apparaîtront ici."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>N° facture</TableHead>
                <TableHead>Fournisseur</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Échéance</TableHead>
                <TableHead className="text-right">Total TTC</TableHead>
                <TableHead className="text-right">Payé</TableHead>
                <TableHead>Statut</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell className="font-mono text-xs">{inv.invoice_number}</TableCell>
                  <TableCell>{supplierName(inv.supplier_id)}</TableCell>
                  <TableCell>{formatDate(inv.invoice_date)}</TableCell>
                  <TableCell>{inv.due_date ? formatDate(inv.due_date) : "—"}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(inv.total_ttc)}</TableCell>
                  <TableCell className="text-right text-muted-foreground">{formatMAD(inv.amount_paid)}</TableCell>
                  <TableCell><StatusBadge status={inv.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
      <p className="text-xs text-muted-foreground">
        Astuce : créez les factures à partir des BL reçus (lien BL → facture géré côté serveur).
      </p>
    </div>
  );
}

// =============================================================
// PAIEMENTS
// =============================================================
interface SupplierPayment {
  id: string;
  supplier_id: string;
  payment_date: string;
  amount: string;
  payment_method: string;
  reference: string | null;
}

export function PaymentsTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const { suppliers } = useSuppliersAndProducts();

  const { data: payments, isLoading } = useQuery({
    queryKey: ["supplier-payments"],
    queryFn: () => api.get<SupplierPayment[]>("/suppliers/payments").then((r) => r.data),
  });

  const supplierName = (id: string) => suppliers.find((s) => s.id === id)?.name ?? "—";

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
          <EmptyState
            Icon={Banknote}
            title="Aucun paiement"
            description="Enregistrez vos règlements fournisseur."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Fournisseur</TableHead>
                <TableHead>Méthode</TableHead>
                <TableHead>Référence</TableHead>
                <TableHead className="text-right">Montant</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{formatDate(p.payment_date)}</TableCell>
                  <TableCell>{supplierName(p.supplier_id)}</TableCell>
                  <TableCell className="text-sm">{p.payment_method}</TableCell>
                  <TableCell className="text-xs font-mono">{p.reference || "—"}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(p.amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreatePaymentDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => {
        setCreateOpen(false);
        qc.invalidateQueries({ queryKey: ["supplier-payments"] });
      }} />
    </div>
  );
}

function CreatePaymentDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const { suppliers } = useSuppliersAndProducts();
  const [supplierId, setSupplierId] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("transfer");
  const [reference, setReference] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/suppliers/payments", {
        supplier_id: supplierId,
        amount: parseFloat(amount || "0").toFixed(2),
        payment_method: method,
        reference: reference || null,
      }),
    onSuccess: () => {
      toast.success("Paiement enregistré");
      setSupplierId(""); setAmount(""); setReference("");
      onCreated();
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Enregistrer un paiement</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Fournisseur</Label>
            <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
              <option value="">— Choisir —</option>
              {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Montant (MAD)</Label>
              <Input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Méthode</Label>
              <select value={method} onChange={(e) => setMethod(e.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
                <option value="cash">Espèces</option>
                <option value="transfer">Virement</option>
                <option value="check">Chèque</option>
                <option value="card">Carte</option>
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Référence (optionnel)</Label>
            <Input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="N° chèque, réf virement…" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={!supplierId || !amount || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================
// RETOURS
// =============================================================
interface SupplierReturn {
  id: string;
  return_number: string;
  supplier_id: string;
  return_date: string;
  reason: string;
  total_amount: string;
  credit_note_received: boolean;
  status: string;
}

export function ReturnsTab() {
  const { suppliers } = useSuppliersAndProducts();

  const { data: returns, isLoading } = useQuery({
    queryKey: ["supplier-returns"],
    queryFn: () => api.get<SupplierReturn[]>("/suppliers/returns").then((r) => r.data),
  });

  const supplierName = (id: string) => suppliers.find((s) => s.id === id)?.name ?? "—";

  return (
    <div className="space-y-4">
      <Card>
        {isLoading ? (
          <SkeletonRows />
        ) : !returns || returns.length === 0 ? (
          <EmptyState
            Icon={RotateCcw}
            title="Aucun retour"
            description="Les retours fournisseur (périmés, casse, erreurs) apparaîtront ici."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>N° retour</TableHead>
                <TableHead>Fournisseur</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Motif</TableHead>
                <TableHead className="text-right">Montant</TableHead>
                <TableHead>Avoir reçu</TableHead>
                <TableHead>Statut</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {returns.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{r.return_number}</TableCell>
                  <TableCell>{supplierName(r.supplier_id)}</TableCell>
                  <TableCell>{formatDate(r.return_date)}</TableCell>
                  <TableCell className="text-sm">{r.reason}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(r.total_amount)}</TableCell>
                  <TableCell>
                    {r.credit_note_received ? (
                      <Badge variant="success" className="text-[10px]">Reçu</Badge>
                    ) : (
                      <Badge variant="warning" className="text-[10px]">En attente</Badge>
                    )}
                  </TableCell>
                  <TableCell><StatusBadge status={r.status} /></TableCell>
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
// Helper
// =============================================================
function SkeletonRows() {
  return (
    <div className="p-4 space-y-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

// =============================================================
// PROPOSITION DE COMMANDE
// =============================================================
interface ProposalItem {
  product_id: string;
  product_name: string;
  product_code: string;
  pph: string;
  ppv: string;
  qty_sold: number;
  current_stock: number;
  suggested_quantity: number;
}
interface ProposalResult {
  mode: string;
  count: number;
  total_pph: string;
  total_ppv: string;
  items: ProposalItem[];
}

export function ProposalTab() {
  const qc = useQueryClient();
  const { suppliers } = useSuppliersAndProducts();
  const [mode, setMode] = useState<"sales" | "minmax">("sales");
  const [supplierId, setSupplierId] = useState("");
  const [days, setDays] = useState("30");
  const [qtys, setQtys] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  const { data, refetch, isFetching } = useQuery({
    queryKey: ["proposal", mode, supplierId, days],
    queryFn: () => {
      const params = new URLSearchParams({ mode });
      if (supplierId) params.set("supplier_id", supplierId);
      if (mode === "sales") params.set("days", days);
      return api.get<ProposalResult>(`/suppliers/purchase-proposals?${params}`).then((r) => {
        const q: Record<string, number> = {};
        const s: Record<string, boolean> = {};
        r.data.items.forEach((it) => {
          q[it.product_id] = it.suggested_quantity;
          s[it.product_id] = true;
        });
        setQtys(q);
        setSelected(s);
        return r.data;
      });
    },
    enabled: false,
  });

  const items = data?.items ?? [];
  const selectedItems = items.filter((i) => selected[i.product_id] && (qtys[i.product_id] ?? 0) > 0);
  const totalPPH = selectedItems.reduce((s, i) => s + parseFloat(i.pph) * (qtys[i.product_id] ?? 0), 0);

  const generateMutation = useMutation({
    mutationFn: () => {
      if (!supplierId) throw new Error("Choisissez un fournisseur pour générer le bon de commande.");
      return api.post("/suppliers/orders", {
        supplier_id: supplierId,
        items: selectedItems.map((i) => ({
          product_id: i.product_id,
          quantity_ordered: qtys[i.product_id] ?? 0,
          unit_price_ht: parseFloat(i.pph || "0").toFixed(4),
          discount_rate: "0",
          vat_rate: "0.07",
        })),
      });
    },
    onSuccess: () => {
      toast.success("Bon de commande créé", "Retrouvez-le dans l'onglet Commandes.");
      qc.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  const exportCSV = () => {
    const header = ["Code", "Produit", "PPH", "PPV", "Vendu", "Stock", "Qte commandee"];
    const rows = selectedItems.map((i) => [
      i.product_code, i.product_name, i.pph, i.ppv, i.qty_sold, i.current_stock, qtys[i.product_id] ?? 0,
    ]);
    const csv = [header, ...rows].map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `proposition_commande_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 rounded-md p-3 text-xs text-blue-900">
        Proposition d'achat intelligente : basée sur vos ventes ou vos seuils de stock. Ajustez les quantités, puis générez le bon de commande.
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Mode</Label>
            <div className="flex gap-1">
              <button onClick={() => setMode("sales")}
                className={`px-3 py-1.5 rounded-md text-sm border-2 ${mode === "sales" ? "border-primary bg-primary/5 text-primary" : "border-input"}`}>
                <TrendingDown className="h-3.5 w-3.5 inline mr-1" />Par ventes
              </button>
              <button onClick={() => setMode("minmax")}
                className={`px-3 py-1.5 rounded-md text-sm border-2 ${mode === "minmax" ? "border-primary bg-primary/5 text-primary" : "border-input"}`}>
                <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />Sous le minimum
              </button>
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Fournisseur</Label>
            <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm">
              <option value="">Tous (catalogue non filtré)</option>
              {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          {mode === "sales" && (
            <div className="space-y-1">
              <Label className="text-xs">Période (jours)</Label>
              <select value={days} onChange={(e) => setDays(e.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm">
                <option value="7">7 derniers jours</option>
                <option value="30">30 derniers jours</option>
                <option value="60">60 derniers jours</option>
                <option value="90">90 derniers jours</option>
              </select>
            </div>
          )}
          <Button onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Lightbulb className="h-4 w-4 mr-1" />}
            Calculer la proposition
          </Button>
        </div>
      </Card>

      {data && (
        <Card>
          {items.length === 0 ? (
            <EmptyState Icon={CheckCircle2} title="Rien à commander"
              description={mode === "sales" ? "Aucune vente sur la période, ou stock suffisant." : "Tous les produits sont au-dessus de leur seuil minimum."} />
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8"></TableHead>
                      <TableHead>Produit</TableHead>
                      <TableHead className="text-right">PPH</TableHead>
                      <TableHead className="text-right">PPV</TableHead>
                      {mode === "sales" && <TableHead className="text-right">Vendu</TableHead>}
                      <TableHead className="text-right">Stock</TableHead>
                      <TableHead className="text-right w-28">Qté à commander</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((it) => (
                      <TableRow key={it.product_id} className={!selected[it.product_id] ? "opacity-40" : ""}>
                        <TableCell>
                          <input type="checkbox" checked={selected[it.product_id] ?? false}
                            onChange={(e) => setSelected({ ...selected, [it.product_id]: e.target.checked })} />
                        </TableCell>
                        <TableCell>
                          <p className="font-medium text-sm">{it.product_name}</p>
                          <p className="text-xs text-muted-foreground font-mono">{it.product_code}</p>
                        </TableCell>
                        <TableCell className="text-right">{formatMAD(it.pph)}</TableCell>
                        <TableCell className="text-right">{formatMAD(it.ppv)}</TableCell>
                        {mode === "sales" && <TableCell className="text-right">{it.qty_sold}</TableCell>}
                        <TableCell className="text-right">
                          <span className={it.current_stock <= 0 ? "text-red-600 font-medium" : ""}>{it.current_stock}</span>
                        </TableCell>
                        <TableCell className="text-right">
                          <Input type="number" min={0} value={qtys[it.product_id] ?? 0}
                            onChange={(e) => setQtys({ ...qtys, [it.product_id]: parseInt(e.target.value || "0") })}
                            className="h-8 w-20 text-right ml-auto" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="p-4 border-t flex flex-wrap items-center justify-between gap-3 bg-slate-50">
                <div className="text-sm">
                  <span className="text-muted-foreground">Total commande (PPH) : </span>
                  <span className="font-bold text-lg">{formatMAD(totalPPH)}</span>
                  <span className="text-muted-foreground ml-2">· {selectedItems.length} produit(s)</span>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={exportCSV} disabled={selectedItems.length === 0}>
                    <Download className="h-4 w-4 mr-1" /> Export Excel/CSV
                  </Button>
                  <Button onClick={() => generateMutation.mutate()}
                    disabled={!supplierId || selectedItems.length === 0 || generateMutation.isPending}>
                    {generateMutation.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                    <ShoppingCart className="h-4 w-4 mr-1" /> Générer le bon de commande
                  </Button>
                </div>
              </div>
              {!supplierId && (
                <p className="px-4 pb-3 text-xs text-amber-600">
                  Choisissez un fournisseur ci-dessus pour pouvoir générer le bon de commande.
                </p>
              )}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
