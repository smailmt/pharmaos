import { useQuery } from "@tanstack/react-query";
import {
  Package,
  AlertTriangle,
  Users,
  Calendar,
  TrendingUp,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { api } from "@/lib/api";
import { formatMAD } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { OrderSuggestionsCard } from "@/components/OrderSuggestionsCard";
import type { Product, Client, AgingReport } from "@/types/api";

interface KpiCardProps {
  title: string;
  value: string | number;
  description?: string;
  Icon: React.ComponentType<{ className?: string }>;
  accent?: "default" | "warning" | "danger" | "success";
  loading?: boolean;
}

function KpiCard({ title, value, description, Icon, accent = "default", loading }: KpiCardProps) {
  const accentColors = {
    default: "text-primary bg-primary/10",
    warning: "text-amber-700 bg-amber-100",
    danger: "text-red-700 bg-red-100",
    success: "text-emerald-700 bg-emerald-100",
  };
  return (
    <Card>
      <CardContent className="p-4 sm:p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1 min-w-0">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            {loading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <p className="text-2xl font-bold tracking-tight truncate">{value}</p>
            )}
            {description && !loading && (
              <p className="text-xs text-muted-foreground">{description}</p>
            )}
          </div>
          <div className={`h-10 w-10 rounded-md flex items-center justify-center shrink-0 ${accentColors[accent]}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { data: products, isLoading: loadingProducts } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products").then((r) => r.data),
  });

  const { data: clients, isLoading: loadingClients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<Client[]>("/clients").then((r) => r.data),
  });

  const { data: lowStock, isLoading: loadingLow } = useQuery({
    queryKey: ["alerts", "low-stock"],
    queryFn: () => api.get<Product[]>("/products/alerts/low-stock").then((r) => r.data),
  });

  const { data: expiring, isLoading: loadingExpiring } = useQuery({
    queryKey: ["alerts", "expiring"],
    queryFn: () => api.get("/products/alerts/expiring?days=180").then((r) => r.data),
  });

  const { data: aging, isLoading: loadingAging } = useQuery({
    queryKey: ["clients", "aging"],
    queryFn: () => api.get<AgingReport>("/clients/credit/aging-report").then((r) => r.data),
  });

  const agingChartData =
    aging?.buckets.map((b) => ({
      bucket: b.bucket + " j",
      Encours: parseFloat(b.amount),
      Clients: b.clients_count,
    })) ?? [];

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Tableau de bord</h1>
        <p className="text-muted-foreground text-sm sm:text-base">Vue d'ensemble de votre pharmacie</p>
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KpiCard
          title="Produits"
          value={products?.length ?? 0}
          description="Références actives"
          Icon={Package}
          loading={loadingProducts}
        />
        <KpiCard
          title="Clients"
          value={clients?.length ?? 0}
          description={`${clients?.filter((c) => c.credit_enabled).length ?? 0} avec crédit`}
          Icon={Users}
          loading={loadingClients}
        />
        <KpiCard
          title="Stock faible"
          value={lowStock?.length ?? 0}
          description="Sous seuil minimum"
          Icon={AlertTriangle}
          accent={lowStock && lowStock.length > 0 ? "warning" : "default"}
          loading={loadingLow}
        />
        <KpiCard
          title="Péremption ≤ 6 mois"
          value={expiring?.length ?? 0}
          description="Lots à surveiller"
          Icon={Calendar}
          accent={expiring && expiring.length > 0 ? "danger" : "default"}
          loading={loadingExpiring}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Balance âgée — Crédits clients</CardTitle>
            <CardDescription>
              Encours total : <span className="font-semibold">{formatMAD(aging?.total_outstanding)}</span>
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loadingAging ? (
              <Skeleton className="h-[260px] w-full" />
            ) : agingChartData.length > 0 && parseFloat(aging?.total_outstanding ?? "0") > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={agingChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="bucket" fontSize={12} />
                  <YAxis fontSize={12} />
                  <Tooltip
                    formatter={(value: number, name: string) =>
                      name === "Encours" ? formatMAD(value) : value
                    }
                  />
                  <Bar dataKey="Encours" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground py-10 text-center">
                Aucun encours client — tout est à jour ✨
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Alertes
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {lowStock && lowStock.length > 0 && (
              <div className="rounded-md border-l-4 border-amber-500 bg-amber-50 p-3">
                <p className="text-sm font-medium text-amber-900">
                  {lowStock.length} produit{lowStock.length > 1 ? "s" : ""} sous seuil
                </p>
                <p className="text-xs text-amber-700 mt-1">
                  À commander rapidement.
                </p>
              </div>
            )}
            {expiring && expiring.length > 0 && (
              <div className="rounded-md border-l-4 border-red-500 bg-red-50 p-3">
                <p className="text-sm font-medium text-red-900">
                  {expiring.length} lot{expiring.length > 1 ? "s" : ""} bientôt périmé{expiring.length > 1 ? "s" : ""}
                </p>
                <p className="text-xs text-red-700 mt-1">
                  Échéance ≤ 6 mois.
                </p>
              </div>
            )}
            {aging && parseFloat(aging.total_outstanding) > 0 && (
              <div className="rounded-md border-l-4 border-primary bg-primary/5 p-3">
                <p className="text-sm font-medium">
                  Encours crédit : {formatMAD(aging.total_outstanding)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Pensez aux relances.
                </p>
              </div>
            )}
            {!loadingLow && !loadingExpiring && !loadingAging &&
              (!lowStock || lowStock.length === 0) &&
              (!expiring || expiring.length === 0) &&
              (!aging || parseFloat(aging.total_outstanding) === 0) && (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  ✨ Tout est sous contrôle
                </p>
              )}
          </CardContent>
        </Card>
      </div>

      <OrderSuggestionsCard />
    </div>
  );
}
