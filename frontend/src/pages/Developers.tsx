import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Key,
  Webhook,
  Plus,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
  Code2,
  ExternalLink,
  Loader2,
  Clock,
} from "lucide-react";
import { api, extractErrorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";

interface ApiKey {
  id: string;
  name: string;
  description: string | null;
  key_prefix: string;
  scopes: string | null;
  rate_limit_per_min: number | null;
  last_used_at: string | null;
  usage_count: number;
  is_active: boolean;
  revoked_at: string | null;
  expires_at: string | null;
  created_at: string;
}

interface ApiKeyCreated extends ApiKey {
  key: string; // plaintext, une seule fois
}

interface WebhookEndpoint {
  id: string;
  url: string;
  description: string | null;
  secret_prefix: string;
  events: string[];
  is_active: boolean;
  last_delivery_at: string | null;
  last_success_at: string | null;
  consecutive_failures: number;
  created_at: string;
}

interface WebhookCreated extends WebhookEndpoint {
  secret: string;
}

interface SupportedEvent {
  type: string;
  description: string;
  example_data: Record<string, unknown>;
}

export function DevelopersPage() {
  const [tab, setTab] = useState<"keys" | "webhooks" | "docs">("keys");

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <header>
        <div className="flex items-center gap-2 mb-1">
          <Code2 className="h-6 w-6 text-primary" />
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Espace développeurs</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Intégrez PharmaOS à vos outils : compta, ERP, mobile, scripts. Notre API publique est notre signature —
          aucun concurrent ne la propose.
        </p>
      </header>

      <div className="border-b flex gap-1 overflow-x-auto">
        <TabButton active={tab === "keys"} onClick={() => setTab("keys")}>
          <Key className="h-4 w-4" />
          Clés API
        </TabButton>
        <TabButton active={tab === "webhooks"} onClick={() => setTab("webhooks")}>
          <Webhook className="h-4 w-4" />
          Webhooks
        </TabButton>
        <TabButton active={tab === "docs"} onClick={() => setTab("docs")}>
          <Code2 className="h-4 w-4" />
          Démarrage
        </TabButton>
      </div>

      {tab === "keys" && <ApiKeysTab />}
      {tab === "webhooks" && <WebhooksTab />}
      {tab === "docs" && <DocsTab />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
        active
          ? "border-primary text-primary"
          : "border-transparent text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

// =================== API Keys ===================
function ApiKeysTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [showKey, setShowKey] = useState<string | null>(null);

  const { data: keys, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get<ApiKey[]>("/developer/api-keys").then((r) => r.data),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.delete(`/developer/api-keys/${id}`),
    onSuccess: () => {
      toast.success("Clé révoquée");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">Clés API</h2>
          <p className="text-sm text-muted-foreground">
            Authentifiez vos intégrations avec <code className="bg-muted px-1 py-0.5 rounded text-xs">X-API-Key</code>.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Nouvelle clé
        </Button>
      </div>

      <Card>
        {isLoading ? (
          <div className="p-6 space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : !keys || keys.length === 0 ? (
          <EmptyState
            Icon={Key}
            title="Aucune clé API"
            description="Créez votre première clé pour commencer à intégrer PharmaOS à vos outils."
            action={<Button onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4 mr-1" />Créer une clé</Button>}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nom</TableHead>
                <TableHead>Préfixe</TableHead>
                <TableHead>Dernière utilisation</TableHead>
                <TableHead className="text-right">Appels</TableHead>
                <TableHead>État</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.map((k) => (
                <TableRow key={k.id}>
                  <TableCell>
                    <p className="font-medium">{k.name}</p>
                    {k.description && (
                      <p className="text-xs text-muted-foreground">{k.description}</p>
                    )}
                  </TableCell>
                  <TableCell>
                    <code className="font-mono text-xs bg-muted px-2 py-1 rounded">
                      {k.key_prefix}…
                    </code>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {k.last_used_at ? formatDateTime(k.last_used_at) : "Jamais"}
                  </TableCell>
                  <TableCell className="text-right text-sm">{k.usage_count}</TableCell>
                  <TableCell>
                    {k.is_active ? (
                      <Badge variant="success">Active</Badge>
                    ) : (
                      <Badge variant="destructive">Révoquée</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {k.is_active && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          if (confirm(`Révoquer la clé "${k.name}" ?`)) revoke.mutate(k.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreateApiKeyDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(plaintextKey) => {
          setCreateOpen(false);
          setShowKey(plaintextKey);
          qc.invalidateQueries({ queryKey: ["api-keys"] });
        }}
      />

      <RevealSecretDialog
        title="Votre nouvelle clé API"
        description="Copiez-la maintenant : pour des raisons de sécurité, elle ne sera plus jamais affichée."
        secret={showKey}
        onClose={() => setShowKey(null)}
      />
    </div>
  );
}

function CreateApiKeyDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: (key: string) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [env, setEnv] = useState<"live" | "test">("live");

  const mutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<ApiKeyCreated>("/developer/api-keys", {
        name, description: description || null, env,
      });
      return data;
    },
    onSuccess: (data) => {
      onCreated(data.key);
      setName("");
      setDescription("");
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle clé API</DialogTitle>
          <DialogDescription>
            Cette clé pourra accéder à toutes les ressources de votre pharmacie.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label className="text-xs">Nom *</Label>
            <Input
              placeholder="Ex: Intégration Sage compta"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Description</Label>
            <Input
              placeholder="Optionnel"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Environnement</Label>
            <div className="flex gap-2">
              <button
                onClick={() => setEnv("live")}
                className={`flex-1 px-3 py-2 rounded-md border text-sm transition ${
                  env === "live" ? "border-primary bg-primary/5" : "border-input"
                }`}
              >
                <span className="font-mono">pk_live_</span> — Production
              </button>
              <button
                onClick={() => setEnv("test")}
                className={`flex-1 px-3 py-2 rounded-md border text-sm transition ${
                  env === "test" ? "border-primary bg-primary/5" : "border-input"
                }`}
              >
                <span className="font-mono">pk_test_</span> — Tests
              </button>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button onClick={() => mutation.mutate()} disabled={!name || mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =================== Webhooks ===================
function WebhooksTab() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [showSecret, setShowSecret] = useState<string | null>(null);

  const { data: hooks, isLoading } = useQuery({
    queryKey: ["webhooks"],
    queryFn: () => api.get<WebhookEndpoint[]>("/developer/webhooks").then((r) => r.data),
  });

  const del = useMutation({
    mutationFn: (id: string) => api.delete(`/developer/webhooks/${id}`),
    onSuccess: () => {
      toast.success("Webhook supprimé");
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">Webhooks</h2>
          <p className="text-sm text-muted-foreground">
            Recevez les événements de votre pharmacie en temps réel sur vos URL HTTPS.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Nouveau webhook
        </Button>
      </div>

      <Card>
        {isLoading ? (
          <div className="p-6 space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : !hooks || hooks.length === 0 ? (
          <EmptyState
            Icon={Webhook}
            title="Aucun webhook configuré"
            description="Ajoutez une URL pour recevoir les événements (vente créée, stock bas, etc.)"
            action={<Button onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4 mr-1" />Ajouter un webhook</Button>}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>URL</TableHead>
                <TableHead>Events</TableHead>
                <TableHead>Dernière livraison</TableHead>
                <TableHead>État</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {hooks.map((h) => (
                <TableRow key={h.id}>
                  <TableCell>
                    <code className="font-mono text-xs">{h.url}</code>
                    {h.description && (
                      <p className="text-xs text-muted-foreground mt-1">{h.description}</p>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1 flex-wrap">
                      {h.events.map((e) => (
                        <Badge key={e} variant="outline" className="text-[10px]">{e}</Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {h.last_delivery_at ? formatDateTime(h.last_delivery_at) : "Jamais"}
                  </TableCell>
                  <TableCell>
                    {h.consecutive_failures > 0 ? (
                      <Badge variant="warning">
                        <AlertTriangle className="h-3 w-3 mr-1" />
                        {h.consecutive_failures} échecs
                      </Badge>
                    ) : h.is_active ? (
                      <Badge variant="success">Actif</Badge>
                    ) : (
                      <Badge variant="secondary">Inactif</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        if (confirm("Supprimer ce webhook ?")) del.mutate(h.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <CreateWebhookDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(secret) => {
          setCreateOpen(false);
          setShowSecret(secret);
          qc.invalidateQueries({ queryKey: ["webhooks"] });
        }}
      />

      <RevealSecretDialog
        title="Votre secret webhook"
        description="Utilisez ce secret pour vérifier la signature HMAC-SHA256 dans l'en-tête X-PharmaOS-Signature des requêtes entrantes."
        secret={showSecret}
        onClose={() => setShowSecret(null)}
      />
    </div>
  );
}

function CreateWebhookDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: (secret: string) => void;
}) {
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [events, setEvents] = useState<string[]>(["sale.created"]);

  const { data: supportedEvents } = useQuery({
    queryKey: ["supported-events"],
    queryFn: () => api.get<SupportedEvent[]>("/developer/events").then((r) => r.data),
    enabled: open,
  });

  const toggle = (ev: string) => {
    setEvents((prev) => (prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]));
  };

  const mutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<WebhookCreated>("/developer/webhooks", {
        url, events, description: description || null,
      });
      return data;
    },
    onSuccess: (data) => {
      onCreated(data.secret);
      setUrl("");
      setDescription("");
      setEvents(["sale.created"]);
    },
    onError: (err) => toast.error("Erreur", extractErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau webhook</DialogTitle>
          <DialogDescription>
            Recevez les événements souscrits en POST sur votre URL.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label className="text-xs">URL HTTPS *</Label>
            <Input
              type="url"
              placeholder="https://votre-app.com/pharmaos-webhook"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Description</Label>
            <Input
              placeholder="Optionnel"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Événements à recevoir *</Label>
            <div className="space-y-1.5 border rounded-md p-2 max-h-60 overflow-y-auto">
              {supportedEvents?.map((e) => (
                <label key={e.type} className="flex items-start gap-2 cursor-pointer p-1.5 hover:bg-muted/50 rounded">
                  <input
                    type="checkbox"
                    checked={events.includes(e.type)}
                    onChange={() => toggle(e.type)}
                    className="mt-0.5"
                  />
                  <div className="flex-1 min-w-0">
                    <code className="text-xs font-mono font-medium">{e.type}</code>
                    <p className="text-xs text-muted-foreground">{e.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!url || events.length === 0 || mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =================== Docs ===================
function DocsTab() {
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-lg font-semibold mb-2">Documentation interactive</h2>
        <p className="text-sm text-muted-foreground mb-3">
          Tous les 79+ endpoints sont documentés en OpenAPI avec exemples et schémas.
        </p>
        <div className="flex gap-2 flex-wrap">
          <Button asChild variant="outline">
            <a href="/docs" target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4 mr-1" />
              Swagger UI
            </a>
          </Button>
          <Button asChild variant="outline">
            <a href="/redoc" target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4 mr-1" />
              ReDoc
            </a>
          </Button>
          <Button asChild variant="outline">
            <a href="/openapi.json" target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4 mr-1" />
              openapi.json
            </a>
          </Button>
        </div>
      </div>

      <Card className="p-5">
        <h3 className="font-semibold mb-3">Exemple — Lister les produits</h3>
        <CodeBlock
          language="bash"
          code={`curl https://api.pharmaos.ma/api/v1/products \\
  -H "X-API-Key: pk_live_xxxxxxxxxxxxxxxxxxxx"`}
        />
      </Card>

      <Card className="p-5">
        <h3 className="font-semibold mb-3">Exemple — Créer une vente (Python)</h3>
        <CodeBlock
          language="python"
          code={`import httpx

API_KEY = "pk_live_xxxxxxxxxxxxxxxxxxxx"

response = httpx.post(
    "https://api.pharmaos.ma/api/v1/sales",
    headers={"X-API-Key": API_KEY},
    json={
        "items": [
            {"product_id": "uuid", "quantity": 2, "unit_price_ttc": "25.00"},
        ],
        "paid_cash": "50.00",
    },
)
sale = response.json()
print(f"Vente créée : {sale['sale_number']}")`}
        />
      </Card>

      <Card className="p-5">
        <h3 className="font-semibold mb-3">Exemple — Vérifier une signature webhook (Node.js)</h3>
        <CodeBlock
          language="javascript"
          code={`import crypto from "crypto";

function verifySignature(body, secret, signatureHeader) {
  // Header format: t=<timestamp>,v1=<hmac>
  const parts = Object.fromEntries(
    signatureHeader.split(",").map(p => p.split("="))
  );
  const signedPayload = \`\${parts.t}.\${body}\`;
  const expected = crypto.createHmac("sha256", secret)
    .update(signedPayload)
    .digest("hex");
  return crypto.timingSafeEqual(
    Buffer.from(expected, "hex"),
    Buffer.from(parts.v1, "hex")
  );
}

app.post("/pharmaos-webhook", (req, res) => {
  const valid = verifySignature(
    req.rawBody,
    process.env.PHARMAOS_WEBHOOK_SECRET,
    req.headers["x-pharmaos-signature"]
  );
  if (!valid) return res.status(401).send("Invalid signature");
  // Traiter req.body...
  res.status(200).send("OK");
});`}
        />
      </Card>
    </div>
  );
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      <div className="absolute top-2 right-2">
        <Button size="sm" variant="ghost" onClick={handleCopy} className="h-7 px-2">
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
        </Button>
      </div>
      <div className="text-xs text-muted-foreground uppercase mb-1">{language}</div>
      <pre className="bg-zinc-950 text-zinc-100 p-4 rounded-md overflow-x-auto text-xs leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// =================== Shared : Reveal secret ===================
function RevealSecretDialog({
  title,
  description,
  secret,
  onClose,
}: {
  title: string;
  description: string;
  secret: string | null;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  if (!secret) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(secret);
    setCopied(true);
    toast.success("Copié dans le presse-papiers");
  };

  return (
    <Dialog open={!!secret} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-600" />
            {title}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
          <p className="text-xs text-amber-900 mb-2 font-medium">
            ⚠️ Pour des raisons de sécurité, cette valeur ne sera plus affichée après fermeture.
          </p>
          <div className="flex items-center gap-2 bg-white border rounded-md p-2">
            <code className="font-mono text-xs flex-1 truncate select-all">{secret}</code>
            <Button size="sm" variant="outline" onClick={handleCopy}>
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            </Button>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={onClose}>J'ai bien copié la valeur</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
