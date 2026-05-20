import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, AlertTriangle, Calendar, Loader2 } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
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
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";
import type { Product, ProductLot } from "@/types/api";

type FilterMode = "all" | "low" | "expiring";

export function StockPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterMode>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [lotProductId, setLotProductId] = useState<string | null>(null);

  const { data: products, isLoading } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products?limit=500").then((r) => r.data),
  });

  const { data: lowStock } = useQuery({
    queryKey: ["alerts", "low-stock"],
    queryFn: () => api.get<Product[]>("/products/alerts/low-stock").then((r) => r.data),
  });

  const { data: expiringLots } = useQuery({
    queryKey: ["alerts", "expiring"],
    queryFn: () =>
      api.get<(ProductLot & { product_id: string })[]>("/products/alerts/expiring?days=180")
        .then((r) => r.data),
  });

  const filtered = useMemo(() => {
    if (!products) return [];
    let list = products;
    if (filter === "low") {
      const lowIds = new Set((lowStock ?? []).map((p) => p.id));
      list = list.filter((p) => lowIds.has(p.id));
    } else if (filter === "expiring") {
      const ids = new Set((expiringLots ?? []).map((l) => l.product_id));
      list = list.filter((p) => ids.has(p.id));
    }
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.code.toLowerCase().includes(q) ||
          (p.dci && p.dci.toLowerCase().includes(q))
      );
    }
    return list;
  }, [products, lowStock, expiringLots, filter, search]);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Stock</h1>
          <p className="text-sm text-muted-foreground">
            {products?.length ?? 0} référence{(products?.length ?? 0) > 1 ? "s" : ""} ·
            {" "}
            {lowStock?.length ?? 0} sous seuil ·
            {" "}
            {expiringLots?.length ?? 0} lot{(expiringLots?.length ?? 0) > 1 ? "s" : ""} bientôt périmé{(expiringLots?.length ?? 0) > 1 ? "s" : ""}
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Nouveau produit
        </Button>
      </header>

      <div className="flex gap-2 flex-wrap">
        <FilterButton active={filter === "all"} onClick={() => setFilter("all")}>
          Tous
        </FilterButton>
        <FilterButton active={filter === "low"} onClick={() => setFilter("low")}>
          <AlertTriangle className="h-3.5 w-3.5" />
          Stock faible
          {lowStock && lowStock.length > 0 && (
            <Badge variant="warning" className="ml-1">{lowStock.length}</Badge>
          )}
        </FilterButton>
        <FilterButton active={filter === "expiring"} onClick={() => setFilter("expiring")}>
          <Calendar className="h-3.5 w-3.5" />
          Péremption proche
          {expiringLots && expiringLots.length > 0 && (
            <Badge variant="destructive" className="ml-1">{expiringLots.length}</Badge>
          )}
        </FilterButton>
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher..."
            className="pl-10"
          />
        </div>
      </div>

      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Nom</TableHead>
              <TableHead>DCI</TableHead>
              <TableHead>Labo</TableHead>
              <TableHead className="text-right">Stock</TableHead>
              <TableHead className="text-right">Prix HT</TableHead>
              <TableHead className="text-right">Prix TTC</TableHead>
              <TableHead className="text-right">Actions</TableHead>
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
                  Aucun produit
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-mono text-xs">{p.code}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium">{p.name}</span>
                      {p.is_prescription_required && (
                        <Badge variant="warning" className="text-[10px]">Ord.</Badge>
                      )}
                      {p.is_psychotropic && (
                        <Badge variant="destructive" className="text-[10px]">Psy.</Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{p.dci ?? "—"}</TableCell>
                  <TableCell className="text-sm">{p.laboratory ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <Badge variant={p.stock_quantity <= p.stock_min ? "warning" : "secondary"}>
                      {p.stock_quantity} / {p.stock_min}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right text-sm">{formatMAD(p.purchase_price_ht)}</TableCell>
                  <TableCell className="text-right font-medium">{formatMAD(p.sale_price_ttc)}</TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="ghost" onClick={() => setLotProductId(p.id)}>
                      Lots
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      <CreateProductDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {
          qc.invalidateQueries({ queryKey: ["products"] });
          qc.invalidateQueries({ queryKey: ["alerts"] });
        }}
      />

      <LotsDialog
        productId={lotProductId}
        product={products?.find((p) => p.id === lotProductId)}
        onClose={() => setLotProductId(null)}
      />
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={onClick}
      className="gap-1.5"
    >
      {children}
    </Button>
  );
}

// ---------- CreateProductDialog ----------
function CreateProductDialog({
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
    dci: "",
    laboratory: "",
    purchase_price_ht: "",
    sale_price_ttc: "",
    stock_min: "10",
    stock_max: "50",
    is_prescription_required: false,
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        purchase_price_ht: form.purchase_price_ht || "0",
        sale_price_ttc: form.sale_price_ttc || "0",
        stock_min: parseInt(form.stock_min) || 0,
        stock_max: parseInt(form.stock_max) || 0,
      };
      const { data } = await api.post("/products", payload);
      return data;
    },
    onSuccess: () => {
      toast.success("Produit créé");
      onCreated();
      onOpenChange(false);
      setForm({
        code: "",
        name: "",
        dci: "",
        laboratory: "",
        purchase_price_ht: "",
        sale_price_ttc: "",
        stock_min: "10",
        stock_max: "50",
        is_prescription_required: false,
      });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau produit</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Code *">
            <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </Field>
          <Field label="Laboratoire">
            <Input
              value={form.laboratory}
              onChange={(e) => setForm({ ...form, laboratory: e.target.value })}
            />
          </Field>
          <Field label="Nom *" colSpan={2}>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="DCI" colSpan={2}>
            <Input value={form.dci} onChange={(e) => setForm({ ...form, dci: e.target.value })} />
          </Field>
          <Field label="Prix achat HT">
            <Input
              type="number"
              step="0.01"
              value={form.purchase_price_ht}
              onChange={(e) => setForm({ ...form, purchase_price_ht: e.target.value })}
            />
          </Field>
          <Field label="Prix vente TTC *">
            <Input
              type="number"
              step="0.01"
              value={form.sale_price_ttc}
              onChange={(e) => setForm({ ...form, sale_price_ttc: e.target.value })}
            />
          </Field>
          <Field label="Stock min">
            <Input
              type="number"
              value={form.stock_min}
              onChange={(e) => setForm({ ...form, stock_min: e.target.value })}
            />
          </Field>
          <Field label="Stock max">
            <Input
              type="number"
              value={form.stock_max}
              onChange={(e) => setForm({ ...form, stock_max: e.target.value })}
            />
          </Field>
          <label className="col-span-2 flex items-center gap-2 cursor-pointer pt-2">
            <input
              type="checkbox"
              checked={form.is_prescription_required}
              onChange={(e) => setForm({ ...form, is_prescription_required: e.target.checked })}
            />
            <span className="text-sm">Ordonnance obligatoire</span>
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!form.code || !form.name || !form.sale_price_ttc || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  children,
  colSpan = 1,
}: {
  label: string;
  children: React.ReactNode;
  colSpan?: 1 | 2;
}) {
  return (
    <div className={colSpan === 2 ? "col-span-2 space-y-1" : "space-y-1"}>
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}

// ---------- LotsDialog ----------
function LotsDialog({
  productId,
  product,
  onClose,
}: {
  productId: string | null;
  product?: Product;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [lotNumber, setLotNumber] = useState("");
  const [quantity, setQuantity] = useState("");
  const [expirationDate, setExpirationDate] = useState("");

  const { data: lots } = useQuery({
    queryKey: ["lots", productId],
    queryFn: () =>
      api.get<ProductLot[]>(`/products/${productId}/lots`).then((r) => r.data),
    enabled: !!productId,
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        product_id: productId,
        lot_number: lotNumber,
        quantity: parseInt(quantity) || 0,
        expiration_date: expirationDate,
      };
      const { data } = await api.post("/products/lots", payload);
      return data;
    },
    onSuccess: () => {
      toast.success("Lot ajouté");
      setLotNumber("");
      setQuantity("");
      setExpirationDate("");
      qc.invalidateQueries({ queryKey: ["lots", productId] });
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={!!productId} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Lots — {product?.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-2 items-end">
            <Field label="N° lot">
              <Input value={lotNumber} onChange={(e) => setLotNumber(e.target.value)} />
            </Field>
            <Field label="Quantité">
              <Input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </Field>
            <Field label="Péremption">
              <Input
                type="date"
                value={expirationDate}
                onChange={(e) => setExpirationDate(e.target.value)}
              />
            </Field>
            <Button
              onClick={() => mutation.mutate()}
              disabled={!lotNumber || !quantity || !expirationDate || mutation.isPending}
            >
              Ajouter
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>N° lot</TableHead>
                <TableHead className="text-right">Quantité</TableHead>
                <TableHead>Péremption</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lots && lots.length > 0 ? (
                lots.map((l) => {
                  const expiry = new Date(l.expiration_date);
                  const daysLeft = Math.floor((expiry.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
                  return (
                    <TableRow key={l.id}>
                      <TableCell className="font-mono">{l.lot_number}</TableCell>
                      <TableCell className="text-right">{l.quantity}</TableCell>
                      <TableCell>
                        <Badge variant={daysLeft < 180 ? "destructive" : "secondary"}>
                          {formatDate(l.expiration_date)}
                          {daysLeft < 365 && ` (${daysLeft}j)`}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-muted-foreground py-6">
                    Aucun lot
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );
}
