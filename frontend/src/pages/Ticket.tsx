import { useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Printer, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { formatMAD, formatDateTime } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import type { Sale, Product } from "@/types/api";

interface PharmacyInfo {
  id: string;
  name: string;
  address: string | null;
  city: string | null;
  phone: string | null;
  ice: string | null;
  if_number: string | null;
  rc_number: string | null;
}

export function TicketPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();

  const { data: sale, isLoading } = useQuery({
    queryKey: ["sales", id],
    queryFn: () => api.get<Sale>(`/sales/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products?limit=500").then((r) => r.data),
  });

  const { data: pharmacy } = useQuery({
    queryKey: ["pharmacy", user?.pharmacy_id],
    queryFn: () => api.get<PharmacyInfo>("/auth/pharmacy").then((r) => r.data),
    enabled: !!user?.pharmacy_id,
  });

  const productsById = useMemo(
    () => Object.fromEntries((products ?? []).map((p) => [p.id, p])),
    [products]
  );

  // Décomposition TVA par taux
  const vatBreakdown = useMemo(() => {
    if (!sale) return [];
    const buckets: Record<string, { ht: number; vat: number; ttc: number }> = {};
    sale.items.forEach((it) => {
      const product = productsById[it.product_id];
      const rate = product ? parseFloat(product.vat_rate) : 0.07;
      const ttc = parseFloat(it.line_total_ttc);
      const ht = ttc / (1 + rate);
      const vat = ttc - ht;
      const key = (rate * 100).toFixed(0);
      if (!buckets[key]) buckets[key] = { ht: 0, vat: 0, ttc: 0 };
      buckets[key].ht += ht;
      buckets[key].vat += vat;
      buckets[key].ttc += ttc;
    });
    return Object.entries(buckets).map(([rate, v]) => ({ rate, ...v }));
  }, [sale, productsById]);

  useEffect(() => {
    document.body.classList.add("printable-ticket");
    return () => document.body.classList.remove("printable-ticket");
  }, []);

  if (isLoading || !sale) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  const totalPaid =
    parseFloat(sale.paid_cash) +
    parseFloat(sale.paid_card) +
    parseFloat(sale.paid_check) +
    parseFloat(sale.paid_credit);
  const rendu = totalPaid - parseFloat(sale.total_ttc);

  return (
    <div className="min-h-screen bg-muted/30 py-8 px-4 print:bg-white print:p-0">
      {/* Barre d'action (cachée à l'impression) */}
      <div className="max-w-md mx-auto mb-4 flex gap-2 print:hidden">
        <Button onClick={() => window.print()} className="flex-1">
          <Printer className="h-4 w-4 mr-2" />
          Imprimer
        </Button>
        <Button variant="outline" onClick={() => window.close()}>
          Fermer
        </Button>
      </div>

      {/* Ticket 80mm */}
      <div className="ticket bg-white mx-auto p-4 print:p-2 font-mono text-xs print:shadow-none shadow-lg">
        <div className="text-center mb-3">
          <p className="font-bold text-base">{pharmacy?.name ?? "Pharmacie"}</p>
          {pharmacy?.address && <p>{pharmacy.address}</p>}
          {pharmacy?.city && <p>{pharmacy.city}</p>}
          {pharmacy?.phone && <p>Tél : {pharmacy.phone}</p>}
          {pharmacy?.ice && <p>ICE : {pharmacy.ice}</p>}
          {pharmacy?.if_number && <p>IF : {pharmacy.if_number}</p>}
        </div>

        <div className="border-t border-b border-dashed border-gray-400 py-2 mb-2 text-center">
          <p className="font-bold">TICKET DE CAISSE</p>
          <p>N° {sale.sale_number}</p>
          <p>{formatDateTime(sale.sale_date)}</p>
        </div>

        <table className="w-full mb-2">
          <thead>
            <tr className="border-b border-dashed border-gray-400">
              <th className="text-left py-1">Article</th>
              <th className="text-right py-1">Qté</th>
              <th className="text-right py-1">PU</th>
              <th className="text-right py-1">Total</th>
            </tr>
          </thead>
          <tbody>
            {sale.items.map((it) => {
              const product = productsById[it.product_id];
              return (
                <tr key={it.id} className="align-top">
                  <td className="py-1 pr-1">
                    <div className="font-medium">{product?.name ?? "—"}</div>
                    {product?.code && <div className="text-[10px] text-gray-500">{product.code}</div>}
                  </td>
                  <td className="text-right py-1">{it.quantity}</td>
                  <td className="text-right py-1">{parseFloat(it.unit_price_ttc).toFixed(2)}</td>
                  <td className="text-right py-1">{parseFloat(it.line_total_ttc).toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <div className="border-t border-dashed border-gray-400 pt-2 space-y-0.5">
          <div className="flex justify-between">
            <span>Sous-total HT</span>
            <span>{formatMAD(sale.subtotal_ht)}</span>
          </div>
          {parseFloat(sale.total_discount) > 0 && (
            <div className="flex justify-between">
              <span>Remise</span>
              <span>-{formatMAD(sale.total_discount)}</span>
            </div>
          )}
          {vatBreakdown.map((v) => (
            <div key={v.rate} className="flex justify-between">
              <span>TVA {v.rate}%</span>
              <span>{formatMAD(v.vat)}</span>
            </div>
          ))}
          <div className="flex justify-between font-bold text-sm border-t border-dashed border-gray-400 pt-1 mt-1">
            <span>TOTAL TTC</span>
            <span>{formatMAD(sale.total_ttc)}</span>
          </div>
        </div>

        <div className="border-t border-dashed border-gray-400 pt-2 mt-2 space-y-0.5">
          {parseFloat(sale.paid_cash) > 0 && (
            <div className="flex justify-between">
              <span>Espèces</span>
              <span>{formatMAD(sale.paid_cash)}</span>
            </div>
          )}
          {parseFloat(sale.paid_card) > 0 && (
            <div className="flex justify-between">
              <span>Carte</span>
              <span>{formatMAD(sale.paid_card)}</span>
            </div>
          )}
          {parseFloat(sale.paid_check) > 0 && (
            <div className="flex justify-between">
              <span>Chèque</span>
              <span>{formatMAD(sale.paid_check)}</span>
            </div>
          )}
          {parseFloat(sale.paid_credit) > 0 && (
            <div className="flex justify-between">
              <span>Crédit</span>
              <span>{formatMAD(sale.paid_credit)}</span>
            </div>
          )}
          {rendu > 0.001 && (
            <div className="flex justify-between font-bold">
              <span>Rendu</span>
              <span>{formatMAD(rendu)}</span>
            </div>
          )}
        </div>

        {sale.loyalty_points_earned > 0 && (
          <div className="mt-2 pt-2 border-t border-dashed border-gray-400 text-center">
            <p>+{sale.loyalty_points_earned} points fidélité gagnés</p>
          </div>
        )}

        <div className="mt-4 text-center text-[10px] text-gray-600">
          <p>Merci de votre visite !</p>
          <p className="mt-1">Conservez ce ticket pour tout échange.</p>
        </div>
      </div>

      <style>{`
        @media print {
          @page {
            size: 80mm auto;
            margin: 0;
          }
          body {
            background: white !important;
          }
          .ticket {
            width: 80mm;
            max-width: 80mm;
            box-shadow: none;
            margin: 0;
          }
        }
        @media screen {
          .ticket {
            width: 80mm;
            max-width: 100%;
          }
        }
      `}</style>
    </div>
  );
}
