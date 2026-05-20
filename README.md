# PharmaOS — SaaS de gestion de pharmacie (Maroc)

**Objectif : surpasser Gestofi et Sobrus** sur les axes API ouverte, cloud natif, IA intégrée, tiers payant flexible, gestion fournisseurs/crédits robuste.

## Stack

- **Backend** : FastAPI (Python 3.12), SQLAlchemy 2.0 async, PostgreSQL 16, Redis
- **Frontend** : React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui + TanStack Query
- **Auth** : JWT multi-tenant (isolation par pharmacie)
- **IA** : API Anthropic Claude (interactions médicamenteuses, suggestions, agent conversationnel)
- **Migrations** : Alembic
- **Conteneurisation** : Docker + Docker Compose

## Modules livrés

### Backend (Jours 1-2)
- Auth (register, login, refresh, /me) — multi-tenant
- Produits (CRUD, recherche barcode/DCI, alertes stock/péremption, lots)
- Ventes / caisse (auto-décrément stock, points fidélité, annulation)
- IA (interactions, suggestions commande, PharmaBot)
- **Clients** — fiche, historique, plafond de crédit, scoring
- **Crédits clients** — échéancier, paiements partiels, relances auto, balance âgée
- **Fournisseurs** — grossistes, labos, conditions commerciales, multi-fournisseurs
- **Commandes fournisseur** — bons de commande, réception BL, écarts, retours
- **Factures fournisseur** — comptes fournisseurs, paiements, balance âgée
- **Tiers payants** — système 100% générique (CNSS, CNOPS, RAMED, mutuelles), bordereaux, suivi remboursements

### Frontend (Jour 3)
- **Login** — JWT, persistence localStorage
- **Tableau de bord** — KPIs (produits, clients, stock faible, péremption), graphique balance âgée, alertes
- **Caisse (POS)** — recherche/scan produit, panier interactif (qté, prix, remise), client + tiers payant, encaissement multi-moyens (cash/carte/chèque/crédit), reçu, raccourci F2
- **Stock** — table filtrable, filtres "sous seuil" et "péremption proche", création produit, gestion lots
- **Clients** — table filtrable, drawer détail avec balance/échéancier/encaissement, création client

### Jour 4 — Polish + Tests + Onboarding
- **Page Fournisseurs (Achats)** — interface à 6 onglets exposant tout le workflow achat : Fournisseurs (liste + création), Commandes (BC avec lignes produits), Bons de livraison (réception → stock auto-incrémenté + lots), Factures, Paiements (multi-méthode), Retours
- **Tickets imprimables** (80mm) — format thermique, décomposition TVA par taux, paiements multi-moyens, rendu, fidélité, CSS `@media print`
- **Factures A4 imprimables** — header pro avec ICE/IF/RC/CNSS, encart client, table détaillée, mentions légales conformes DGI Maroc
- **Onboarding** — page Register 3 étapes (plan / pharmacie / compte), 4 plans tarifaires (Trial / Starter 299 / Pro 599 / Enterprise)
- **Polish UI** — composants Skeleton + EmptyState, Layout responsive avec sidebar mobile (overlay + Menu/X), padding adaptatif sur toutes les pages
- **Tests E2E** — 22 tests pytest couvrant Auth (8), Products (5), Sales (7), Multi-tenant isolation (2). Détection et correction d'un bug réel dans `update_risk_score` (`func.cast` mal utilisé)
- **CI GitHub Actions** — backend pytest + frontend build sur chaque push/PR

### Jour 5 — Le moat technique (API publique + Webhooks)
**Ceci est notre vrai différenciateur : ni Gestofi ni Sobrus ne le propose au Maroc.**
- **Clés API** — modèle `ApiKey` avec hash SHA-256 stocké (jamais la clé en clair), format `pk_live_*` / `pk_test_*`, préfixe visible pour identification, scopes, rate-limit, expiration optionnelle, stats `last_used_at`/`usage_count`
- **Auth duale** — chaque endpoint accepte `Authorization: Bearer <jwt>` OU `X-API-Key: pk_live_...` (dépendance `get_pharmacy_id_dual`)
- **Webhooks sortants** — abonnement à des événements, payload signé HMAC-SHA256, header `X-PharmaOS-Signature: t=<ts>,v1=<hmac>` style Stripe, table `webhook_deliveries` pour audit trail
- **Événements émis** — `sale.created` à chaque vente, `product.low_stock` à chaque passage sous seuil
- **Portail développeur** — page `/developers` à 3 onglets (Clés API / Webhooks / Démarrage), reveal-once du secret avec warning sécurité, exemples cURL/Python/Node.js avec bouton copier
- **OpenAPI polish** — tags par module, descriptions enrichies, métadonnées de contact, section authentification documentée
- **Tests E2E** — 11 nouveaux tests : création/révocation clé, isolation tenant, plaintext une seule fois, émission webhooks `sale.created` + `product.low_stock`, signature HMAC

### Jour 6 — Killers features (Mobile + IA wow effect)
**Ce qui fait dire "wow" en démo et signer des pharmacies.**
- **Worker de delivery webhooks** — retry exponentiel (1m, 5m, 30m, 2h, 12h), désactivation auto après 10 échecs consécutifs, audit complet via `webhook_deliveries`
- **Chiffrement Fernet** des secrets webhooks — `secret_encrypted` (AES-128-CBC + HMAC) avec clé maître dérivée du `SECRET_KEY`, permet de resigner après création (correction du design J5)
- **Rate limiting** par clé API — sliding window Redis (sorted set), 120 req/min par défaut, configurable par clé, fail-open si Redis indispo, header `Retry-After` sur 429
- **PWA** (Progressive Web App) — `manifest.webmanifest` avec shortcuts Caisse/Stock, service worker `sw.js` avec cache cache-first pour assets et network-first pour API, fallback offline JSON, installable sur écran d'accueil mobile
- **Scanner code-barres caméra** — composant `BarcodeScanner` avec `@zxing/browser`, détection EAN-13/UPC en temps réel, choix de caméra (frontale/arrière), overlay visuel de zone de scan, intégré directement dans la caisse
- **OCR ordonnance via Claude Vision** 🌟 — endpoint `/ai/prescription-ocr` qui prend une photo en base64, retourne les lignes structurées (médicament, DCI, dosage, quantité, durée, instructions, confiance), cross-check automatique avec le catalogue local, dialog UI complet avec preview image, états de chargement, warnings IA, sélection par ligne, ajout en un clic au panier
- **Tests E2E** — 9 nouveaux tests : crypto roundtrip + non-déterminisme Fernet, secret webhook chiffré en BDD, rate limit fail-open, OCR auth requise + base64 invalide, worker delivery succès + retry sur échec avec `next_retry_at`

### Jour 7 — Sprint final (Offline + Analytics + Notifs + Anomalies + Déploiement)
**Le dernier kilomètre vers la production.**
- **Mode hors-ligne complet caisse** — `lib/offline-db.ts` avec IndexedDB (wrapper `idb`), cache produits + queue ventes pending, store Zustand `useOffline` avec sync auto au retour réseau, polling 30s, badge réseau dans topbar (en ligne / hors ligne / N à synchroniser), bascule transparente : la vente passe par le réseau si possible, sinon en queue locale avec UX `OFFLINE-xxx` placeholder
- **Analytics avancés** — 5 endpoints `/analytics/*` (revenue-summary avec comparaison période précédente, sales-timeseries N jours, top-products par CA ou quantité, payment-methods-breakdown, hourly-distribution pour staffing), page frontend complète avec cartes KPI + 4 graphiques Recharts
- **Notifications WhatsApp/SMS** — service `NotificationService` via Twilio (mode preview si pas configuré pour les démos), normalisation auto des numéros marocains (+212), helper `build_credit_reminder_message` pour composer les relances en français, branché sur l'endpoint `POST /clients/{id}/credit/reminders` quand channel = whatsapp/sms
- **Détection anomalies caisse par IA** — endpoint `/ai/anomaly-detection`, Claude analyse les ventes du jour (remises excessives, horaires inhabituels, annulations en série, montants atypiques) et retourne `AnomalyAlert[]` typés (info/warning/critical) avec catégorie + description + IDs de ventes concernées, dialog UI dans la page Analytics
- **Déploiement Contabo prêt** — `docker-compose.prod.yml` complet (Caddy HTTPS auto + API + frontend + db + redis + sidecar backup), `Caddyfile` (reverse proxy + HSTS + compression + Permissions-Policy caméra), `backup.sh` (pg_dump compressé quotidien + rotation 14j), `deploy.sh` (install/up/down/logs/backup/restore), `.env.prod.example`, `DEPLOYMENT.md` complet avec recovery plan
- **Tests E2E** — 12 nouveaux tests : 5 analytics endpoints, normalisation téléphone + preview mode notif + message builder + reminder endpoint, anomaly detection auth + cas vide

### Jour 8 — Parité métier + UX double mode (vs Gebs Pharma)
**L'analyse des écrans Gebs en production nous a montré 5 manques métier à combler et l'opportunité de gagner massivement sur l'UX.**
- **Permissions atomiques** — module `core/permissions.py` avec hiérarchie de rôles (`owner` > `titulaire` > `adjoint` > `caissier`) et 20 permissions atomiques (sales:create, expenses:write, exchanges:read, sales:close_day...), helper `require_permission()` pour les endpoints
- **Clôture de journée (Z-report)** — endpoints `/operations/day-closings/*` (preview totaux temps réel, créer clôture avec cash compté + écart automatique, historique), bloque automatiquement la création de ventes après clôture (HTTP 409), figé en lecture seule pour la comptabilité
- **Ordonnancier réglementaire** — table `prescription_logs` avec numérotation séquentielle annuelle, alimentée automatiquement quand une vente a `has_prescription=True`, registre légal obligatoire au Maroc pour les médicaments listes I/II, endpoint `/operations/prescription-log` avec recherche par patient/prescripteur
- **Échanges confrères** — endpoints `/operations/exchanges/*`, gestion entrée/sortie produits avec pharmacies voisines (très courant au Maroc), calcul automatique des soldes par partenaire (`/exchanges/balances` : qui doit quoi à qui), workflow settle (régler)
- **Charges d'exploitation** — endpoints `/operations/expenses/*` avec 9 catégories (rent, utilities, salaries, supplies, taxes, insurance, maintenance, marketing, other), résumé par catégorie, méthodes de paiement, support charges récurrentes
- **Inventaires physiques** — sessions `/operations/inventory-sessions/*` avec workflow complet : start session → add lines (snapshot stock théorique vs compté, calcul écart valeur au PA) → complete avec `apply_adjustments=true` pour aligner automatiquement le stock physique
- **Mode Caissier (kiosk plein écran)** 🌟 — page `/cashier` sans sidebar, gros boutons tactiles, raccourcis clavier F1-F12 partout (F1 cherche, F2 scan, F3 OCR ordonnance, F4 client, F10 encaisser, Esc vider, F12 aide), auto-add si scan code-barres exact, dialog paiement cash simplifié avec calcul rendu automatique, ReceiptOverlay animée auto-close, badge réseau intégré, redirection automatique vers ce mode au login si `user.role === "caissier"`
- **Search global ⌘K (CommandPalette)** 🌟 — composant Linear/GitHub-style activé par Ctrl+K ou ⌘K dans tout l'app, recherche unifiée produits + clients + 12 entrées navigation, keyboard nav (↑↓ Enter Esc), TanStack queries actives à partir de 2 caractères
- **Glossaire métier (Term)** — composant `<Term code="ICE" />` avec popover, dictionnaire de 30+ termes (ICE, IF, RC, CNSS, INPE, AMO, PPV, PPH, DCI, BL, BC, BR, TVA HT/TTC, Z-report, Liste I/II...) — chaque abréviation explique elle-même au hover/clic
- **Tests E2E** — 13 nouveaux tests J8 : function `has_permission()`, preview/close/double-close day, vente bloquée après clôture (409), auto-log ordonnance dans ordonnancier avec numérotation séquentielle, échanges CRUD + balances + settle, charges create + summary, inventaire full flow avec apply_adjustments, isolation tenant

### Jour 8+ — Branchement front du backend + besoins terrain pharmacien
**Suite à un retour d'un pharmacien marocain en exercice, et à l'audit de l'écart back/front.**
- **Module Achats/Fournisseurs branché** — page à 6 onglets exposant les 19 endpoints existants : Fournisseurs, Commandes (BC), Bons de livraison (réception → stock auto), Factures, Paiements, Retours. (3 bugs backend corrigés au passage : eager-loading `.items` manquant, ordre des routes `/{id}` vs littérales)
- **Module Tiers Payants branché** — page à 4 onglets : Organismes (CNOPS/CNSS/mutuelles), Demandes, Bordereaux (génération + soumission), Paiements. (1 bug corrigé : `payment_date` rendu optionnel)
- **Prix au lot (PPV par lot)** 🌟 — besoin terrain critique : au Maroc le PPV est imprimé sur la boîte et change entre arrivages. Chaque `ProductLot` porte désormais son propre `sale_price_ttc`. À la vente, logique **FEFO** : on prend le lot qui périme le plus tôt et on applique SON prix. Le PPV se renseigne à la réception du BL (saisie manuelle ou hérité du catalogue fournisseur). Priorité de prix : explicite > PPV lot FEFO > prix référence produit.
- **Catalogue fournisseur** — champ PPV ajouté pour pré-remplir le prix des lots à la réception
- **Tests E2E** — 21 nouveaux tests : workflow fournisseurs complet (BC, BL→stock, écarts, paiements), workflow tiers payants (payeurs, bordereaux, soumission, paiement), prix au lot (FEFO applique le bon prix, override, fallback, réception avec PPV)

## Démarrage

```bash
cp .env.example .env
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed
```

API disponible sur http://localhost:8000/docs

**Login démo** : `demo@pharmaos.ma` / `demo1234`

Voir [QUICKSTART.md](./QUICKSTART.md) pour les détails et un Makefile (`make up`, `make migrate`, `make seed`...).

## Statut

### Backend
- **~70 fichiers Python** (~10 000 lignes app + tests)
- **33 tables PostgreSQL** (multi-tenant strict via `pharmacy_id`)
- **103 endpoints REST** documentés OpenAPI :
  - `/auth` (5) — register, login, refresh, me, pharmacy
  - `/products` (9) — CRUD, recherche, lots, alertes stock/péremption
  - `/clients` (13) — CRUD, crédits, échéancier, paiements, relances **WhatsApp/SMS**, aging
  - `/suppliers` (19) — CRUD, catalogue, BC, BL, factures, paiements, retours
  - `/third-party` (11) — payeurs, claims, bordereaux, paiements
  - `/sales` (5) — caisse, annulation, stats, **bloquée si journée clôturée**
  - `/ai` (5) — interactions, suggestions, PharmaBot, **OCR ordonnance**, **détection anomalies**
  - `/developer` (8) — API publique : clés API + webhooks + events + deliveries
  - `/analytics` (5) — KPIs CA, séries temporelles, top produits, paiements, distribution horaire
  - `/operations` (17) — **clôture journée**, **ordonnancier**, **échanges confrères**, **charges**, **inventaires**
- **Permissions atomiques** — 4 rôles × 20 permissions configurables
- **Worker async** — delivery webhooks avec retry exponentiel
- **Notifications** — Twilio SMS + WhatsApp (mode preview sans config)

### Frontend
- **React 18 + TypeScript + Vite + Tailwind + shadcn/ui**
- **17 pages** : Login, Register, Dashboard, **Caisse titulaire**, **Cashier (mode kiosk)**, Stock, Clients, Fournisseurs, Analytics, Developers, Ticket, Invoice, **Ordonnancier**, **Charges**, **Échanges confrères**, **Inventaire**, **Clôture journée**
- **Double mode UX** — caissiers redirigés automatiquement vers `/cashier` (kiosk plein écran avec raccourcis F1-F12), titulaires vers dashboard complet
- **Search global ⌘K** — CommandPalette unifiée (produits, clients, navigation)
- **Glossaire métier** — composant `<Term code="..." />` avec 30+ abréviations expliquées au hover
- **PWA installable** — manifest + service worker
- **Mode offline complet** — IndexedDB `idb` pour cache produits + queue ventes, sync auto au retour réseau, badge réseau dans topbar
- **Composants premium** — BarcodeScanner caméra, PrescriptionOCRDialog, AnomalyDetectionCard
- **Build production** validé (365 KB gzippé)

### Production-ready
- **Caddy HTTPS auto** — Let's Encrypt, HSTS, compression, headers sécurité
- **Backups nightly** — pg_dump compressé + rotation 14j
- **Script `deploy.sh`** — install/up/down/logs/backup/restore idempotent
- **`DEPLOYMENT.md`** — guide complet avec recovery plan

### Tests & CI
- **92 tests pytest** E2E ✅ tous verts en ~130s
- **CI GitHub Actions** : pytest backend + npm build frontend

## Architecture

Multi-tenant strict : chaque ligne de chaque table porte un `pharmacy_id`. Toutes les requêtes sont filtrées par le tenant courant via une dépendance FastAPI globale.

## Différenciation concurrentielle

| Feature | Gestofi | Sobrus | Gebs Pharma | PharmaOS |
|---|---|---|---|---|
| Cloud natif | ❌ | ✅ | ⚠️ Local | ✅ |
| API publique | ❌ | ❌ | ❌ | ✅ (OpenAPI) |
| Webhooks signés HMAC | ❌ | ❌ | ❌ | ✅ |
| iOS + Android (PWA) | ❌ | ✅ | ❌ | ✅ |
| Mode offline caisse | ❌ | ❌ | ❌ | ✅ |
| IA native (OCR + interactions) | ❌ | Basique | ❌ | ✅ Claude |
| Mode caissier simplifié | ❌ | ❌ | ⚠️ Tout pareil | ✅ Dédié |
| Raccourcis clavier F1-F12 | ❌ | ❌ | ✅ Partiel | ✅ Complet |
| Search global ⌘K | ❌ | ❌ | ❌ | ✅ |
| Clôture journée (Z-report) | ✅ | ✅ | ✅ | ✅ |
| Ordonnancier | ✅ | ✅ | ✅ | ✅ Auto-rempli |
| Échanges confrères | ⚠️ | ❌ | ✅ | ✅ + soldes auto |
| Charges d'exploitation | ✅ | ⚠️ | ✅ | ✅ |
| Inventaire physique | ✅ | ✅ | ✅ | ✅ |
| Tiers payant configurable | Partiel | Partiel | Partiel | ✅ 100% générique |
| Crédits clients + relances WhatsApp | ❌ | Partiel | ❌ | ✅ |
| Multi-fournisseurs par produit | ✅ | ✅ | ✅ | ✅ |
| Détection anomalies caisse | ❌ | ❌ | ❌ | ✅ IA |
| Self-serve onboarding | ❌ | ❌ | ❌ | ✅ |

