# Déploiement PharmaOS sur Contabo VPS

## Prérequis

- **VPS Contabo** — VPS S (4 GB RAM, 200 GB SSD, ~5€/mois) suffit pour démarrer
- **Nom de domaine** — pointé vers l'IP du VPS (record A)
- **Ubuntu 22.04 ou 24.04**

## Installation initiale (depuis ton poste)

```bash
# 1. Envoyer le code sur le VPS
scp -r pharmaos/ root@<IP-VPS>:/opt/

# 2. SSH dans le VPS
ssh root@<IP-VPS>

# 3. Installer
cd /opt/pharmaos
./deploy.sh install

# 4. Configurer
nano .env
# → renseigner DOMAIN, SECRET_KEY (openssl rand -hex 32),
#   POSTGRES_PASSWORD, ANTHROPIC_API_KEY

# 5. Démarrer
./deploy.sh up
```

Le démarrage prend ~2 minutes :
- Build des images Docker
- Démarrage des 6 services (Caddy, API, frontend, db, redis, backup)
- Caddy obtient automatiquement un certificat HTTPS Let's Encrypt
- Application des migrations Alembic

## Premier accès

Une fois le DNS propagé et Caddy ayant son certificat (vérifiable via `./deploy.sh logs caddy`) :

```
https://votre-domaine.com         → SPA frontend
https://votre-domaine.com/docs    → Documentation OpenAPI (Swagger UI)
```

Créer la première pharmacie via la page `/register` ou en CLI :
```bash
./deploy.sh logs api | grep "🚀"
docker compose -f docker-compose.prod.yml exec api python -m app.scripts.seed
```

## Commandes utiles

```bash
./deploy.sh up          # déployer/mettre à jour
./deploy.sh down        # arrêter
./deploy.sh logs api    # suivre les logs API
./deploy.sh logs caddy  # logs Caddy (utile pour debug HTTPS)
./deploy.sh backup      # backup manuel
./deploy.sh restore backup.sql.gz   # restaurer
```

## Sauvegardes automatiques

Le service `backup` du compose tourne en arrière-plan :
- Dump PostgreSQL compressé chaque 24h dans le volume `postgres_backups`
- Rotation à 14 jours par défaut (modifiable via `BACKUP_RETENTION_DAYS`)
- Pour copier off-site :
  ```bash
  docker run --rm -v pharmaos_postgres_backups:/data alpine \
      tar czf - -C /data . | ssh user@backup-host "cat > pharmaos-$(date +%Y%m%d).tar.gz"
  ```

## Monitoring basique

L'endpoint `/health` est dispo et peut être pingué par UptimeRobot (gratuit) ou similaire :
- URL : `https://votre-domaine.com/health`
- Attendu : `{"status":"ok","service":"PharmaOS","env":"production"}`
- Intervalle : 5 min, alerte par email si > 2 échecs consécutifs

## Mise à jour

```bash
cd /opt/pharmaos
git pull   # ou rsync depuis ton poste
./deploy.sh up   # rebuild + restart, migrations appliquées auto
```

## Restauration après incident

Si le VPS est perdu :
1. Provisionner un nouveau VPS
2. `./deploy.sh install` + `./deploy.sh up`
3. Restaurer le backup le plus récent : `./deploy.sh restore <dernier-backup.sql.gz>`
4. Pointer le DNS sur le nouveau VPS

Le RTO (Recovery Time Objective) est ~30 minutes en assumant des backups off-site disponibles.

## Sécurité

- **HTTPS forcé** : Caddy redirige automatiquement HTTP → HTTPS
- **HSTS** : 1 an dans les headers
- **Firewall ufw** : seuls les ports 22, 80, 443 sont ouverts
- **Secrets** : ne JAMAIS committer `.env`, utiliser un gestionnaire de secrets en équipe
- **Mises à jour OS** : `apt update && apt upgrade -y` mensuel + redémarrage si kernel
- **Rotation clé** : changer `SECRET_KEY` invalidera tous les JWT + casse les secrets webhooks chiffrés (à faire seulement en cas de compromission, avec préavis utilisateurs)

## Échelle

Sur un VPS S (4 GB) :
- Supporte ~50-100 pharmacies actives simultanément
- Pour scaler : passer en VPS M (16 GB), ajouter `replicas: N` sur le service `api`, mettre un load balancer Caddy upstream

Pour le multi-instance, prévoir aussi :
- Postgres en RDS / managed (Scaleway DB, Hetzner Cloud DB)
- Redis en managed
- Stockage objet S3 pour les uploads (pas encore implémenté)
