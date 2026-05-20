/**
 * Carte "Suggestions d'achat IA" — affiche les produits à commander
 * basé sur l'historique des ventes.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Truck,
  Sparkles,
  AlertTriangle,
  Package,
  TrendingDown,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface OrderSuggestion {
  product_id: string;
  product_name: string;
  current_stock: number;
  avg_daily_sales: number;
  days_of_stock: number;
  suggested_quantity: number;
  reason: string;
}

export function OrderSuggestionsCard() {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["order-suggestions"],
    queryFn: () =>
      api.get<OrderSuggestion[]>("/ai/order-suggestions?days_history=30&days_target=30").then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });

  if (error) return null;

  const items = data ?? [];
  const visible = expanded ? items : items.slice(0, 4);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Truck className="h-4 w-4 text-primary" />
              Suggestions d'achat
              <Badge variant="secondary" className="text-[10px]">
                <Sparkles className="h-3 w-3 mr-0.5" />
                IA
              </Badge>
            </CardTitle>
            <CardDescription className="text-xs mt-0.5">
              Basé sur les ventes des 30 derniers jours.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Analyse en cours…
          </div>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            Aucune suggestion — votre stock semble bien dimensionné.
          </p>
        ) : (
          <>
            <div className="space-y-2">
              {visible.map((s) => (
                <SuggestionRow key={s.product_id} suggestion={s} onClick={() => navigate("/stock")} />
              ))}
            </div>
            {items.length > 4 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExpanded(!expanded)}
                className="w-full mt-2 text-xs"
              >
                {expanded ? "Voir moins" : `Voir ${items.length - 4} suggestion(s) de plus`}
              </Button>
            )}
            <div className="mt-3 pt-3 border-t flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => navigate("/fournisseurs")}
                className="text-xs"
              >
                <Truck className="h-3 w-3 mr-1" />
                Passer commande
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function SuggestionRow({
  suggestion,
  onClick,
}: {
  suggestion: OrderSuggestion;
  onClick: () => void;
}) {
  const isUrgent = suggestion.days_of_stock < 7;
  return (
    <button
      onClick={onClick}
      className="w-full flex items-start gap-2 p-2 rounded-md hover:bg-muted/30 text-left transition-colors"
    >
      <div
        className={`rounded p-1.5 shrink-0 mt-0.5 ${
          isUrgent ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
        }`}
      >
        {isUrgent ? (
          <AlertTriangle className="h-3.5 w-3.5" />
        ) : (
          <TrendingDown className="h-3.5 w-3.5" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{suggestion.product_name}</p>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>Stock {suggestion.current_stock}</span>
          <span>·</span>
          <span>
            {suggestion.days_of_stock.toFixed(0)} j de couverture
          </span>
        </div>
      </div>
      <div className="text-right shrink-0">
        <p className="text-sm font-semibold text-primary">+{suggestion.suggested_quantity}</p>
        <p className="text-[10px] text-muted-foreground">à commander</p>
      </div>
      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-1" />
    </button>
  );
}
