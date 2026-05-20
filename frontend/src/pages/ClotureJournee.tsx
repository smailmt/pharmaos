import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, CheckCircle2, AlertTriangle, Lock } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatMAD } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface ClosingPreview {
  already_closed: boolean;
  closing_date: string;
  closing_id?: string;
  sales_count?: number;
  cancelled_count?: number;
  total_revenue?: string;
  total_cash?: string;
  total_card?: string;
  total_check?: string;
  total_credit?: string;
  cash_expected?: string;
}

interface ClosingRecord {
  id: string;
  closing_date: string;
  sales_count: number;
  total_revenue: string;
  total_cash: string;
  total_card: string;
  total_credit: string;
  cash_counted: string;
  cash_difference: string;
  notes: string | null;
}

export function ClotureJourneePage() {
  const qc = useQueryClient();
  const [cashCounted, setCashCounted] = useState("");
  const [notes, setNotes] = useState("");

  const { data: preview, isLoading } = useQuery({
    queryKey: ["closing-preview"],
    queryFn: () =>
      api.get<ClosingPreview>("/operations/day-closings/preview").then((r) => r.data),
  });

  const { data: history } = useQuery({
    queryKey: ["closing-history"],
    queryFn: () =>
      api.get<ClosingRecord[]>("/operations/day-closings").then((r) => r.data),
  });

  const closeMutation = useMutation({
    mutationFn: async () =>
      api
        .post<ClosingRecord>("/operations/day-closings", {
          cash_counted: parseFloat(cashCounted || "0").toFixed(2),
          notes: notes || null,
        })
        .then((r) => r.data),
    onSuccess: () => {
      toast.success("Journée clôturée");
      qc.invalidateQueries({ queryKey: ["closing-preview"] });
      qc.invalidateQueries({ queryKey: ["closing-history"] });
      setCashCounted("");
      setNotes("");
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-5xl">
      <header>
        <div className="flex items-center gap-2 mb-1">
          <FileText className="h-6 w-6 text-primary" />
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Clôture de journée</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Figez les ventes du jour. Une fois clôturée, aucune modification possible (Z-report comptable).
        </p>
      </header>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : preview?.already_closed ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 flex items-start gap-3">
            <Lock className="h-5 w-5 text-amber-700 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Journée déjà clôturée</p>
              <p className="text-sm text-amber-800 mt-1">
                La journée du {preview.closing_date} a déjà été clôturée. Plus aucune vente ne peut
                être créée pour cette date.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Totaux du jour (en temps réel)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <Metric label="Ventes" value={String(preview?.sales_count ?? 0)} />
                <Metric label="Annulations" value={String(preview?.cancelled_count ?? 0)} />
                <Metric label="CA total" value={formatMAD(preview?.total_revenue ?? 0)} highlight />
                <Metric label="Espèces" value={formatMAD(preview?.total_cash ?? 0)} />
                <Metric label="Carte" value={formatMAD(preview?.total_card ?? 0)} />
                <Metric label="Chèque" value={formatMAD(preview?.total_check ?? 0)} />
                <Metric label="Crédit client" value={formatMAD(preview?.total_credit ?? 0)} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Procéder à la clôture</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-primary/5 border border-primary/20 rounded-md p-3 text-sm">
                <p>
                  <strong>Espèces théoriques en caisse :</strong>{" "}
                  {formatMAD(preview?.total_cash ?? 0)}
                </p>
                <p className="text-muted-foreground mt-1 text-xs">
                  Comptez physiquement votre caisse, entrez le montant ci-dessous. PharmaOS calculera
                  automatiquement l'écart.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Espèces comptées (MAD)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={cashCounted}
                    onChange={(e) => setCashCounted(e.target.value)}
                    placeholder="0.00"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Notes (optionnel)</Label>
                  <Input
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Remarques sur la journée…"
                  />
                </div>
              </div>

              {cashCounted && preview?.total_cash && (
                <div
                  className={`text-sm p-3 rounded-md ${
                    Math.abs(parseFloat(cashCounted) - parseFloat(preview.total_cash)) < 0.01
                      ? "bg-emerald-50 text-emerald-900 border border-emerald-200"
                      : "bg-amber-50 text-amber-900 border border-amber-200"
                  }`}
                >
                  Écart :{" "}
                  <strong>
                    {formatMAD(parseFloat(cashCounted) - parseFloat(preview.total_cash))}
                  </strong>
                  {Math.abs(parseFloat(cashCounted) - parseFloat(preview.total_cash)) < 0.01
                    ? " — Parfait !"
                    : ""}
                </div>
              )}

              <Button
                onClick={() => {
                  if (
                    confirm(
                      "Confirmer la clôture ? Plus aucune vente ne pourra être créée pour aujourd'hui."
                    )
                  )
                    closeMutation.mutate();
                }}
                disabled={closeMutation.isPending}
                className="w-full"
                size="lg"
              >
                {closeMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Clôturer la journée
              </Button>
            </CardContent>
          </Card>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Historique des clôtures</CardTitle>
        </CardHeader>
        <CardContent>
          {!history || history.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              Aucune clôture encore enregistrée.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Ventes</TableHead>
                  <TableHead className="text-right">CA</TableHead>
                  <TableHead className="text-right">Écart caisse</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((h) => {
                  const diff = parseFloat(h.cash_difference);
                  return (
                    <TableRow key={h.id}>
                      <TableCell className="font-medium">{h.closing_date}</TableCell>
                      <TableCell className="text-right">{h.sales_count}</TableCell>
                      <TableCell className="text-right">{formatMAD(h.total_revenue)}</TableCell>
                      <TableCell className="text-right">
                        {Math.abs(diff) < 0.01 ? (
                          <Badge variant="success" className="text-[10px]">OK</Badge>
                        ) : (
                          <span className={diff < 0 ? "text-red-600" : "text-amber-600"}>
                            {formatMAD(diff)}
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`font-semibold ${highlight ? "text-xl" : "text-base"}`}>{value}</p>
    </div>
  );
}
