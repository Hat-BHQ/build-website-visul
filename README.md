# HQ Platform V2

A production-oriented microservices starter for the HQA/HQS portal.

## Included

- Dependency-free JavaScript SPA portal (no npm runtime dependencies)
- FastAPI Backend-for-Frontend (BFF)
- Identity service with module-based RBAC
- Roles: `superadmin`, module `admin`, module `user`
- HttpOnly refresh cookie and 15-minute idle session timeout
- HQA listing service with marketplace fields and snapshots
- Sync service with job/chunk model and Celery worker
- PostgreSQL databases per service
- RabbitMQ, Redis, MinIO
- Nginx edge gateway
- Docker Compose development/production foundation
- GitHub Actions CI, image build, and production deploy templates

## Architecture

```text
Browser
  -> edge-gateway
      -> portal-web
      -> portal-bff
          -> identity-service
          -> hqa-service
          -> sync-service
                 -> RabbitMQ -> sync-worker -> hqa-service
          -> hqs-service
```

## Quick start

1. Copy the environment file:

```bash
cp .env.example .env
```

2. Change all passwords and secrets in `.env`.

3. Start the stack:

```bash
docker compose -f infra/compose/compose.yml up -d --build
```

4. Open:

```text
http://localhost:8080
```

Default bootstrap accounts (change immediately):

```text
root@example.com        / ChangeMe123!
hqa.admin@example.com   / Admin123!
hqa.user@example.com    / User123!
```

## Useful commands

```bash
make up
make down
make logs
make test
make health
```

## RBAC model

- `superadmin` is a system-level role and can access every module.
- `admin` and `user` are assigned per module through memberships.
- A person can be HQA admin and HQS user at the same time.
- Frontend guards only improve UX. Every backend endpoint enforces permissions.

## Production notes

- Replace bootstrap credentials.
- Use HTTPS and set `COOKIE_SECURE=true`.
- Store marketplace credentials in a secret manager.
- Do not expose PostgreSQL, RabbitMQ, Redis, or MinIO publicly.
- Run database migrations as a dedicated deployment step.
- Use immutable image tags based on commit SHA.
