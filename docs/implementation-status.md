# Implementation status

## Implemented and runnable

- Edge gateway and static SPA portal
- BFF API
- Identity service with HttpOnly refresh session
- 15-minute idle timeout and refresh token rotation
- Module RBAC with superadmin, admin, and user
- Superadmin user creation and module membership assignment
- HQA listing dashboard, filters, pagination, seller/shop, quantity, and snapshots
- HQS request dashboard and request creation
- Sync job API, idempotency, database-backed item payload, batch size 100, and Celery worker
- PostgreSQL databases per service
- RabbitMQ, Redis, and MinIO containers
- GitHub Actions CI, image publishing, SSH deployment, backup, health check, and rollback scripts

## Production integration points

The sync worker uses a deterministic demo adapter so the stack can be tested without marketplace credentials. Replace the demo payload builder with real eBay, Reverb, and Etsy clients. The marketplace account table and account selection foundation are included, but secrets must be supplied through Docker Secrets, Vault, or another secret manager.

Alembic migrations should be introduced before production data migrations. Local bootstrap currently uses SQLAlchemy `create_all` so a new environment can start immediately.

HTTPS certificates, domain names, API credentials, email/Telegram channels, and organization-specific HQS workflows are deployment configuration rather than embedded secrets.
