# PharmaOS — Quickstart

## Prérequis
- Docker + Docker Compose installés
- (Optionnel) Clé API Anthropic pour les fonctionnalités IA

## Démarrer en 3 commandes

```bash
# 1. Copier les variables d'environnement
cp .env.example .env
# (Éditez .env si nécessaire — au minimum, mettez votre ANTHROPIC_API_KEY si vous voulez tester l'IA)

# 2. Démarrer les services (db, redis, api)
make up
# ou : docker compose up -d

# 3. Initialiser la base + charger les données démo
make migrate
make seed
```

## Vérifier que ça marche

- **Frontend** : http://localhost:5173 (interface complète : caisse, stock, clients, dashboard)
- Health check API : http://localhost:8000/health
- Documentation API (Swagger) : http://localhost:8000/docs
- Documentation alternative (ReDoc) : http://localhost:8000/redoc

## Login démo

Après `make seed`, vous pouvez vous authentifier :
- **Email** : `demo@pharmaos.ma`
- **Mot de passe** : `demo1234`

Endpoint : `POST /api/v1/auth/login` (JSON : `{"email": "...", "password": "..."}`)
Récupérez le `access_token` et utilisez-le en header `Authorization: Bearer <token>`.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@pharmaos.ma","password":"demo1234"}'
```

## Commandes courantes (Makefile)

```bash
make help     # liste des cibles
make up       # démarrer
make down     # arrêter
make logs     # voir les logs de l'API
make migrate  # appliquer migrations
make seed     # données démo
make shell    # shell dans le conteneur API
make clean    # tout détruire (DESTRUCTIF — supprime aussi les volumes)
```

## Tester un workflow complet

1. **Login** → récupérer token
2. **Lister produits** : `GET /api/v1/products`
3. **Lister clients** : `GET /api/v1/clients`
4. **Créer une vente** : `POST /api/v1/sales` avec items + client + payment
5. **Voir l'aging des crédits** : `GET /api/v1/clients/credit/aging-report`
6. **Générer un bordereau tiers payant** : `POST /api/v1/third-party/bordereaux`

## Architecture rapide

```
pharmaos/
├── backend/                    # API FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── core/               # config + sécurité (JWT)
│   │   ├── db/                 # SQLAlchemy session + Base
│   │   ├── models/             # 24 tables ORM
│   │   ├── schemas/            # validation Pydantic
│   │   ├── services/           # logique métier
│   │   ├── api/v1/             # 70 endpoints REST
│   │   └── scripts/seed.py
│   ├── alembic/                # migrations
│   └── requirements.txt
├── frontend/                   # SPA React + Vite + TS
│   ├── src/
│   │   ├── components/         # UI shadcn + Layout
│   │   ├── pages/              # Login, Dashboard, Caisse, Stock, Clients
│   │   ├── stores/             # auth + panier (Zustand)
│   │   ├── lib/                # Axios client
│   │   └── types/              # types TS miroir des schémas
│   └── package.json
├── docker-compose.yml          # db + redis + api + frontend
├── Makefile
└── .env.example
```

## Développement frontend séparé

Si vous voulez itérer rapidement sur le frontend avec hot-reload :

```bash
# Terminal 1 : démarrer juste l'API
docker compose up -d db redis api

# Terminal 2 : Vite en dev
cd frontend
npm install
npm run dev
# → http://localhost:5173 (avec proxy automatique sur /api → :8000)
```

## Stack

- **FastAPI 0.115** + Python 3.12 (async)
- **PostgreSQL 16** (multi-tenant strict via `pharmacy_id`)
- **Redis** (cache/rate-limit futur)
- **JWT** (auth)
- **Anthropic Claude** (IA : interactions médicamenteuses, suggestions, PharmaBot)

## Spécificités Maroc

- Devise MAD, TVA 7% par défaut (médicaments)
- Champs légaux : ICE, IF, RC, CNSS, INPE
- Tiers payants 100% configurables (CNSS, CNOPS, RAMED, mutuelles…)
- Crédits clients avec relances multi-canaux

## Prochaines étapes (Jour 3+)

- Tests pytest (intégration + unitaires)
- Frontend (Next.js / React)
- Module facturation TVA conforme DGI
- Connecteur balances / lecteurs code-barres
- Module statistiques + dashboards
