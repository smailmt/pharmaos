import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { RequireAuth } from "@/components/RequireAuth";
import { Toaster } from "@/components/ui/toast";
import { useAuth } from "@/stores/auth";
import { LoginPage } from "@/pages/Login";
import { RegisterPage } from "@/pages/Register";
import { DashboardPage } from "@/pages/Dashboard";
import { CaissePage } from "@/pages/Caisse";
import { CashierPage } from "@/pages/Cashier";
import { StockPage } from "@/pages/Stock";
import { ClientsPage } from "@/pages/Clients";
import { FournisseursPage } from "@/pages/Fournisseurs";
import { AnalyticsPage } from "@/pages/Analytics";
import { DevelopersPage } from "@/pages/Developers";
import { TicketPage } from "@/pages/Ticket";
import { InvoicePage } from "@/pages/Invoice";
import { ClotureJourneePage } from "@/pages/ClotureJournee";
import { PharmabotPage } from "@/pages/Pharmabot";
import { TiersPayantsPage } from "@/pages/TiersPayants";
import {
  OrdonnancierPage,
  ChargesPage,
  EchangesPage,
  InventairePage,
} from "@/pages/Operations";

/**
 * Redirige les caissiers vers /cashier (mode kiosk) au lieu du dashboard titulaire.
 */
function HomeRouter() {
  const { user } = useAuth();
  if (user?.role === "caissier") {
    return <Navigate to="/cashier" replace />;
  }
  return <DashboardPage />;
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Mode caissier : plein écran, sans layout titulaire */}
        <Route
          path="/cashier"
          element={
            <RequireAuth>
              <CashierPage />
            </RequireAuth>
          }
        />

        <Route
          path="/sales/:id/ticket"
          element={
            <RequireAuth>
              <TicketPage />
            </RequireAuth>
          }
        />
        <Route
          path="/sales/:id/invoice"
          element={
            <RequireAuth>
              <InvoicePage />
            </RequireAuth>
          }
        />

        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<HomeRouter />} />
          <Route path="caisse" element={<CaissePage />} />
          <Route path="stock" element={<StockPage />} />
          <Route path="clients" element={<ClientsPage />} />
          <Route path="fournisseurs" element={<FournisseursPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="developers" element={<DevelopersPage />} />

          {/* Modules opérationnels (Jour 8) */}
          <Route path="ordonnancier" element={<OrdonnancierPage />} />
          <Route path="charges" element={<ChargesPage />} />
          <Route path="echanges" element={<EchangesPage />} />
          <Route path="inventaire" element={<InventairePage />} />
          <Route path="cloture" element={<ClotureJourneePage />} />
          <Route path="pharmabot" element={<PharmabotPage />} />
          <Route path="tiers-payants" element={<TiersPayantsPage />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  );
}
