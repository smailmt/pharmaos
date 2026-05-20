/**
 * Command Palette — Search global ⌘K (Ctrl+K).
 *
 * Inspiré de Linear/GitHub/VSCode : un seul champ pour tout chercher.
 * Recherche : produits, clients, ventes, navigation rapide.
 */
import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  Package,
  Users,
  ScanLine,
  LayoutDashboard,
  Truck,
  BarChart3,
  Code2,
  ArrowRight,
  CornerDownLeft,
  ListChecks,
  Banknote,
  ArrowLeftRight,
  ClipboardList,
  FileText,
  Bot,
  Shield,
} from "lucide-react";
import { api } from "@/lib/api";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { formatMAD } from "@/lib/utils";
import type { Product, Client } from "@/types/api";

interface CommandItem {
  id: string;
  type: "nav" | "product" | "client" | "action";
  label: string;
  hint?: string;
  shortcut?: string;
  icon: React.ComponentType<{ className?: string }>;
  onSelect: () => void;
}

const NAV_ITEMS: { label: string; path: string; icon: React.ComponentType<{ className?: string }>; hint: string }[] = [
  { label: "Tableau de bord", path: "/", icon: LayoutDashboard, hint: "Vue d'ensemble" },
  { label: "Caisse", path: "/cashier", icon: ScanLine, hint: "Mode caissier plein écran" },
  { label: "Stock", path: "/stock", icon: Package, hint: "Catalogue produits" },
  { label: "Clients", path: "/clients", icon: Users, hint: "Gestion clients et crédits" },
  { label: "Tiers payants", path: "/tiers-payants", icon: Shield, hint: "CNOPS, CNSS, mutuelles, bordereaux" },
  { label: "Fournisseurs", path: "/fournisseurs", icon: Truck, hint: "Commandes et factures" },
  { label: "Analytics", path: "/analytics", icon: BarChart3, hint: "Graphiques et KPIs" },
  { label: "PharmaBot IA", path: "/pharmabot", icon: Bot, hint: "Assistant clinique conversationnel" },
  { label: "Ordonnancier", path: "/ordonnancier", icon: ClipboardList, hint: "Registre des ordonnances" },
  { label: "Charges", path: "/charges", icon: Banknote, hint: "Frais d'exploitation" },
  { label: "Échanges confrères", path: "/echanges", icon: ArrowLeftRight, hint: "Échanges entre pharmacies" },
  { label: "Inventaire", path: "/inventaire", icon: ListChecks, hint: "Comptage physique du stock" },
  { label: "Clôture journée", path: "/cloture", icon: FileText, hint: "Z-report fin de journée" },
  { label: "Développeurs", path: "/developers", icon: Code2, hint: "API publique et webhooks" },
];

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const { data: products } = useQuery({
    queryKey: ["cmdk-products", search],
    queryFn: () => api.get<Product[]>(`/products?search=${encodeURIComponent(search)}&limit=8`).then((r) => r.data),
    enabled: open && search.length >= 2,
  });

  const { data: clients } = useQuery({
    queryKey: ["cmdk-clients", search],
    queryFn: () => api.get<Client[]>(`/clients?search=${encodeURIComponent(search)}&limit=5`).then((r) => r.data),
    enabled: open && search.length >= 2,
  });

  // Reset on open
  useEffect(() => {
    if (open) {
      setSearch("");
      setActiveIndex(0);
    }
  }, [open]);

  const items = useMemo<CommandItem[]>(() => {
    const q = search.trim().toLowerCase();
    const navMatches: CommandItem[] = NAV_ITEMS.filter(
      (n) => !q || n.label.toLowerCase().includes(q) || n.hint.toLowerCase().includes(q)
    ).map((n) => ({
      id: `nav-${n.path}`,
      type: "nav",
      label: n.label,
      hint: n.hint,
      icon: n.icon,
      onSelect: () => {
        navigate(n.path);
        onClose();
      },
    }));

    const productMatches: CommandItem[] = (products ?? []).map((p) => ({
      id: `prod-${p.id}`,
      type: "product",
      label: p.name,
      hint: `${p.code}${p.dci ? ` · ${p.dci}` : ""} · ${formatMAD(Number(p.sale_price_ttc))} · Stock ${p.stock_quantity}`,
      icon: Package,
      onSelect: () => {
        navigate(`/stock?focus=${p.id}`);
        onClose();
      },
    }));

    const clientMatches: CommandItem[] = (clients ?? []).map((c) => ({
      id: `client-${c.id}`,
      type: "client",
      label: c.full_name,
      hint: c.phone || "Client",
      icon: Users,
      onSelect: () => {
        navigate(`/clients?focus=${c.id}`);
        onClose();
      },
    }));

    // Limiter navigation aux 8 premières si une recherche existe
    return q
      ? [...navMatches.slice(0, 5), ...productMatches, ...clientMatches]
      : navMatches;
  }, [search, products, clients, navigate, onClose]);

  // Reset active index when items change
  useEffect(() => {
    setActiveIndex(0);
  }, [items.length]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(items.length - 1, i + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(0, i - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = items[activeIndex];
        if (item) item.onSelect();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, items, activeIndex]);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xl p-0 gap-0 overflow-hidden">
        <div className="flex items-center gap-2 border-b px-3 py-3">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Chercher un produit, un client, ou naviguer…"
            className="flex-1 bg-transparent border-0 outline-none text-sm"
            autoFocus
          />
          <kbd className="hidden sm:inline px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono">
            ESC
          </kbd>
        </div>

        <div className="max-h-96 overflow-y-auto py-2">
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Aucun résultat
            </p>
          ) : (
            items.map((item, i) => (
              <button
                key={item.id}
                onMouseEnter={() => setActiveIndex(i)}
                onClick={() => item.onSelect()}
                className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${
                  i === activeIndex ? "bg-accent" : "hover:bg-muted/30"
                }`}
              >
                <item.icon className="h-4 w-4 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.label}</p>
                  {item.hint && (
                    <p className="text-xs text-muted-foreground truncate">{item.hint}</p>
                  )}
                </div>
                {i === activeIndex && <CornerDownLeft className="h-3.5 w-3.5 text-muted-foreground" />}
              </button>
            ))
          )}
        </div>

        <div className="border-t px-3 py-1.5 flex items-center gap-3 text-[10px] text-muted-foreground bg-muted/30">
          <span className="flex items-center gap-1">
            <kbd className="px-1 rounded bg-background border">↑↓</kbd> Naviguer
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 rounded bg-background border">↵</kbd> Sélectionner
          </span>
          <span className="flex items-center gap-1 ml-auto">
            <kbd className="px-1 rounded bg-background border">⌘K</kbd> Ouvrir
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
