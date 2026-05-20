#!/bin/bash
# Déploiement PharmaOS sur VPS Contabo (Ubuntu 22.04+)
#
# Usage :
#   1. Provisionner un VPS Contabo (4 GB RAM minimum)
#   2. SSH en root, exécuter ce script
#   3. Personnaliser /opt/pharmaos/.env
#   4. ./deploy.sh up
#
# Le script est idempotent : on peut le relancer pour mettre à jour.

set -euo pipefail

REPO_DIR=${REPO_DIR:-/opt/pharmaos}
COMPOSE_FILE=docker-compose.prod.yml

cmd_install() {
    echo "==> Installation Docker (si nécessaire)"
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com | sh
        systemctl enable --now docker
    fi
    if ! docker compose version &> /dev/null; then
        echo "Docker Compose v2 plugin manquant"
        exit 1
    fi

    echo "==> Firewall : ouvrir 80 et 443 uniquement"
    if command -v ufw &> /dev/null; then
        ufw allow 22/tcp
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
    fi

    echo "==> Création $REPO_DIR"
    mkdir -p "$REPO_DIR"
    cd "$REPO_DIR"
    if [[ ! -f .env ]]; then
        cp .env.prod.example .env
        echo "⚠️  Fichier .env créé depuis .env.prod.example — ÉDITEZ-LE avant de lancer."
    fi
}

cmd_up() {
    cd "$REPO_DIR"
    echo "==> Build des images"
    docker compose -f "$COMPOSE_FILE" build
    echo "==> Démarrage des services"
    docker compose -f "$COMPOSE_FILE" up -d
    echo "==> Application des migrations"
    sleep 5
    docker compose -f "$COMPOSE_FILE" exec -T api alembic upgrade head
    echo "==> Statut"
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    echo "✅ PharmaOS déployé sur https://$(grep '^DOMAIN' .env | cut -d= -f2)"
}

cmd_down() {
    cd "$REPO_DIR"
    docker compose -f "$COMPOSE_FILE" down
}

cmd_logs() {
    cd "$REPO_DIR"
    docker compose -f "$COMPOSE_FILE" logs -f "${2:-}"
}

cmd_backup_now() {
    cd "$REPO_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    docker compose -f "$COMPOSE_FILE" exec -T db \
        pg_dump -U "$(grep POSTGRES_USER .env | cut -d= -f2)" \
        --no-owner --clean --if-exists \
        "$(grep POSTGRES_DB .env | cut -d= -f2)" \
        | gzip > "manual_backup_${TIMESTAMP}.sql.gz"
    echo "✅ Backup → manual_backup_${TIMESTAMP}.sql.gz"
}

cmd_restore() {
    if [[ $# -lt 2 ]]; then
        echo "Usage: $0 restore <backup.sql.gz>"
        exit 1
    fi
    cd "$REPO_DIR"
    echo "⚠️  Restauration depuis $2 (la DB actuelle sera écrasée)"
    read -p "Confirmer ? [yes/no] " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Annulé"
        exit 1
    fi
    gunzip -c "$2" | docker compose -f "$COMPOSE_FILE" exec -T db \
        psql -U "$(grep POSTGRES_USER .env | cut -d= -f2)" \
        "$(grep POSTGRES_DB .env | cut -d= -f2)"
    echo "✅ Restauration terminée"
}

case "${1:-help}" in
    install) cmd_install ;;
    up) cmd_up ;;
    down) cmd_down ;;
    logs) cmd_logs "$@" ;;
    backup) cmd_backup_now ;;
    restore) cmd_restore "$@" ;;
    *)
        cat << EOF
PharmaOS — Script de déploiement Contabo

Usage : $0 <commande>

Commandes :
  install     Installer Docker, firewall, créer /opt/pharmaos
  up          Build + démarrer + migrations (idempotent)
  down        Arrêter les services
  logs [svc]  Suivre les logs (optionnellement d'un service spécifique)
  backup      Backup manuel immédiat
  restore <f> Restaurer depuis un backup
EOF
        ;;
esac
