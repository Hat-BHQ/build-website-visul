# Production deployment

1. Configure GitHub environment secrets.
2. Put the production `.env` in `/opt/hq-platform/.env`.
3. Set `COOKIE_SECURE=true` behind HTTPS.
4. Build and push immutable images through `build-images.yml`.
5. Deploy a SHA image tag with `deploy-production.yml`.
6. Run health checks and verify login, session refresh, listing read, and sync job creation.
7. Roll back application images with `scripts/deployment/rollback.sh` when needed.

Database migrations should be added with Alembic before the first production data migration. The starter currently creates tables on service startup for local bootstrap convenience.
