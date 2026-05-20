/**
 * Mode Caissier — UI simplifiée pour les vendeurs.
 *
 * Principes :
 * - Pas de sidebar, pas de menus complexes
 * - Gros boutons tactiles (mobile friendly)
 * - Raccourcis clavier F1-F12 pour les actions principales
 * - Une seule page, tout est ici
 * - Le caissier peut faire 95% de son boulot sans clic souris
 *
 * Raccourcis :
 *   F1 ou /          → Focus recherche produit
 *   F2               → Scanner code-barres caméra
 *   F3               → Photo ordonnance (OCR)
 *   F4               → Sélectionner / changer client
 *   F10 ou Entrée    → Encaisser
 *   Esc              → Vider panier / fermer dialog
 *   Ctrl+L           → Mode complet (vue titulaire)
 */
import { useState, useEffect, useRef, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Search,
  ScanLine,
  FileImage,
  User as UserIcon,
  Trash2,
  Plus,
  Minus,
  Wifi,
  WifiOff,
  Loader2,
  LogOut,
  HelpCircle,
  CheckCircle2,
  Settings,
  Camera,
  X,
} from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { useCart } from "@/stores/cart";
import { useOffline } from "@/stores/offline";
import { formatMAD } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";
import { BarcodeScanner } from "@/components/BarcodeScanner";
import { PrescriptionOCRDialog } from "@/components/PrescriptionOCRDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Product, Client, Sale } from "@/types/api";

export function CashierPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const cart = useCart();
  const { online, pendingCount, syncing, syncNow } = useOffline();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [scannerOpen, setScannerOpen] = useState(false);
  const [ocrOpen, setOcrOpen] = useState(false);
  const [clientPickerOpen, setClientPickerOpen] = useState(false);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [lastSale, setLastSale] = useState<Sale | null>(null);

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Charger produits + cache offline
  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: async () => {
      try {
        const { data } = await api.get<Product[]>("/products?limit=500");
        const { cacheProducts } = await import("@/lib/offline-db");
        cacheProducts(data).catch(() => undefined);
        return data;
      } catch (err) {
        const { getCachedProducts } = await import("@/lib/offline-db");
        const cached = await getCachedProducts();
        if (cached.length > 0) return cached;
        throw err;
      }
    },
  });

  // Filtrer
  const filtered = useMemo(() => {
    if (!products) return [];
    const q = search.trim().toLowerCase();
    if (!q) return [];
    return products
      .filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.code.toLowerCase().includes(q) ||
          (p.dci && p.dci.toLowerCase().includes(q)) ||
          (p.barcode && p.barcode === q)
      )
      .slice(0, 12);
  }, [products, search]);

  // Raccourcis clavier globaux
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ne pas intercepter si une dialog est ouverte
      const dialogOpen = scannerOpen || ocrOpen || paymentOpen || clientPickerOpen || helpOpen;

      // F1 ou "/" → focus search
      if ((e.key === "F1" || (e.key === "/" && !dialogOpen)) && !dialogOpen) {
        // Ne pas intercepter si on est déjà dans un input
        const tag = (document.activeElement as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        e.preventDefault();
        searchInputRef.current?.focus();
      }
      // F2 → scanner
      if (e.key === "F2" && !dialogOpen) {
        e.preventDefault();
        setScannerOpen(true);
      }
      // F3 → OCR
      if (e.key === "F3" && !dialogOpen) {
        e.preventDefault();
        setOcrOpen(true);
      }
      // F4 → client picker
      if (e.key === "F4" && !dialogOpen) {
        e.preventDefault();
        setClientPickerOpen(true);
      }
      // F10 → encaisser
      if (e.key === "F10" && !dialogOpen && cart.items.length > 0) {
        e.preventDefault();
        setPaymentOpen(true);
      }
      // Escape → vider panier (si rien d'ouvert)
      if (e.key === "Escape" && !dialogOpen) {
        if (cart.items.length > 0) {
          if (confirm("Vider le panier ?")) cart.clear();
        }
      }
      // Ctrl+L → mode titulaire (si autorisé)
      if (e.key === "l" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        navigate("/");
      }
      // F1 = aide (en plus du focus)
      if (e.key === "F12" && !dialogOpen) {
        e.preventDefault();
        setHelpOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [scannerOpen, ocrOpen, paymentOpen, clientPickerOpen, helpOpen, cart, navigate]);

  // Auto-add si scan code-barres exact unique
  useEffect(() => {
    if (!products) return;
    const q = search.trim();
    if (q.length >= 8) {
      const exact = products.find((p) => p.barcode === q || p.code === q);
      if (exact) {
        cart.addProduct(exact);
        setSearch("");
        toast.success("Ajouté", exact.name);
      }
    }
  }, [search, products]);

  const totalTTC = cart.items.reduce(
    (sum, i) => sum + i.quantity * Number(i.unit_price_ttc) * (1 - Number(i.discount_rate)),
    0
  );

  const isMgr = user?.role === "owner" || user?.role === "titulaire";

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* Topbar caissier — minimaliste */}
      <header className="h-14 bg-primary text-primary-foreground flex items-center px-4 gap-3 shadow-md">
        <ScanLine className="h-5 w-5" />
        <h1 className="font-semibold tracking-tight">PharmaOS · Caisse</h1>

        <div className="ml-auto flex items-center gap-3">
          {/* Réseau */}
          {online && pendingCount === 0 ? (
            <span className="text-xs flex items-center gap-1 opacity-90">
              <Wifi className="h-3.5 w-3.5" /> En ligne
            </span>
          ) : !online ? (
            <span className="text-xs flex items-center gap-1 bg-amber-500 text-amber-900 px-2 py-1 rounded">
              <WifiOff className="h-3.5 w-3.5" /> Hors ligne
              {pendingCount > 0 && <span className="font-semibold">({pendingCount})</span>}
            </span>
          ) : (
            <button
              onClick={() => syncNow()}
              disabled={syncing}
              className="text-xs flex items-center gap-1 bg-white text-primary px-2 py-1 rounded font-medium"
            >
              {syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wifi className="h-3.5 w-3.5" />}
              Sync ({pendingCount})
            </button>
          )}

          <span className="text-xs opacity-90 hidden sm:inline">{user?.full_name}</span>

          <button
            onClick={() => setHelpOpen(true)}
            className="opacity-80 hover:opacity-100"
            title="Aide (F12)"
            aria-label="Aide"
          >
            <HelpCircle className="h-5 w-5" />
          </button>

          {isMgr && (
            <button
              onClick={() => navigate("/")}
              className="opacity-80 hover:opacity-100"
              title="Mode titulaire (Ctrl+L)"
              aria-label="Passer en mode titulaire"
            >
              <Settings className="h-5 w-5" />
            </button>
          )}

          <button
            onClick={() => {
              if (confirm("Se déconnecter ?")) logout();
            }}
            className="opacity-80 hover:opacity-100"
            title="Déconnexion"
            aria-label="Déconnexion"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </header>

      {/* Corps : 2 colonnes */}
      <div className="flex-1 flex flex-col lg:flex-row min-h-0">
        {/* Gauche : recherche + résultats */}
        <div className="flex-1 flex flex-col p-4 lg:p-6 gap-3 overflow-hidden">
          {/* Barre de recherche XL */}
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-6 w-6 text-muted-foreground" />
            <Input
              ref={searchInputRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cherchez un produit, scannez un code, ou tapez le nom…"
              className="pl-12 pr-4 h-16 text-lg shadow-sm"
              autoFocus
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
              <kbd className="hidden sm:inline-block px-2 py-1 rounded bg-muted text-xs font-mono">F1</kbd>
            </div>
          </div>

          {/* Boutons gros tactiles */}
          <div className="grid grid-cols-3 gap-2">
            <BigActionButton
              icon={Camera}
              label="Scanner"
              shortcut="F2"
              onClick={() => setScannerOpen(true)}
            />
            <BigActionButton
              icon={FileImage}
              label="Ordonnance"
              shortcut="F3"
              onClick={() => setOcrOpen(true)}
            />
            <BigActionButton
              icon={UserIcon}
              label={cart.clientName || "Client"}
              shortcut="F4"
              onClick={() => setClientPickerOpen(true)}
              active={!!cart.clientId}
            />
          </div>

          {/* Résultats */}
          <div className="flex-1 overflow-y-auto -mx-1 px-1">
            {search.trim() === "" ? (
              <div className="text-center py-12 text-muted-foreground">
                <Search className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p>Tapez pour rechercher, ou scannez un code-barres</p>
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>Aucun produit trouvé pour "{search}"</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {filtered.map((p) => (
                  <ProductCard
                    key={p.id}
                    product={p}
                    onAdd={() => {
                      cart.addProduct(p);
                      setSearch("");
                      searchInputRef.current?.focus();
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Droite : panier */}
        <aside className="lg:w-[420px] bg-white border-l flex flex-col">
          <div className="p-4 border-b">
            <h2 className="font-semibold tracking-tight">
              Panier{" "}
              <span className="text-muted-foreground font-normal">({cart.items.length})</span>
            </h2>
            {cart.clientName && (
              <Badge variant="secondary" className="mt-1">
                <UserIcon className="h-3 w-3 mr-1" />
                {cart.clientName}
              </Badge>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {cart.items.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-12">
                Panier vide
              </p>
            ) : (
              cart.items.map((item) => (
                <div
                  key={item.product.id}
                  className="flex items-center gap-2 p-2 rounded-md hover:bg-muted/50"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.product.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatMAD(Number(item.unit_price_ttc))} × {item.quantity}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() =>
                        cart.updateQuantity(item.product.id, Math.max(0, item.quantity - 1))
                      }
                      className="h-7 w-7 rounded bg-muted hover:bg-muted-foreground/20 flex items-center justify-center"
                      aria-label="Diminuer"
                    >
                      <Minus className="h-3 w-3" />
                    </button>
                    <span className="w-6 text-center text-sm font-medium">{item.quantity}</span>
                    <button
                      onClick={() => cart.updateQuantity(item.product.id, item.quantity + 1)}
                      className="h-7 w-7 rounded bg-muted hover:bg-muted-foreground/20 flex items-center justify-center"
                      aria-label="Augmenter"
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                    <button
                      onClick={() => cart.removeProduct(item.product.id)}
                      className="h-7 w-7 rounded text-red-500 hover:bg-red-50 flex items-center justify-center"
                      aria-label="Retirer"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer avec total + bouton encaisser */}
          <div className="border-t p-4 bg-slate-50 space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium text-muted-foreground">Total à payer</span>
              <span className="text-3xl font-bold tracking-tight">{formatMAD(totalTTC)}</span>
            </div>
            <Button
              onClick={() => setPaymentOpen(true)}
              disabled={cart.items.length === 0}
              size="lg"
              className="w-full h-14 text-base font-semibold"
            >
              Encaisser
              <kbd className="ml-2 px-2 py-0.5 rounded bg-white/20 text-xs font-mono">F10</kbd>
            </Button>
          </div>
        </aside>
      </div>

      {/* Dialogs */}
      <BarcodeScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onScan={(code) => {
          const found = products?.find((p) => p.barcode === code || p.code === code);
          if (found) {
            cart.addProduct(found);
            toast.success("Ajouté", found.name);
          } else {
            toast.error("Produit introuvable", `Code : ${code}`);
            setSearch(code);
          }
        }}
      />

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
          if (added > 0) toast.success(`${added} médicament(s) ajouté(s)`);
        }}
      />

      <ClientPickerDialog
        open={clientPickerOpen}
        onClose={() => setClientPickerOpen(false)}
      />

      <CashierPaymentDialog
        open={paymentOpen}
        onClose={() => setPaymentOpen(false)}
        totalTTC={totalTTC}
        onSuccess={(sale) => {
          setPaymentOpen(false);
          setLastSale(sale);
          cart.clear();
          qc.invalidateQueries({ queryKey: ["products"] });
        }}
      />

      <ReceiptOverlay sale={lastSale} onClose={() => setLastSale(null)} />

      <HelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

// ============ Composants internes ============

function BigActionButton({
  icon: Icon,
  label,
  shortcut,
  onClick,
  active,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  shortcut: string;
  onClick: () => void;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`h-16 rounded-lg border-2 flex flex-col items-center justify-center gap-1 transition-all ${
        active
          ? "border-primary bg-primary/5 text-primary"
          : "border-input bg-white hover:bg-accent/30"
      }`}
    >
      <Icon className="h-5 w-5" />
      <span className="text-xs font-medium flex items-center gap-1">
        {label}
        <kbd className="hidden sm:inline px-1 rounded bg-muted text-[10px] font-mono">{shortcut}</kbd>
      </span>
    </button>
  );
}

function ProductCard({ product, onAdd }: { product: Product; onAdd: () => void }) {
  const lowStock = product.stock_quantity <= product.stock_min && product.stock_quantity > 0;
  const noStock = product.stock_quantity <= 0;
  return (
    <button
      onClick={onAdd}
      disabled={noStock}
      className={`text-left p-3 rounded-lg border bg-white hover:shadow-md transition-shadow disabled:opacity-50 disabled:cursor-not-allowed`}
    >
      <p className="font-medium text-sm line-clamp-2">{product.name}</p>
      {product.dci && <p className="text-xs text-muted-foreground">{product.dci}</p>}
      <div className="flex items-baseline justify-between mt-2">
        <span className="text-base font-bold tracking-tight">
          {formatMAD(Number(product.sale_price_ttc))}
        </span>
        {noStock ? (
          <Badge variant="destructive" className="text-[10px]">
            Épuisé
          </Badge>
        ) : lowStock ? (
          <Badge variant="warning" className="text-[10px]">
            Stock {product.stock_quantity}
          </Badge>
        ) : (
          <span className="text-xs text-muted-foreground">Stock {product.stock_quantity}</span>
        )}
      </div>
    </button>
  );
}

function ClientPickerDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const cart = useCart();
  const [search, setSearch] = useState("");

  const { data: clients } = useQuery({
    queryKey: ["clients", search],
    queryFn: () =>
      api.get<Client[]>(`/clients?search=${encodeURIComponent(search)}&limit=20`).then((r) => r.data),
    enabled: open,
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Sélectionner un client</DialogTitle>
          <DialogDescription>
            Laissez vide pour vendre à un client de passage.
          </DialogDescription>
        </DialogHeader>
        <Input
          placeholder="Nom ou téléphone…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />
        <div className="max-h-72 overflow-y-auto space-y-1">
          <button
            onClick={() => {
              cart.setClient(null, null);
              onClose();
            }}
            className="w-full text-left p-2 rounded hover:bg-muted/50 text-sm text-muted-foreground italic"
          >
            — Client de passage —
          </button>
          {clients?.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                cart.setClient(c.id, c.full_name);
                onClose();
              }}
              className="w-full text-left p-2 rounded hover:bg-muted/50"
            >
              <p className="text-sm font-medium">{c.full_name}</p>
              {c.phone && <p className="text-xs text-muted-foreground">{c.phone}</p>}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CashierPaymentDialog({
  open,
  onClose,
  totalTTC,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  totalTTC: number;
  onSuccess: (sale: Sale) => void;
}) {
  const cart = useCart();
  const [paidCash, setPaidCash] = useState("");
  const total = totalTTC.toFixed(2);
  const cashNum = parseFloat(paidCash) || 0;
  const rendu = cashNum - totalTTC;

  useEffect(() => {
    if (open) setPaidCash(total);
  }, [open, total]);

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        client_id: cart.clientId,
        items: cart.items.map((i) => ({
          product_id: i.product.id,
          quantity: i.quantity,
          unit_price_ttc: Number(i.unit_price_ttc).toFixed(4),
          discount_rate: Number(i.discount_rate).toFixed(4),
        })),
        paid_cash: cashNum.toFixed(2),
        paid_card: "0",
        paid_check: "0",
        paid_credit: "0",
      };

      const { useOffline } = await import("@/stores/offline");
      const isOnline = useOffline.getState().online && navigator.onLine;

      if (!isOnline) {
        const { queuePendingSale } = await import("@/lib/offline-db");
        const entry = await queuePendingSale(payload);
        await useOffline.getState().refreshCounts();
        return {
          id: entry.id,
          sale_number: `OFFLINE-${entry.id.slice(-6)}`,
          total_ttc: total,
          items: [],
          loyalty_points_earned: 0,
        } as unknown as Sale;
      }

      const { data } = await api.post<Sale>("/sales", payload, { timeout: 8_000 });
      return data;
    },
    onSuccess: (sale) => {
      toast.success("Vente enregistrée");
      onSuccess(sale);
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Encaissement</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="text-center py-4 bg-primary/5 rounded-lg">
            <p className="text-sm text-muted-foreground">À payer</p>
            <p className="text-4xl font-bold tracking-tight">{formatMAD(totalTTC)}</p>
          </div>

          <div>
            <label className="text-sm font-medium block mb-1">Reçu (espèces)</label>
            <Input
              type="number"
              step="0.01"
              value={paidCash}
              onChange={(e) => setPaidCash(e.target.value)}
              className="text-xl h-14"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && cashNum >= totalTTC && !mutation.isPending) {
                  mutation.mutate();
                }
              }}
            />
          </div>

          {cashNum >= totalTTC && (
            <div className="text-center bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              <p className="text-sm text-emerald-700">À rendre</p>
              <p className="text-2xl font-bold text-emerald-900">{formatMAD(rendu)}</p>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} className="flex-1">
            Annuler (Esc)
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={cashNum < totalTTC || mutation.isPending}
            className="flex-1"
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Valider (Entrée)
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReceiptOverlay({ sale, onClose }: { sale: Sale | null; onClose: () => void }) {
  const navigate = useNavigate();
  useEffect(() => {
    if (sale) {
      const t = setTimeout(onClose, 3500);
      return () => clearTimeout(t);
    }
  }, [sale, onClose]);

  if (!sale) return null;
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in fade-in">
      <div className="bg-white rounded-2xl p-8 max-w-sm w-full mx-4 text-center space-y-4 animate-in zoom-in">
        <CheckCircle2 className="h-16 w-16 text-emerald-500 mx-auto" />
        <div>
          <h3 className="text-xl font-bold">Vente enregistrée</h3>
          <p className="text-sm text-muted-foreground mt-1">{sale.sale_number}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onClose} className="flex-1">
            Continuer
          </Button>
          {!sale.sale_number.startsWith("OFFLINE") && (
            <Button
              onClick={() => navigate(`/sales/${sale.id}/ticket`)}
              className="flex-1"
            >
              Ticket
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function HelpDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const shortcuts = [
    { key: "F1 ou /", desc: "Rechercher un produit" },
    { key: "F2", desc: "Scanner un code-barres" },
    { key: "F3", desc: "Photo d'ordonnance (IA)" },
    { key: "F4", desc: "Sélectionner un client" },
    { key: "F10 ou Entrée", desc: "Encaisser" },
    { key: "Esc", desc: "Vider le panier / Annuler" },
    { key: "Ctrl+L", desc: "Mode titulaire (admin)" },
    { key: "F12", desc: "Afficher cette aide" },
  ];

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Raccourcis clavier</DialogTitle>
          <DialogDescription>Tout le travail à la caisse sans toucher la souris.</DialogDescription>
        </DialogHeader>
        <div className="space-y-1">
          {shortcuts.map((s) => (
            <div key={s.key} className="flex items-center justify-between py-2 border-b last:border-0">
              <span className="text-sm">{s.desc}</span>
              <kbd className="px-2 py-1 rounded bg-muted text-xs font-mono font-medium">{s.key}</kbd>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
