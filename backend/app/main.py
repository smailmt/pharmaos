"""Point d'entrée FastAPI."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import auth, products, clients, suppliers, third_party, sales, ai, developer, analytics, operations


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.APP_NAME} démarré en mode {settings.APP_ENV}")
    yield
    print(f"⏹  {settings.APP_NAME} arrêté")


tags_metadata = [
    {"name": "auth", "description": "Authentification, inscription, gestion utilisateurs."},
    {"name": "products", "description": "Catalogue produits, lots, alertes stock & péremption."},
    {"name": "sales", "description": "Caisse, ventes, annulations, statistiques."},
    {"name": "clients", "description": "Clients, crédits, échéancier, paiements, balance âgée."},
    {"name": "suppliers", "description": "Fournisseurs, commandes, bons de livraison, factures."},
    {"name": "third-party", "description": "Tiers payants (CNSS, CNOPS, mutuelles), bordereaux."},
    {"name": "ai", "description": "Endpoints IA Claude (interactions, PharmaBot, suggestions)."},
    {
        "name": "developer",
        "description": (
            "**API publique** — Gérez vos clés API et webhooks. "
            "Authentification possible via JWT (header `Authorization: Bearer ...`) "
            "ou clé API (header `X-API-Key: pk_live_...`). "
            "Aucun concurrent au Maroc ne propose ça : c'est notre moat."
        ),
    },
    {"name": "analytics", "description": "KPIs avancés : CA, séries temporelles, top produits, répartition paiements."},
    {"name": "operations", "description": "Modules opérationnels : clôture journée, ordonnancier, échanges confrères, charges, inventaires."},
]

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "API PharmaOS — SaaS de gestion de pharmacie (Maroc).\n\n"
        "## Authentification\n\n"
        "Deux méthodes :\n"
        "- **JWT** (front interne) : `Authorization: Bearer <token>` obtenu via `/auth/login`\n"
        "- **Clé API** (intégrations) : `X-API-Key: pk_live_xxxxxxxx` créée via `/developer/api-keys`\n\n"
        "## Webhooks\n\n"
        "Souscrivez à des événements (`sale.created`, `product.low_stock`...) via `/developer/webhooks`. "
        "Les payloads sont signés HMAC-SHA256 dans l'en-tête `X-PharmaOS-Signature`."
    ),
    version="0.7.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
    contact={
        "name": "Support PharmaOS",
        "email": "support@pharmaos.ma",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "service": settings.APP_NAME, "env": settings.APP_ENV}


@app.get("/", tags=["meta"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "0.7.0",
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }


# Routers v1
prefix = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=prefix)
app.include_router(products.router, prefix=prefix)
app.include_router(clients.router, prefix=prefix)
app.include_router(suppliers.router, prefix=prefix)
app.include_router(third_party.router, prefix=prefix)
app.include_router(sales.router, prefix=prefix)
app.include_router(ai.router, prefix=prefix)
app.include_router(developer.router, prefix=prefix)
app.include_router(analytics.router, prefix=prefix)
app.include_router(operations.router, prefix=prefix)
