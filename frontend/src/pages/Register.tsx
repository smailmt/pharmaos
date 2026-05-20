import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Pill, Loader2, Check, ArrowLeft, ArrowRight } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toast";
import { cn, formatMAD } from "@/lib/utils";

interface Plan {
  id: string;
  name: string;
  price_mad: number;
  description: string;
  features: string[];
  highlighted?: boolean;
}

const plans: Plan[] = [
  {
    id: "trial",
    name: "Essai gratuit",
    price_mad: 0,
    description: "30 jours pour évaluer",
    features: [
      "Toutes les fonctionnalités Pro",
      "Jusqu'à 200 produits",
      "1 utilisateur",
      "Support email",
    ],
  },
  {
    id: "starter",
    name: "Starter",
    price_mad: 299,
    description: "Petite pharmacie",
    features: [
      "Caisse, stock, clients, crédits",
      "Produits illimités",
      "2 utilisateurs",
      "Tiers payants (CNSS, CNOPS, RAMED)",
      "Support email",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price_mad: 599,
    description: "Pharmacie moderne",
    features: [
      "Tout Starter +",
      "5 utilisateurs",
      "IA Claude (PharmaBot, interactions)",
      "API publique OpenAPI",
      "Fournisseurs & commandes",
      "Support prioritaire",
    ],
    highlighted: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price_mad: 0,
    description: "Multi-officines",
    features: [
      "Tout Pro +",
      "Utilisateurs illimités",
      "Multi-pharmacies",
      "Intégrations sur-mesure",
      "Account manager dédié",
    ],
  },
];

export function RegisterPage() {
  const navigate = useNavigate();
  const { setAuth, isAuthenticated } = useAuth();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  const [selectedPlan, setSelectedPlan] = useState<string>("trial");
  const [form, setForm] = useState({
    // Pharmacie
    pharmacy_name: "",
    pharmacy_city: "",
    pharmacy_ice: "",
    // User
    email: "",
    password: "",
    full_name: "",
  });

  if (isAuthenticated()) return <Navigate to="/" replace />;

  const update = (k: keyof typeof form, v: string) => setForm({ ...form, [k]: v });

  const canStep2 = form.pharmacy_name.trim().length >= 2;
  const canSubmit =
    canStep2 &&
    form.email.length > 3 &&
    form.password.length >= 8 &&
    form.full_name.trim().length >= 2;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setLoading(true);
    try {
      const payload = {
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        pharmacy: {
          name: form.pharmacy_name,
          city: form.pharmacy_city || null,
          ice: form.pharmacy_ice || null,
        },
        plan: selectedPlan,
      };
      const { data: tokens } = await api.post("/auth/register", payload);
      const { data: user } = await api.get("/auth/me", {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      });
      setAuth(tokens.access_token, tokens.refresh_token, user);
      toast.success("Bienvenue dans PharmaOS !", "Votre pharmacie est prête.");
      navigate("/");
    } catch (err) {
      toast.error("Inscription impossible", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-primary/10 py-12 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 mb-3">
            <div className="h-12 w-12 rounded-xl bg-primary flex items-center justify-center">
              <Pill className="h-6 w-6 text-primary-foreground" />
            </div>
            <h1 className="text-2xl font-bold">PharmaOS</h1>
          </div>
          <h2 className="text-3xl font-bold tracking-tight">Lancez votre pharmacie en ligne</h2>
          <p className="text-muted-foreground mt-2">
            Commencez gratuitement, sans carte bancaire. Annulation à tout moment.
          </p>
        </div>

        {/* Stepper */}
        <div className="flex items-center justify-center mb-8 gap-2 text-sm">
          <StepIndicator n={1} label="Plan" active={step === 1} done={step > 1} />
          <div className="h-px w-12 bg-border" />
          <StepIndicator n={2} label="Pharmacie" active={step === 2} done={step > 2} />
          <div className="h-px w-12 bg-border" />
          <StepIndicator n={3} label="Compte" active={step === 3} done={false} />
        </div>

        {step === 1 && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {plans.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedPlan(p.id)}
                  className={cn(
                    "text-left rounded-lg border-2 p-5 bg-card transition-all",
                    selectedPlan === p.id
                      ? "border-primary shadow-lg scale-[1.02]"
                      : "border-border hover:border-primary/30",
                    p.highlighted && selectedPlan !== p.id && "border-primary/30"
                  )}
                >
                  {p.highlighted && (
                    <div className="inline-block px-2 py-0.5 bg-primary/10 text-primary text-xs font-medium rounded-full mb-2">
                      Recommandé
                    </div>
                  )}
                  <h3 className="font-bold text-lg">{p.name}</h3>
                  <p className="text-xs text-muted-foreground mb-3">{p.description}</p>
                  <div className="mb-4">
                    {p.price_mad === 0 ? (
                      <p className="text-2xl font-bold">{p.id === "enterprise" ? "Sur devis" : "Gratuit"}</p>
                    ) : (
                      <>
                        <span className="text-2xl font-bold">{formatMAD(p.price_mad)}</span>
                        <span className="text-sm text-muted-foreground"> / mois</span>
                      </>
                    )}
                  </div>
                  <ul className="space-y-1.5 text-sm">
                    {p.features.map((f, i) => (
                      <li key={i} className="flex gap-2">
                        <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </button>
              ))}
            </div>
            <div className="flex justify-end">
              <Button onClick={() => setStep(2)} size="lg">
                Continuer <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <Card className="max-w-md mx-auto">
            <CardHeader>
              <CardTitle>Votre pharmacie</CardTitle>
              <CardDescription>Ces informations apparaîtront sur vos factures</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label>Nom de la pharmacie *</Label>
                <Input
                  value={form.pharmacy_name}
                  onChange={(e) => update("pharmacy_name", e.target.value)}
                  placeholder="Pharmacie Al Andalous"
                />
              </div>
              <div className="space-y-1">
                <Label>Ville</Label>
                <Input
                  value={form.pharmacy_city}
                  onChange={(e) => update("pharmacy_city", e.target.value)}
                  placeholder="Casablanca"
                />
              </div>
              <div className="space-y-1">
                <Label>ICE (optionnel, modifiable plus tard)</Label>
                <Input
                  value={form.pharmacy_ice}
                  onChange={(e) => update("pharmacy_ice", e.target.value)}
                  placeholder="000000000000000"
                />
              </div>
              <div className="flex justify-between pt-2">
                <Button variant="outline" onClick={() => setStep(1)}>
                  <ArrowLeft className="h-4 w-4 mr-2" /> Retour
                </Button>
                <Button onClick={() => setStep(3)} disabled={!canStep2}>
                  Continuer <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 3 && (
          <Card className="max-w-md mx-auto">
            <CardHeader>
              <CardTitle>Votre compte</CardTitle>
              <CardDescription>Vous serez l'administrateur de l'officine</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label>Nom complet *</Label>
                <Input
                  value={form.full_name}
                  onChange={(e) => update("full_name", e.target.value)}
                  placeholder="Dr. Karim Benali"
                />
              </div>
              <div className="space-y-1">
                <Label>Email *</Label>
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => update("email", e.target.value)}
                  placeholder="vous@pharmacie.ma"
                />
              </div>
              <div className="space-y-1">
                <Label>Mot de passe * (min. 8 caractères)</Label>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => update("password", e.target.value)}
                />
              </div>
              <div className="flex justify-between pt-2">
                <Button variant="outline" onClick={() => setStep(2)} disabled={loading}>
                  <ArrowLeft className="h-4 w-4 mr-2" /> Retour
                </Button>
                <Button onClick={handleSubmit} disabled={!canSubmit || loading}>
                  {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  Créer ma pharmacie
                </Button>
              </div>
              <p className="text-xs text-center text-muted-foreground pt-2">
                Déjà un compte ? <Link to="/login" className="text-primary hover:underline">Se connecter</Link>
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function StepIndicator({
  n,
  label,
  active,
  done,
}: {
  n: number;
  label: string;
  active: boolean;
  done: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          "h-8 w-8 rounded-full flex items-center justify-center font-semibold text-sm",
          active
            ? "bg-primary text-primary-foreground"
            : done
            ? "bg-primary/20 text-primary"
            : "bg-muted text-muted-foreground"
        )}
      >
        {done ? <Check className="h-4 w-4" /> : n}
      </div>
      <span className={cn("font-medium", active ? "text-foreground" : "text-muted-foreground")}>
        {label}
      </span>
    </div>
  );
}
