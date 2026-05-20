#!/bin/sh
# Sauvegarde quotidienne PostgreSQL avec rotation
#
# - Dump compressé .sql.gz dans /backups/
# - Retention par défaut : 14 jours
# - Exécution : toutes les 24h (sleep loop simple)

set -eu

BACKUP_DIR=/backups
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}

mkdir -p "$BACKUP_DIR"

while true; do
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/pharmaos_${TIMESTAMP}.sql.gz"

    echo "[$(date)] Backup → $BACKUP_FILE"
    if pg_dump --no-owner --clean --if-exists | gzip > "$BACKUP_FILE"; then
        SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        echo "[$(date)] ✅ Backup OK ($SIZE)"
    else
        echo "[$(date)] ❌ Backup FAILED"
        rm -f "$BACKUP_FILE"
    fi

    # Rotation : supprimer les > RETENTION_DAYS
    find "$BACKUP_DIR" -name "pharmaos_*.sql.gz" -mtime "+$RETENTION_DAYS" -delete

    # Attendre 24h
    sleep 86400
done
