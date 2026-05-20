# PharmaOS — Guide pour Claude Code

> Ce fichier est lu automatiquement par Claude Code à chaque session.
> Il contient le contexte projet, les conventions, l'état actuel et les pièges à connaître.
> **Le projet est en français** : commentaires, libellés UI, messages d'erreur utilisateur en français.

---

## 1. C'est quoi PharmaOS

SaaS de gestion de pharmacie pour le marché marocain (et francophone africain à terme).
Objectif : concurrencer et dépasser les logiciels existants (Gestofi, Sobrus, Gebs Pharma)
en offrant ce qu'ils n'ont pas : API REST publique, vraie architecture cloud/SaaS,
support mobile, intégration IA, UX moderne, onboarding self-serve.

**Multi-tenant strict** : chaque pharmacie est un tenant isolé via `pharmacy_id`.
Toute requête de données DOIT filtrer par `pharmacy_id`. C'est une exigence de sécurité absolue.

Pricing (MAD/mois) : Trial (gratuit 30j) → Starter 299 → Pro 599 → Enterprise (sur mesure).

---

## 2. Stack technique

**Backend**
- FastAPI (Python 3.12)
- PostgreSQL 16 (avec extension `pg_trgm` pour recherche floue sur noms de médicaments / DCI)
- Redis (cache, rate limiting)
- SQLAlchemy 2.0 **async** (ORM)
- Alembic (migrations)
- Anthropic Claude API (features IA, modèle `claude-sonnet-4-20250514`)

**Frontend**
- React 18 + TypeScript
- Vite (build)
- TailwindCSS + shadcn/ui (composants)
- TanStack Query (`@tanstack/react-query`) pour le data fetching
- React Router

**Infra**
- Docker Compose (api, db, redis, frontend)
- Caddy (HTTPS auto en prod sur Contabo VPS)

---

## 3. Architecture & arborescence

```
pharmaos/
├── backend/
│   ├── app/
│   │   ├── api/v1/        # Routers FastAPI (un par domaine)
│   │   ├── models/        # Modèles SQLAlchemy
│   │   ├── schemas/       # Schémas Pydantic (Create / Out / Detail)
│   │   ├── services/      # Logique métier (1 service par domaine)
│   │   ├── core/          # config, security, permissions, deps
│   │   └── scripts/seed.py
│   ├── alembic/versions/  # Migrations
│   └── tests/             # Tests E2E pytest async
└── frontend/
    └── src/
        ├── pages/         # Une page par écran
        ├── components/    # Composants partagés (Layout, CommandPalette, Term...)
        └── lib/           # api.ts (axios), utils.ts (formatMAD, formatDate)
```

### Routers (`backend/app/api/v1/`)
`auth`, `products`, `sales`, `clients`, `suppliers`, `third_party`, `operations`,
`analytics`, `ai`, `developer`.

### Modèles (`backend/app/models/`)
`user`, `pharmacy`, `product` (+ `ProductLot`), `sale` (+ `SaleItem`), `client`,
`supplier` (+ `SupplierProduct`, `PurchaseOrder`, `DeliveryNote`, `SupplierInvoice`,
`SupplierPayment`, `SupplierReturn`), `third_party` (payeurs, claims, bordereaux, paiements),
`operations` (clôture journée, ordonnancier, échanges, charges, inventaires),
`api_key`, `webhook`.

### Services (`backend/app/services/`)
`sale_service`, `supplier_service`, `third_party_service`, `credit_service`,
`day_closing_service`, `purchase_proposal_service`, `notification_service`,
`api_key_service`, `rate_limit_service`, `webhook_service`.

### Pages frontend (`frontend/src/pages/`)
`Login`, `Register`, `Dashboard`, `Caisse` (caisse titulaire), `Cashier` (mode kiosk caissier),
`Stock`, `Clients`, `Fournisseurs` (+ `SupplierOperations` pour les onglets achats),
`TiersPayants`, `Analytics`, `Operations`, `ClotureJournee`, `Pharmabot`, `Developers`,
`Ticket`, `Invoice`.

---

## 4. Conventions à RESPECTER absolument

### 4.1 Multi-tenant
- **Toute** requête sur des données métier filtre par `pharmacy_id`.
- Les dépendances `get_current_pharmacy_id` / `get_current_user` (dans `app/api/deps.py`)
  fournissent le tenant. Ne jamais retourner de données d'un autre tenant.
- Il existe `tests/test_tenant_isolation.py` — toute nouvelle ressource doit avoir
  un test d'isolation tenant.

### 4.2 Migrations Alembic — TOUJOURS idempotentes
- La migration `0002_create_all` crée TOUTES les tables via `Base.metadata.create_all()`.
  Donc les migrations suivantes (0003+) peuvent rencontrer des colonnes/tables déjà existantes.
- **Toute migration qui ajoute une colonne DOIT vérifier son existence d'abord** avec ce helper :
  ```python
  from sqlalchemy import inspect
  def _column_exists(table_name: str, column_name: str) -> bool:
      bind = op.get_bind()
      inspector = inspect(bind)
      return column_name in [c["name"] for c in inspector.get_columns(table_name)]
  ```
  Voir `0004_webhook_secret_encrypted.py` et `0006_lot_ppv.py` comme modèles.
- Migrations actuelles : `0001_init_extensions`, `0002_create_all`, `0003_developer_tables`,
  `0004_webhook_secret_encrypted`, `0005_operations_tables`, `0006_lot_ppv`.

### 4.3 Ordre des routes FastAPI — PIÈGE FRÉQUENT
- Les routes paramétrées `/{id}` doivent être déclarées **APRÈS** les routes littérales.
- Exemple du bug rencontré : `GET /suppliers/{supplier_id}` déclaré avant `/suppliers/payments`
  → FastAPI parse "payments" comme un UUID → erreur 422.
- **Convention** : dans chaque router, mettre les routes `/{param}` EN FIN DE FICHIER.
  Voir le commentaire "Routes paramétrées (DÉFINIES EN DERNIER)" dans `suppliers.py`.

### 4.4 SQLAlchemy async — eager loading des relations
- Sérialiser un objet ORM avec une relation non chargée (`.items`, `.claims`...) provoque
  un crash `MissingGreenlet` (lazy-load interdit en async).
- **Toujours** charger les relations explicitement avant de retourner :
  ```python
  from sqlalchemy.orm import selectinload
  result = await db.execute(
      select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(...)
  )
  ```

### 4.5 Sécurité / mots de passe
- On utilise **bcrypt directement** (paquet `bcrypt==4.1.3`), PAS passlib (incompatibilités
  rencontrées). Voir `app/core/security.py`. Troncature à 72 bytes avant hash.

### 4.6 Tests
- Tests E2E avec pytest + httpx async (`AsyncClient` + `ASGITransport`).
- Fixtures dans `tests/conftest.py` : `client`, `registered_user`, `auth_headers`.
- Pattern : créer les données via l'API (POST), puis vérifier via l'API.
- **Lancer les tests** : `cd backend && python -m pytest` (≈ 92 tests, ~130s).
- Toute nouvelle feature = nouveau test E2E qui valide le workflow complet.
- Convention de nommage : `test_<domaine>_workflow.py` pour les workflows métier.

### 4.7 Décimaux & argent
- Tout l'argent est en `Decimal` (jamais float). Numeric(12,4) pour les prix, (12,2) pour totaux.
- Attention : `sum()` sur une liste vide retourne `int 0` (pas de `.quantize()`).
  Utiliser `sum(generateur, Decimal("0"))`.
- TVA pharmacie Maroc : 7% par défaut (`vat_rate = 0.07`).

### 4.8 Frontend
- Data fetching via TanStack Query (`useQuery` / `useMutation`).
- Client API : `import { api, extractErrorMessage } from "@/lib/api"`.
- Formatage : `formatMAD()` et `formatDate()` depuis `@/lib/utils`.
- Toasts : `import { toast } from "@/components/ui/toast"`.
- Glossaire métier : composant `<Term code="CNOPS" />` explique les termes au survol.
- **Build** : `cd frontend && npm run build` (doit passer clean avant tout commit).
- Ne PAS utiliser localStorage/sessionStorage dans les artifacts (non supporté).

---

## 5. État actuel du projet (à jour)

**92 tests backend verts.** Build frontend clean. Version frontend 0.3.0.

### Modules fonctionnels et branchés (back + front)
- **Auth** : register avec auto-création tenant, login, refresh, /me. 4 rôles
  (owner / titulaire / adjoint / caissier) × ~20 permissions atomiques (`app/core/permissions.py`).
- **Produits** : CRUD, recherche code-barres/DCI, lots, alertes stock bas & péremption.
- **Caisse / Ventes** : décrément stock auto FEFO, points fidélité, annulation avec
  restauration stock, stats du jour. Mode caissier kiosk (`Cashier.tsx`).
- **Prix au lot (PPV par lot)** 🌟 : besoin terrain marocain. Le PPV est imprimé sur la boîte
  et change entre arrivages. Chaque `ProductLot` porte son `sale_price_ttc`. À la vente,
  logique **FEFO** : on prend le lot qui périme le plus tôt et SON prix.
  Priorité de prix : prix explicite > PPV lot FEFO > prix référence produit.
  PPV renseigné à la réception du BL (saisie manuelle ou hérité du catalogue fournisseur).
- **Achats / Fournisseurs** : page 7 onglets (Fournisseurs, Proposition, Commandes, Bons de
  livraison, Factures, Paiements, Retours). Réception BL → stock auto + création de lots.
- **Proposition de commande** : 2 modes (par ventes sur période / par seuil min-Max),
  filtrable par fournisseur, génère un BC, export CSV. (`purchase_proposal_service.py`)
- **Tiers Payants** : page 4 onglets (Organismes CNOPS/CNSS/mutuelles, Demandes/claims,
  Bordereaux + soumission, Paiements).
- **Opérations** : clôture de journée, ordonnancier, échanges confrères, charges, inventaires.
- **IA** : Pharmabot (chat), vérif interactions médicamenteuses, suggestions de commande,
  OCR ordonnance, analyse ventes. (`ai.py` + `Pharmabot.tsx`)
- **Portail développeur** : clés API, webhooks, doc (page `/developers`).
- **CommandPalette** (⌘K) pour navigation rapide.

---

## 6. Reste à faire (backlog priorisé)

1. **Crédits clients** (partiellement fait) : entrées de crédit, échéancier, impayés,
   relances WhatsApp/SMS (`credit_service.py` existe, à compléter au front).
2. **Analytics** : 4 graphiques sur 5 pas encore affichés au front
   (sales-timeseries, top-products, payment-methods-breakdown, hourly-distribution).
   Les endpoints backend existent dans `analytics.py`.
3. **Petits manques** : bouton annulation vente au front (`/sales/{id}/cancel` existe),
   affichage alerte expiration produits (`/products/alerts/expiring` existe).
4. **Vue catalogue fournisseur complète** au front (produits disponibles par fournisseur).
5. **Features Gebs non faites** : multi-comptoirs ("2ème comptoir"), devis clients,
   audit log changements de prix ("produits rectifiés").
6. (Gros chantier, plus tard) connexion temps réel aux grossistes en ligne.

> ⚠️ **Conseil stratégique récurrent** : ne pas copier Gebs feature par feature à partir de
> screenshots. Faire TESTER PharmaOS par un vrai pharmacien (surtout la caisse + le prix au lot
> qui répondent à un besoin réel exprimé) avant de construire plus. Risque sinon : reconstruire
> des features que personne n'utilise.

---

## 7. Commandes utiles

### Docker (depuis la racine du projet)
```bash
# Démarrage / rebuild après changement de code
docker compose up -d --build

# Reset complet (efface la DB — uniquement en dev !)
docker compose down -v
docker compose up -d --build
sleep 10
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed
```

### Backend
```bash
cd backend
python -m pytest                          # tous les tests
python -m pytest tests/test_sales.py -x   # un fichier, stop au 1er échec
alembic upgrade head                      # appliquer migrations
alembic revision -m "description"         # créer une migration (puis la rendre idempotente !)
```

### Frontend
```bash
cd frontend
npm run dev      # serveur de dev (localhost:5173)
npm run build    # build de prod (doit passer clean)
```

### Identifiants de démo (après seed)
`demo@pharmaos.ma` / `demo1234` (rôle owner, Pharmacie Atlas).

### Variables d'env (`.env` à la racine, NON versionné)
`SECRET_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL=claude-sonnet-4-20250514`.

---

## 8. Workflow de travail attendu

1. Avant de coder une feature, lire le service et le router du domaine concerné.
2. Backend d'abord (modèle → migration idempotente → schéma → service → router), puis test E2E.
3. Lancer `python -m pytest` et vérifier que TOUT passe (pas seulement le nouveau test).
4. Frontend ensuite, puis `npm run build` pour valider.
5. Respecter les conventions de la section 4 (multi-tenant, ordre routes, selectinload, Decimal).
6. Bien penser au contexte marocain (PPV imprimé sur boîte, TVA 7%, CNOPS/CNSS, MAD/DH).
