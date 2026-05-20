"""
Rôles et permissions PharmaOS.

Hiérarchie :
- **owner** : créateur du compte (premier titulaire), accès total + facturation
- **titulaire** : pharmacien titulaire avec accès complet métier (sans facturation SaaS)
- **adjoint** : pharmacien adjoint, accès complet métier sauf admin (pas de gestion users)
- **caissier** : vendeur/préparateur, accès limité (caisse + recherche stock + clients)

Le rôle détermine :
1. Les endpoints API autorisés
2. La vue par défaut (mode caissier vs mode titulaire)
3. Les modules visibles dans le menu

Note : tout le monde dans la même pharmacie partage les mêmes données — c'est juste l'accès qui change.
"""

# Liste des rôles dans l'ordre hiérarchique (du plus puissant au plus restreint)
ROLES = ["owner", "titulaire", "adjoint", "caissier"]

# Définition des permissions atomiques
PERMISSIONS = {
    # Caisse
    "sales:create": ["owner", "titulaire", "adjoint", "caissier"],
    "sales:cancel": ["owner", "titulaire", "adjoint"],
    "sales:close_day": ["owner", "titulaire"],

    # Stock
    "stock:read": ["owner", "titulaire", "adjoint", "caissier"],
    "stock:write": ["owner", "titulaire", "adjoint"],
    "stock:inventory": ["owner", "titulaire", "adjoint"],

    # Clients
    "clients:read": ["owner", "titulaire", "adjoint", "caissier"],
    "clients:write": ["owner", "titulaire", "adjoint", "caissier"],
    "clients:credit": ["owner", "titulaire", "adjoint"],

    # Fournisseurs
    "suppliers:read": ["owner", "titulaire", "adjoint"],
    "suppliers:write": ["owner", "titulaire", "adjoint"],

    # Charges et finances
    "expenses:read": ["owner", "titulaire"],
    "expenses:write": ["owner", "titulaire"],

    # Échanges confrères
    "exchanges:read": ["owner", "titulaire", "adjoint"],
    "exchanges:write": ["owner", "titulaire", "adjoint"],

    # Analytics
    "analytics:read": ["owner", "titulaire"],

    # Admin
    "users:manage": ["owner", "titulaire"],
    "api_keys:manage": ["owner", "titulaire"],
    "webhooks:manage": ["owner", "titulaire"],
    "settings:write": ["owner"],
}


def has_permission(role: str, permission: str) -> bool:
    """Vérifie si un rôle a une permission."""
    allowed = PERMISSIONS.get(permission)
    if not allowed:
        return False
    return role in allowed


def default_view_for_role(role: str) -> str:
    """Vue par défaut au login selon le rôle."""
    if role == "caissier":
        return "cashier"  # Mode kiosk
    return "manager"  # Mode complet
