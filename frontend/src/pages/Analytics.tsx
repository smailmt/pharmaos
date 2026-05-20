import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Wallet,
  Clock,
  Package as PackageIcon,
  Sparkles,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/toast";

interface RevenueComparison {
  today: string;
  yesterday: string;
  this_week: string;
  last_week: string;
  this_month: string;
  last_month: string;
  delta_week_pct: number | null;
  delta_month_pct: number | null;
}

interface SalesTimeSeriesPoint {
  date: string;
  revenue: string;
  sales_count: number;
}

interface TopProduct {
  product_id: string;
  code: string;
  name: string;
  quantity_sold: number;
  revenue: string;
}

interface PaymentBreakdown {
  method: string;
  amount: string;
  percentage: number;
}

interface HourlyDistribution {
  hour: number;
  sales_count: number;
  revenue: string;
}

interface AnomalyAlert {
  severity: "info" | "warning" | "critical";
  category: string;
  title: string;
  description: string;
  sale_ids: string[];
}

interface AnomalyResponse {
  period_start: string;
  period_end: string;
  sales_analyzed: number;
  total_revenue: string;
  anomalies: AnomalyAlert[];
  summary: string;
}

const PAYMENT_COLORS: Record<string, string> = {
  cash: "#10b981",
  card: "#3b82f6",
  check: "#a855f7",
  credit: "#f59e0b",
};
const PAYMENT_LABELS: Record<string, string> = {
  cash: "Espèces",
  card: "Carte",
  check: "Chèque",
  credit: "Crédit",
};

export function AnalyticsPage() {
  const [period, setPeriod] = useState(30);

  const { data: revenue, isLoading: loadingRev } = useQuery({
    queryKey: ["analytics", "revenue"],
    queryFn: () =>
      api.get<RevenueComparison>("/analytics/revenue-summary").then((r) => r.data),
  });

  const { data: timeseries, isLoading: loadingTs } = useQuery({
    queryKey: ["analytics", "timeseries", period],
    queryFn: () =>
      api
        .get<SalesTimeSeriesPoint[]>(`/analytics/sales-timeseries?days=${period}`)
        .then((r) => r.data),
  });

  const { data: top, isLoading: loadingTop } = useQuery({
    queryKey: ["analytics", "top", period],
    queryFn: () =>
      api
        .get<TopProduct[]>(`/analytics/top-products?days=${period}&limit=10`)
        .then((r) => r.data),
  });

  const { data: payments, isLoading: loadingPay } = useQuery({
    queryKey: ["analytics", "payments", period],
    queryFn: () =>
      api
        .get<PaymentBreakdown[]>(`/analytics/payment-methods-breakdown?days=${period}`)
        .then((r) => r.data),
  });

  const { data: hourly, isLoading: loadingHourly } = useQuery({
    queryKey: ["analytics", "hourly", period],
    queryFn: () =>
      api.get<HourlyDistribution[]>(`/analytics/hourly-distribution?days=${period}`).then((r) => r.data),
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <BarChart3 className="h-6 w-6 text-primary" />
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Analytics</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Pilotez votre pharmacie avec des données en temps réel.
          </p>
        </div>
        <div className="flex gap-1">
          {[7, 30, 90].map((d) => (
            <Button
              key={d}
              variant={period === d ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod(d)}
            >
              {d}j
            </Button>
          ))}
        </div>
      </header>

      {/* Revenue summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <RevenueCard
          title="Aujourd'hui"
          value={revenue?.today}
          loading={loadingRev}
        />
        <RevenueCard
          title="Hier"
          value={revenue?.yesterday}
          loading={loadingRev}
          subtle
        />
        <RevenueCard
          title="Cette semaine"
          value={revenue?.this_week}
          deltaPct={revenue?.delta_week_pct ?? null}
          loading={loadingRev}
        />
        <RevenueCard
          title="Ce mois"
          value={revenue?.this_month}
          deltaPct={revenue?.delta_month_pct ?? null}
          loading={loadingRev}
        />
      </div>

      {/* Time series */}
      <Card>
        <CardHeader>
          <CardTitle>Chiffre d'affaires — {period} derniers jours</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingTs ? (
            <Skeleton className="h-[260px] w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={timeseries ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="date"
                  fontSize={11}
                  tickFormatter={(d: string) => d.slice(5)}
                />
                <YAxis fontSize={11} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  formatter={(value: number) => formatMAD(value)}
                  labelFormatter={(d: string) => d}
                />
                <Line
                  type="monotone"
                  dataKey="revenue"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Top products + Payment breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PackageIcon className="h-4 w-4" />
              Top 10 produits — {period} jours
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingTop ? (
              <Skeleton className="h-[260px] w-full" />
            ) : !top || top.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-10">Aucune vente sur cette période.</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={top} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" fontSize={11} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    fontSize={11}
                    width={120}
                    tick={{ width: 120 }}
                  />
                  <Tooltip formatter={(value: number) => formatMAD(value)} />
                  <Bar dataKey="revenue" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wallet className="h-4 w-4" />
              Paiements
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingPay ? (
              <Skeleton className="h-[260px] w-full" />
            ) : !payments || payments.length === 0 || payments.every((p) => parseFloat(p.amount) === 0) ? (
              <p className="text-sm text-muted-foreground text-center py-10">Aucun paiement.</p>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={payments.filter((p) => parseFloat(p.amount) > 0)}
                    dataKey={(p) => parseFloat(p.amount)}
                    nameKey="method"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={(e) => `${PAYMENT_LABELS[e.method] ?? e.method} ${e.percentage.toFixed(0)}%`}
                  >
                    {payments.map((p) => (
                      <Cell key={p.method} fill={PAYMENT_COLORS[p.method] ?? "#888"} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => formatMAD(value)} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Hourly + Anomaly Detection */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Distribution horaire (staffing)
            </CardTitle>
            <CardDescription>
              Ventes par heure de la journée — moyenne sur {period} jours.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loadingHourly ? (
              <Skeleton className="h-[240px] w-full" />
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={hourly ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="hour" fontSize={11} tickFormatter={(h: number) => `${h}h`} />
                  <YAxis fontSize={11} />
                  <Tooltip
                    labelFormatter={(h: number) => `${h}h - ${h + 1}h`}
                    formatter={(value: number, name) =>
                      name === "sales_count" ? [`${value} ventes`, "Ventes"] : value
                    }
                  />
                  <Bar dataKey="sales_count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <AnomalyDetectionCard />
      </div>
    </div>
  );
}

function RevenueCard({
  title,
  value,
  deltaPct,
  loading,
  subtle,
}: {
  title: string;
  value: string | undefined;
  deltaPct?: number | null;
  loading?: boolean;
  subtle?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-4 sm:p-6">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        {loading ? (
          <Skeleton className="h-8 w-24 mt-2" />
        ) : (
          <>
            <p className={`text-2xl font-bold tracking-tight mt-1 ${subtle ? "text-muted-foreground" : ""}`}>
              {formatMAD(value)}
            </p>
            {deltaPct !== undefined && deltaPct !== null && (
              <div className="flex items-center gap-1 mt-1.5 text-xs">
                {deltaPct >= 0 ? (
                  <>
                    <TrendingUp className="h-3.5 w-3.5 text-emerald-600" />
                    <span className="text-emerald-700 font-medium">+{deltaPct.toFixed(1)}%</span>
                  </>
                ) : (
                  <>
                    <TrendingDown className="h-3.5 w-3.5 text-red-600" />
                    <span className="text-red-700 font-medium">{deltaPct.toFixed(1)}%</span>
                  </>
                )}
                <span className="text-muted-foreground">vs période précédente</span>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function AnomalyDetectionCard() {
  const [result, setResult] = useState<AnomalyResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const runDetection = async () => {
    setLoading(true);
    try {
      const { data } = await api.post<AnomalyResponse>(
        "/ai/anomaly-detection?days=1",
        {},
        { timeout: 60_000 }
      );
      setResult(data);
      if (data.anomalies.length === 0) {
        toast.success("Aucune anomalie détectée", "Votre caisse semble normale aujourd'hui.");
      } else {
        toast.info(`${data.anomalies.length} alerte${data.anomalies.length > 1 ? "s" : ""} détectée${data.anomalies.length > 1 ? "s" : ""}`);
      }
    } catch (err) {
      toast.error("Erreur d'analyse", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const severityStyles = {
    info: "border-l-blue-500 bg-blue-50 text-blue-900",
    warning: "border-l-amber-500 bg-amber-50 text-amber-900",
    critical: "border-l-red-500 bg-red-50 text-red-900",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          Audit IA
        </CardTitle>
        <CardDescription>Claude analyse vos ventes pour détecter des patterns suspects.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button onClick={runDetection} disabled={loading} className="w-full">
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Analyse en cours…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4 mr-2" />
              Lancer l'audit
            </>
          )}
        </Button>

        {result && (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {result.summary && (
              <p className="text-xs text-muted-foreground italic px-1">{result.summary}</p>
            )}
            {result.anomalies.length === 0 ? (
              <p className="text-sm text-emerald-700 text-center py-3">
                ✓ {result.sales_analyzed} ventes analysées, RAS
              </p>
            ) : (
              result.anomalies.map((a, i) => (
                <div
                  key={i}
                  className={`border-l-4 rounded-md p-2.5 text-sm ${severityStyles[a.severity]}`}
                >
                  <div className="flex items-start gap-2">
                    {a.severity !== "info" && <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />}
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{a.title}</p>
                      <p className="text-xs mt-0.5 opacity-90">{a.description}</p>
                      <Badge variant="outline" className="mt-1.5 text-[10px]">
                        {a.category}
                      </Badge>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
