import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  ScanLine,
  Package,
  Users,
  Truck,
  BarChart3,
  Code2,
  LogOut,
  Pill,
  Menu,
  X,
  Wifi,
  WifiOff,
  Loader2,
  RefreshCw,
  Search,
  ClipboardList,
  Banknote,
  ArrowLeftRight,
  ListChecks,
  FileText,
  Bot,
  Shield,
} from "lucide-react";
import { useAuth } from "@/stores/auth";
import { useOffline } from "@/stores/offline";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CommandPalette } from "@/components/CommandPalette";

const navItems = [
  { to: "/", label: "Tableau de bord", icon: LayoutDashboard, end: true },
  { to: "/caisse", label: "Caisse", icon: ScanLine },
  { to: "/stock", label: "Stock", icon: Package },
  { to: "/clients", label: "Clients", icon: Users },
  { to: "/tiers-payants", label: "Tiers payants", icon: Shield },
  { to: "/fournisseurs", label: "Fournisseurs", icon: Truck },
  { to: "/ordonnancier", label: "Ordonnancier", icon: ClipboardList },
  { to: "/echanges", label: "Échanges", icon: ArrowLeftRight },
  { to: "/charges", label: "Charges", icon: Banknote },
  { to: "/inventaire", label: "Inventaire", icon: ListChecks },
  { to: "/cloture", label: "Clôture", icon: FileText },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/pharmabot", label: "PharmaBot IA", icon: Bot },
  { to: "/developers", label: "Développeurs", icon: Code2 },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [cmdkOpen, setCmdkOpen] = useState(false);

  // ⌘K / Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setCmdkOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen bg-muted/30">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "bg-card border-r flex flex-col z-50 transition-transform",
          "fixed inset-y-0 left-0 w-64 lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        <div className="h-16 flex items-center justify-between gap-2 px-6 border-b">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-md bg-primary flex items-center justify-center">
              <Pill className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <p className="font-semibold leading-tight">PharmaOS</p>
              <p className="text-xs text-muted-foreground">v0.4</p>
            </div>
          </div>
          <button
            className="lg:hidden text-muted-foreground hover:text-foreground"
            onClick={() => setMobileOpen(false)}
            aria-label="Fermer le menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground hover:bg-accent hover:text-accent-foreground"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t">
          <div className="px-3 py-2 mb-2">
            <p className="text-sm font-medium truncate">{user?.full_name}</p>
            <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="w-full justify-start gap-2"
          >
            <LogOut className="h-4 w-4" />
            Se déconnecter
          </Button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar (visible mobile + desktop) */}
        <header className="h-14 border-b bg-card flex items-center px-4 gap-3">
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden text-foreground"
            aria-label="Ouvrir le menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="lg:hidden flex items-center gap-2">
            <Pill className="h-5 w-5 text-primary" />
            <span className="font-semibold">PharmaOS</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <button
              onClick={() => setCmdkOpen(true)}
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md border bg-background hover:bg-accent/50 text-sm text-muted-foreground transition-colors"
              title="Recherche globale (⌘K)"
            >
              <Search className="h-3.5 w-3.5" />
              <span>Rechercher…</span>
              <kbd className="ml-2 px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono">⌘K</kbd>
            </button>
            <button
              onClick={() => setCmdkOpen(true)}
              className="sm:hidden text-muted-foreground"
              aria-label="Recherche"
            >
              <Search className="h-5 w-5" />
            </button>
            <NetworkBadge />
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>

      <CommandPalette open={cmdkOpen} onClose={() => setCmdkOpen(false)} />
    </div>
  );
}

function NetworkBadge() {
  const { online, pendingCount, syncing, syncNow } = useOffline();
  if (online && pendingCount === 0) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Wifi className="h-3.5 w-3.5 text-emerald-600" />
        <span className="hidden sm:inline">En ligne</span>
      </div>
    );
  }
  if (!online) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded">
        <WifiOff className="h-3.5 w-3.5" />
        <span className="font-medium">Hors ligne</span>
        {pendingCount > 0 && (
          <span className="bg-amber-200 text-amber-900 px-1.5 rounded text-[10px] font-semibold">
            {pendingCount}
          </span>
        )}
      </div>
    );
  }
  // En ligne mais avec du pending → bouton sync
  return (
    <button
      onClick={() => syncNow()}
      disabled={syncing}
      className="flex items-center gap-1.5 text-xs text-primary bg-primary/10 hover:bg-primary/20 px-2 py-1 rounded font-medium transition-colors disabled:opacity-50"
    >
      {syncing ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <RefreshCw className="h-3.5 w-3.5" />
      )}
      <span>{syncing ? "Synchronisation…" : `Synchroniser (${pendingCount})`}</span>
    </button>
  );
}
