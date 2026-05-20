import { useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Printer, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { formatMAD, formatDate } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import type { Sale, Product, Client } from "@/types/api";

interface PharmacyInfo {
  id: string;
  name: string;
  address: string | null;
  city: string | null;
  phone: string | null;
  email: string | null;
  ice: string | null;
  if_number: string | null;
  rc_number: string | null;
  cnss_number: string | null;
  inpe_number: string | null;
}

export function InvoicePage() {
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

  const { data: client } = useQuery({
    queryKey: ["clients", sale?.client_id],
    queryFn: () => api.get<Client>(`/clients/${sale!.client_id}`).then((r) => r.data),
    enabled: !!sale?.client_id,
  });

  const productsById = useMemo(
    () => Object.fromEntries((products ?? []).map((p) => [p.id, p])),
    [products]
  );

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
    return Object.entries(buckets)
      .map(([rate, v]) => ({ rate, ...v }))
      .sort((a, b) => parseInt(a.rate) - parseInt(b.rate));
  }, [sale, productsById]);

  if (isLoading || !sale) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30 py-8 px-4 print:bg-white print:p-0">
      <div className="max-w-4xl mx-auto mb-4 flex gap-2 print:hidden">
        <Button onClick={() => window.print()} className="flex-1">
          <Printer className="h-4 w-4 mr-2" />
          Imprimer / PDF
        </Button>
        <Button variant="outline" onClick={() => window.close()}>
          Fermer
        </Button>
      </div>

      {/* Facture A4 */}
      <div className="invoice bg-white max-w-4xl mx-auto p-10 shadow-lg print:shadow-none print:p-12 text-sm">
        {/* Header */}
        <div className="flex justify-between items-start mb-8 pb-6 border-b-2 border-primary">
          <div>
            <h1 className="text-2xl font-bold text-primary">{pharmacy?.name ?? "Pharmacie"}</h1>
            {pharmacy?.address && <p className="text-gray-600">{pharmacy.address}</p>}
            {pharmacy?.city && <p className="text-gray-600">{pharmacy.city}</p>}
            {pharmacy?.phone && <p className="text-gray-600">Tél : {pharmacy.phone}</p>}
            {pharmacy?.email && <p className="text-gray-600">{pharmacy.email}</p>}
          </div>
          <div className="text-right">
            <h2 className="text-3xl font-bold tracking-tight">FACTURE</h2>
            <p className="text-gray-600 mt-1">N° {sale.sale_number}</p>
            <p className="text-gray-600">Date : {formatDate(sale.sale_date)}</p>
          </div>
        </div>

        {/* Identifiants pharmacie */}
        <div className="grid grid-cols-4 gap-4 mb-8 text-xs">
          {pharmacy?.ice && (
            <div>
              <p className="text-gray-500 uppercase">ICE</p>
              <p className="font-mono font-medium">{pharmacy.ice}</p>
            </div>
          )}
          {pharmacy?.if_number && (
            <div>
              <p className="text-gray-500 uppercase">IF</p>
              <p className="font-mono font-medium">{pharmacy.if_number}</p>
            </div>
          )}
          {pharmacy?.rc_number && (
            <div>
              <p className="text-gray-500 uppercase">RC</p>
              <p className="font-mono font-medium">{pharmacy.rc_number}</p>
            </div>
          )}
          {pharmacy?.cnss_number && (
            <div>
              <p className="text-gray-500 uppercase">CNSS</p>
              <p className="font-mono font-medium">{pharmacy.cnss_number}</p>
            </div>
          )}
        </div>

        {/* Client */}
        <div className="mb-8 bg-gray-50 p-4 rounded-md">
          <p className="text-xs uppercase text-gray-500 mb-1">Facturé à</p>
          {client ? (
            <>
              <p className="font-semibold text-base">{client.full_name}</p>
              {client.address && <p className="text-gray-600">{client.address}</p>}
              {client.cin && <p className="text-gray-600">CIN : {client.cin}</p>}
              {client.phone && <p className="text-gray-600">Tél : {client.phone}</p>}
            </>
          ) : (
            <p className="italic text-gray-500">Client de passage</p>
          )}
        </div>

        {sale.has_prescription && sale.prescription_number && (
          <p className="text-xs mb-4">
            <span className="text-gray-500">Ordonnance N° :</span>{" "}
            <span className="font-mono">{sale.prescription_number}</span>
          </p>
        )}

        {/* Lignes */}
        <table className="w-full mb-6">
          <thead className="bg-gray-100 border-b-2 border-gray-300">
            <tr>
              <th className="text-left p-2">Désignation</th>
              <th className="text-center p-2">Qté</th>
              <th className="text-right p-2">PU HT</th>
              <th className="text-center p-2">TVA</th>
              <th className="text-right p-2">PU TTC</th>
              <th className="text-right p-2">Total TTC</th>
            </tr>
          </thead>
          <tbody>
            {sale.items.map((it) => {
              const product = productsById[it.product_id];
              const rate = product ? parseFloat(product.vat_rate) : 0.07;
              const puTtc = parseFloat(it.unit_price_ttc);
              const puHt = puTtc / (1 + rate);
              return (
                <tr key={it.id} className="border-b border-gray-200">
                  <td className="p-2">
                    <div className="font-medium">{product?.name ?? "—"}</div>
                    {product?.code && (
                      <div className="text-xs text-gray-500">
                        {product.code}
                        {product.dci && ` · ${product.dci}`}
                      </div>
                    )}
                  </td>
                  <td className="text-center p-2">{it.quantity}</td>
                  <td className="text-right p-2 font-mono">{puHt.toFixed(2)}</td>
                  <td className="text-center p-2">{(rate * 100).toFixed(0)}%</td>
                  <td className="text-right p-2 font-mono">{puTtc.toFixed(2)}</td>
                  <td className="text-right p-2 font-mono font-medium">
                    {parseFloat(it.line_total_ttc).toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Totaux */}
        <div className="flex justify-end mb-6">
          <table className="w-80">
            <tbody>
              <tr>
                <td className="py-1 text-gray-600">Sous-total HT</td>
                <td className="text-right py-1 font-mono">{formatMAD(sale.subtotal_ht)}</td>
              </tr>
              {parseFloat(sale.total_discount) > 0 && (
                <tr>
                  <td className="py-1 text-gray-600">Remise</td>
                  <td className="text-right py-1 font-mono">-{formatMAD(sale.total_discount)}</td>
                </tr>
              )}
              {vatBreakdown.map((v) => (
                <tr key={v.rate}>
                  <td className="py-1 text-gray-600">TVA {v.rate}%</td>
                  <td className="text-right py-1 font-mono">{formatMAD(v.vat)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-primary">
                <td className="py-2 font-bold text-base">TOTAL TTC</td>
                <td className="text-right py-2 font-mono font-bold text-lg text-primary">
                  {formatMAD(sale.total_ttc)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Mentions légales */}
        <div className="mt-12 pt-6 border-t text-xs text-gray-600 space-y-1">
          <p className="font-medium">Mentions légales</p>
          <p>
            Conformément à la réglementation marocaine, cette facture est soumise à la TVA selon
            les taux applicables aux médicaments et produits pharmaceutiques.
          </p>
          {pharmacy?.if_number && (
            <p>TVA acquittée d'après les encaissements. IF : {pharmacy.if_number}.</p>
          )}
          <p className="text-center mt-4 text-gray-400">Merci de votre confiance.</p>
        </div>
      </div>

      <style>{`
        @media print {
          @page {
            size: A4;
            margin: 0;
          }
          body {
            background: white !important;
          }
          .invoice {
            box-shadow: none;
            margin: 0;
            max-width: 100%;
          }
        }
      `}</style>
    </div>
  );
}
