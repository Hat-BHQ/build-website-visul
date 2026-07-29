# Validation report

Validated in the build environment on 2026-07-29.

## Passed

- Python syntax compilation for all BFF and service packages
- JavaScript syntax and portal build command
- JSON parsing
- YAML parsing for Compose and GitHub Actions files
- POSIX shell syntax for deployment and database scripts
- Identity unit tests
- HQA unit tests
- HQS unit tests
- Sync chunking unit tests
- Identity integration: login and refresh token rotation
- Identity integration: create user and assign module membership
- HQA integration: dashboard, bulk upsert, listing query
- HQS integration: create request and dashboard count

## Environment limitation

Docker is not installed in the artifact build environment, so container image builds and `docker compose config/up` could not be executed here. The Compose YAML was parsed successfully and should be validated again on the target Docker host.

The sync worker's real marketplace connectors require eBay, Reverb, and Etsy credentials. The included worker uses a deterministic demo adapter until those credentials and client implementations are supplied.
