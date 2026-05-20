import { useState } from "react";
import { useNavigate, Navigate, Link } from "react-router-dom";
import { Pill, Loader2 } from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/toast";

export function LoginPage() {
  const navigate = useNavigate();
  const { setAuth, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("demo@pharmaos.ma");
  const [password, setPassword] = useState("demo1234");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated()) return <Navigate to="/" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data: tokens } = await api.post("/auth/login", { email, password });
      // Récupérer le user
      const tempToken = tokens.access_token;
      const { data: user } = await api.get("/auth/me", {
        headers: { Authorization: `Bearer ${tempToken}` },
      });
      setAuth(tokens.access_token, tokens.refresh_token, user);
      toast.success("Bienvenue", user.full_name);
      navigate("/");
    } catch (err) {
      toast.error("Échec de connexion", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/5 via-background to-primary/10 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto h-14 w-14 rounded-xl bg-primary flex items-center justify-center">
            <Pill className="h-7 w-7 text-primary-foreground" />
          </div>
          <div>
            <CardTitle className="text-2xl">PharmaOS</CardTitle>
            <CardDescription className="mt-1">
              Connectez-vous à votre pharmacie
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              Se connecter
            </Button>
            <p className="text-xs text-center text-muted-foreground pt-2">
              Démo : <span className="font-mono">demo@pharmaos.ma</span> / <span className="font-mono">demo1234</span>
            </p>
            <p className="text-sm text-center pt-2 border-t mt-4 pt-4">
              Pas encore de compte ?{" "}
              <Link to="/register" className="text-primary hover:underline font-medium">
                Créer ma pharmacie
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
