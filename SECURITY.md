# Security Policy

## Supported Scope

This policy applies to the backend API, desktop clients, and project release artifacts.

## Reporting a Vulnerability

1. Do not open public issues for active security vulnerabilities.
2. Report privately to the project maintainers.
3. Include reproduction steps, impact assessment, and suggested mitigation.

## Secure Configuration Requirements

- SECRET_KEY must be strong and unique per environment.
- INITIAL_ADMIN_PASSWORD must be rotated immediately in production.
- GEMINI_API_KEY must never be committed.
- CORS origins must be explicitly listed in production.
- Use Postgres and Redis for production deployments.

## Incident Response Baseline

1. Rotate impacted secrets.
2. Revoke issued tokens if auth scope is affected.
3. Patch and deploy hotfix.
4. Record root cause and mitigation in postmortem.
