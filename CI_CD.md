# CI/CD

GitHub Actions entrypoint: `.github/workflows/ci.yml`.

Pull requests and pushes to `main` run independent jobs for static/security checks, pytest, PostgreSQL migration/isolation tests, and the production Docker build. Jobs are intentionally independent so failures identify the affected layer.

Mypy is currently advisory while legacy modules are incrementally typed. Security scanners, Ruff fatal Python errors, dependency audit, pytest, PostgreSQL tests and Docker build are blocking.

## Deployment boundary

CI builds and validates artifacts but does **not** deploy production and does not run migrations against production. Before deploying a release:

1. back up PostgreSQL;
2. review pending Alembic revisions;
3. run `alembic upgrade head` using deployment credentials;
4. start the updated application/worker containers;
5. perform manual smoke tests for authentication, Cartridge, Repair, Location and WhatsApp delivery.

Production secrets must remain outside GitHub and the repository. CI tests use generated/test-only configuration and must never require real LDAP, WhatsApp or network-device credentials.
