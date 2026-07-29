# System overview

## Service boundaries

- **portal-web** renders the user interface and stores access tokens only in memory.
- **portal-bff** is the browser-facing API and owns the HttpOnly refresh cookie.
- **identity-service** owns users, sessions, module memberships, roles, and permissions.
- **hqa-service** owns normalized marketplace listings and snapshots.
- **sync-service** owns synchronization jobs, credential metadata, retry state, and workers.
- **n8n** should call service APIs and must not write directly to domain databases.

## Data ownership

One PostgreSQL instance is used initially, with separate databases and database users. Services must not query another service database directly.

## Scale path

Docker Compose is the initial deployment target. Stateless APIs and workers can later move to Kubernetes without redesigning the domain boundaries.
