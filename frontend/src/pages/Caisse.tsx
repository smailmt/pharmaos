import { useState, useMemo, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, X, Trash2, Plus, Minus, Loader2, ScanLine, Camera, FileImage, ShieldAlert } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD, cn } from "@/lib/utils";
import { useCart } from "@/stores/cart";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";
import { BarcodeScanner } from "@/components/BarcodeScanner";
import { PrescriptionOCRDialog } from "@/components/PrescriptionOCRDialog";
import { DrugInteractionsDialog } from "@/components/DrugInteractionsDialog";
import type { Product, Client, ThirdPartyPayer, Sale } from "@/types/api";

export function CaissePage() {
  const qc = useQueryClient();
  const cart = useCart();
  const [search, setSearch] = useState("");
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [interactionsOpen, setInteractionsOpen] = useState(false);
  const [lastSale, setLastSale] = useState<Sale | null>(null);
  const [scannerOpen, setScannerOpen] = useState(false);
  const [ocrOpen, setOcrOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: async () => {
      try {
        const { data } = await api.get<Product[]>("/products?limit=200");
        // Cache pour mode offline
        const { cacheProducts } = await import("@/lib/offline-db");
        cacheProducts(data).catch(() => undefined);
        return data;
      } catch (err) {
        // Si offline, tomber sur le cache
        const { getCachedProducts } = await import("@/lib/offline-db");
        const cached = await getCachedProducts();
        if (cached.length > 0) return cached;
        throw err;
      }
    },
  });

  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<Client[]>("/clients").then((r) => r.data),
  });

  const { data: payers } = useQuery({
    queryKey: ["payers"],
    queryFn: () => api.get<ThirdPartyPayer[]>("/third-party/payers").then((r) => r.data),
  });

  const filteredProducts = useMemo(() => {
    if (!products) return [];
    const q = search.trim().toLowerCase();
    if (!q) return products.slice(0, 30);
    return products
      .filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.code.toLowerCase().includes(q) ||
          (p.barcode && p.barcode.includes(q)) ||
          (p.dci && p.dci.toLowerCase().includes(q))
      )
      .slice(0, 30);
  }, [products, search]);

  // Raccourci F2 pour focus la recherche
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "F2") {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const selectedClient = clients?.find((c) => c.id === cart.clientId);

  const total = cart.total();
  const totalItems = cart.items.reduce((s, i) => s + i.quantity, 0);

  return (
    <div className="h-full flex flex-col lg:flex-row">
      {/* Colonne gauche : produits */}
      <div className="flex-1 flex flex-col p-4 sm:p-6 gap-4 min-w-0">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Caisse</h1>
          <p className="text-sm text-muted-foreground">
            Recherchez, scannez ou photographiez une ordonnance.{" "}
            <kbd className="px-1.5 py-0.5 rounded bg-muted text-xs hidden sm:inline">F2</kbd>
            <span className="hidden sm:inline"> pour focus.</span>
          </p>
        </div>

        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              ref={searchInputRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Nom, code, DCI…"
              className="pl-10"
              autoFocus
            />
          </div>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setScannerOpen(true)}
            title="Scanner code-barres"
            aria-label="Scanner un code-barres"
          >
            <Camera className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setOcrOpen(true)}
            title="Photo d'ordonnance (IA)"
            aria-label="Photo d'ordonnance"
          >
            <FileImage className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto -mx-2 px-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredProducts.map((p) => {
              const lowStock = p.stock_quantity <= p.stock_min;
              return (
                <button
                  key={p.id}
                  onClick={() => {
                    if (p.stock_quantity <= 0) {
                      toast.error("Stock épuisé", p.name);
                      return;
                    }
                    cart.addProduct(p);
                  }}
                  disabled={p.stock_quantity <= 0}
                  className={cn(
                    "text-left p-3 rounded-lg border bg-card hover:border-primary hover:shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  )}
                >
                  <div className="flex justify-between items-start gap-2 mb-1.5">
                    <p className="font-medium text-sm leading-tight line-clamp-2">{p.name}</p>
                    {p.is_prescription_required && (
                      <Badge variant="warning" className="shrink-0 text-[10px]">Ord.</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground truncate">
                    {p.dci ?? "—"} · {p.code}
                  </p>
                  <div className="flex justify-between items-center mt-2">
                    <span className="text-base font-semibold">{formatMAD(p.sale_price_ttc)}</span>
                    <Badge variant={lowStock ? "warning" : "secondary"} className="text-[10px]">
                      Stock {p.stock_quantity}
                    </Badge>
                  </div>
                </button>
              );
            })}
            {filteredProducts.length === 0 && (
              <p className="col-span-full text-sm text-muted-foreground text-center py-10">
                Aucun produit trouvé
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Colonne droite : panier */}
      <div className="w-[420px] bg-card border-l flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold">Panier</h2>
            <Badge variant="secondary">{totalItems} article{totalItems > 1 ? "s" : ""}</Badge>
          </div>

          {/* Client */}
          <div className="space-y-2">
            <Label className="text-xs">Client</Label>
            <select
              value={cart.clientId ?? ""}
              onChange={(e) => cart.setClient(e.target.value || null)}
              className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">— Client de passage —</option>
              {clients?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name}
                  {c.credit_enabled ? " (crédit OK)" : ""}
                </option>
              ))}
            </select>
            {selectedClient?.third_party_payer_id && (
              <p className="text-xs text-muted-foreground">
                Tiers payant assigné : {payers?.find((p) => p.id === selectedClient.third_party_payer_id)?.code}
              </p>
            )}
          </div>
        </div>

        {/* Items */}
        <div className="flex-1 overflow-y-auto">
          {cart.items.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 text-center">
              <ScanLine className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm">Panier vide.</p>
              <p className="text-xs mt-1">Cliquez sur un produit pour l'ajouter.</p>
            </div>
          ) : (
            <ul className="divide-y">
              {cart.items.map((item) => (
                <li key={item.product.id} className="p-3 hover:bg-muted/30">
                  <div className="flex justify-between items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm leading-tight">{item.product.name}</p>
                      <p className="text-xs text-muted-foreground">{item.product.code}</p>
                    </div>
                    <button
                      onClick={() => cart.removeItem(item.product.id)}
                      className="text-muted-foreground hover:text-destructive"
                      aria-label="Retirer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  <div className="flex items-center gap-2 mt-2">
                    <div className="flex items-center border rounded-md">
                      <button
                        onClick={() => cart.updateQuantity(item.product.id, item.quantity - 1)}
                        className="px-2 py-1 hover:bg-muted text-sm"
                      >
                        <Minus className="h-3 w-3" />
                      </button>
                      <span className="px-3 text-sm font-medium min-w-[2rem] text-center">
                        {item.quantity}
                      </span>
                      <button
                        onClick={() => {
                          if (item.quantity >= item.product.stock_quantity) {
                            toast.error("Stock insuffisant", `Stock disponible : ${item.product.stock_quantity}`);
                            return;
                          }
                          cart.updateQuantity(item.product.id, item.quantity + 1);
                        }}
                        className="px-2 py-1 hover:bg-muted text-sm"
                      >
                        <Plus className="h-3 w-3" />
                      </button>
                    </div>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={item.unit_price_ttc.toFixed(2)}
                      onChange={(e) => cart.updatePrice(item.product.id, parseFloat(e.target.value) || 0)}
                      className="h-8 w-24 text-sm text-right"
                    />
                    <span className="text-sm font-semibold ml-auto whitespace-nowrap">
                      {formatMAD(item.quantity * item.unit_price_ttc * (1 - item.discount_rate))}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Total + actions */}
        <div className="p-4 border-t bg-muted/20 space-y-3">
          <div className="flex justify-between text-2xl font-bold">
            <span>Total</span>
            <span className="text-primary">{formatMAD(total)}</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" onClick={cart.clear} disabled={cart.items.length === 0}>
              <X className="h-4 w-4 mr-1" />
              Annuler
            </Button>
            <Button
              onClick={() => setPaymentOpen(true)}
              disabled={cart.items.length === 0}
            >
              Encaisser
            </Button>
          </div>
          {cart.items.length >= 2 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setInteractionsOpen(true)}
              className="w-full text-xs"
            >
              <ShieldAlert className="h-3.5 w-3.5 mr-1 text-primary" />
              Vérifier les interactions ({cart.items.length})
            </Button>
          )}
        </div>
      </div>

      {/* Dialog interactions médicamenteuses */}
      <DrugInteractionsDialog
        open={interactionsOpen}
        onClose={() => setInteractionsOpen(false)}
        medications={cart.items.map((i) => i.product.dci || i.product.name)}
      />

      {/* Dialog paiement */}
      <PaymentDialog
        open={paymentOpen}
        onOpenChange={setPaymentOpen}
        onSuccess={(sale) => {
          setPaymentOpen(false);
          setLastSale(sale);
          cart.clear();
          qc.invalidateQueries({ queryKey: ["products"] });
          qc.invalidateQueries({ queryKey: ["clients"] });
        }}
      />

      {/* Dialog reçu */}
      <ReceiptDialog
        sale={lastSale}
        onClose={() => setLastSale(null)}
        productsById={Object.fromEntries((products ?? []).map((p) => [p.id, p]))}
      />

      {/* Scanner code-barres */}
      <BarcodeScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onScan={(code) => {
          // Chercher le produit par code-barres ou code
          const found = products?.find(
            (p) => p.barcode === code || p.code === code
          );
          if (found) {
            if (found.stock_quantity <= 0) {
              toast.error("Stock épuisé", found.name);
            } else {
              cart.addProduct(found);
              toast.success("Ajouté au panier", found.name);
            }
          } else {
            toast.error("Produit introuvable", `Code : ${code}`);
            setSearch(code); // pré-remplir la recherche pour aider
          }
        }}
      />

      {/* OCR ordonnance */}
      <PrescriptionOCRDialog
        open={ocrOpen}
        onClose={() => setOcrOpen(false)}
        products={products ?? []}
        onAddLines={(productIds) => {
          let added = 0;
          for (const pid of productIds) {
            const p = products?.find((x) => x.id === pid);
            if (p && p.stock_quantity > 0) {
              cart.addProduct(p);
              added++;
            }
          }
          if (added > 0) {
            toast.success(`${added} médicament${added > 1 ? "s" : ""} ajouté${added > 1 ? "s" : ""} au panier`);
          }
        }}
      />
    </div>
  );
}

// ---------- PaymentDialog ----------
function PaymentDialog({
  open,
  onOpenChange,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSuccess: (sale: Sale) => void;
}) {
  const cart = useCart();
  const total = cart.total();
  const [paidCash, setPaidCash] = useState("");
  const [paidCard, setPaidCard] = useState("");
  const [paidCheck, setPaidCheck] = useState("");
  const [paidCredit, setPaidCredit] = useState("");

  useEffect(() => {
    if (open) {
      // Reset puis pré-remplit cash avec le total
      setPaidCash(total.toFixed(2));
      setPaidCard("");
      setPaidCheck("");
      setPaidCredit("");
    }
  }, [open, total]);

  const sumPaid =
    (parseFloat(paidCash) || 0) +
    (parseFloat(paidCard) || 0) +
    (parseFloat(paidCheck) || 0) +
    (parseFloat(paidCredit) || 0);

  const rendu = sumPaid - total;
  const insuffisant = sumPaid + 0.001 < total;

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        client_id: cart.clientId,
        has_prescription: cart.hasPrescription,
        prescription_number: cart.prescriptionNumber,
        third_party_payer_id: cart.thirdPartyPayerId,
        items: cart.items.map((i) => ({
          product_id: i.product.id,
          quantity: i.quantity,
          unit_price_ttc: i.unit_price_ttc.toFixed(4),
          discount_rate: i.discount_rate.toFixed(4),
        })),
        paid_cash: (parseFloat(paidCash) || 0).toFixed(2),
        paid_card: (parseFloat(paidCard) || 0).toFixed(2),
        paid_check: (parseFloat(paidCheck) || 0).toFixed(2),
        paid_credit: (parseFloat(paidCredit) || 0).toFixed(2),
      };

      // Si hors ligne, on met en queue IndexedDB
      const { useOffline } = await import("@/stores/offline");
      const isOnline = useOffline.getState().online && navigator.onLine;

      if (!isOnline) {
        const { queuePendingSale } = await import("@/lib/offline-db");
        const entry = await queuePendingSale(payload);
        await useOffline.getState().refreshCounts();
        // Retourner une "fake sale" pour l'UX
        return {
          id: entry.id,
          sale_number: `OFFLINE-${entry.id.slice(-6)}`,
          total_ttc: total.toFixed(2),
          items: [],
          loyalty_points_earned: 0,
          _offline: true,
        } as unknown as Sale & { _offline: true };
      }

      try {
        const { data } = await api.post<Sale>("/sales", payload, { timeout: 8_000 });
        return data;
      } catch (err: unknown) {
        // Erreur réseau (timeout, perte connexion) → queue + retour fake
        const isNetworkErr =
          err && typeof err === "object" &&
          ("code" in err && (err as { code: string }).code === "ERR_NETWORK" ||
           "message" in err && /network|timeout|fetch/i.test(String((err as { message: string }).message)));
        if (isNetworkErr) {
          const { queuePendingSale } = await import("@/lib/offline-db");
          const entry = await queuePendingSale(payload);
          await useOffline.getState().refreshCounts();
          return {
            id: entry.id,
            sale_number: `OFFLINE-${entry.id.slice(-6)}`,
            total_ttc: total.toFixed(2),
            items: [],
            loyalty_points_earned: 0,
            _offline: true,
          } as unknown as Sale & { _offline: true };
        }
        throw err;
      }
    },
    onSuccess: (sale: Sale & { _offline?: boolean }) => {
      if (sale._offline) {
        toast.info("Vente enregistrée hors-ligne", "Sera synchronisée au retour du réseau");
      } else {
        toast.success("Vente enregistrée", sale.sale_number);
      }
      onSuccess(sale);
    },
    onError: (err) => {
      toast.error("Échec de la vente", extractErrorMessage(err));
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Encaissement</DialogTitle>
          <DialogDescription>
            Total à payer : <span className="font-semibold text-foreground">{formatMAD(total)}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <PayInput label="Espèces" value={paidCash} onChange={setPaidCash} />
          <PayInput label="Carte" value={paidCard} onChange={setPaidCard} />
          <PayInput label="Chèque" value={paidCheck} onChange={setPaidCheck} />
          <PayInput
            label="Crédit"
            value={paidCredit}
            onChange={setPaidCredit}
            disabled={!cart.clientId}
            hint={!cart.clientId ? "Sélectionnez un client pour activer le crédit" : undefined}
          />

          <div className="rounded-md bg-muted p-3 space-y-1 text-sm">
            <div className="flex justify-between">
              <span>Payé</span>
              <span className="font-medium">{formatMAD(sumPaid)}</span>
            </div>
            <div className="flex justify-between">
              <span>Total</span>
              <span className="font-medium">{formatMAD(total)}</span>
            </div>
            <div className="flex justify-between text-base font-semibold pt-2 border-t">
              {rendu >= 0 ? (
                <>
                  <span>Rendu</span>
                  <span className="text-emerald-700">{formatMAD(rendu)}</span>
                </>
              ) : (
                <>
                  <span>Manque</span>
                  <span className="text-red-700">{formatMAD(-rendu)}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={insuffisant || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
            Valider la vente
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PayInput({
  label,
  value,
  onChange,
  disabled,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <Input
        type="number"
        step="0.01"
        min="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="0.00"
      />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

// ---------- ReceiptDialog ----------
function ReceiptDialog({
  sale,
  onClose,
  productsById,
}: {
  sale: Sale | null;
  onClose: () => void;
  productsById: Record<string, Product>;
}) {
  if (!sale) return null;
  return (
    <Dialog open={!!sale} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-emerald-700">✓ Vente {sale.sale_number}</DialogTitle>
          <DialogDescription>
            Total : <span className="font-semibold text-foreground">{formatMAD(sale.total_ttc)}</span>
            {sale.loyalty_points_earned > 0 && (
              <> · {sale.loyalty_points_earned} pts fidélité gagnés</>
            )}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 text-sm">
          <div className="border rounded-md divide-y max-h-60 overflow-y-auto">
            {sale.items.map((it) => (
              <div key={it.id} className="flex justify-between p-2">
                <div>
                  <p className="font-medium">{productsById[it.product_id]?.name ?? it.product_id}</p>
                  <p className="text-xs text-muted-foreground">
                    {it.quantity} × {formatMAD(it.unit_price_ttc)}
                  </p>
                </div>
                <p className="font-medium">{formatMAD(it.line_total_ttc)}</p>
              </div>
            ))}
          </div>
        </div>
        <DialogFooter className="gap-2 flex-wrap sm:flex-nowrap">
          <Button
            variant="outline"
            onClick={() => window.open(`/sales/${sale.id}/ticket`, "_blank")}
            className="flex-1"
          >
            🧾 Ticket
          </Button>
          <Button
            variant="outline"
            onClick={() => window.open(`/sales/${sale.id}/invoice`, "_blank")}
            className="flex-1"
          >
            📄 Facture
          </Button>
          <Button onClick={onClose} className="flex-1">Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
