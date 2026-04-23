# AI Assist Backend

Secure API service for authentication, user management, and operations.

## Features

- JWT authentication with role-based access control (admin/user)
- Password hashing with bcrypt
- User CRUD for admin panel
- Redis cache with in-memory fallback
- Health probes for deployment orchestration
- Security headers and login rate limiting

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Configure environment variables:

```bash
copy backend/.env.example .env
```

4. Run API server:

```bash
uvicorn app.main:app --app-dir backend --reload --port 8080
```

### Database Migrations (Alembic)

From repository root:

```powershell
./scripts/db_migrate.ps1
```

Equivalent command:

```bash
python -m alembic -c backend/alembic.ini upgrade head
```

5. Open docs:

- Swagger: http://127.0.0.1:8080/docs
- Health live: http://127.0.0.1:8080/api/v1/health/live
- Health ready: http://127.0.0.1:8080/api/v1/health/ready

## Run Tests

From repository root:

```bash
python -m pytest backend/tests
```

## Run Local Quality Gate

From repository root:

```powershell
./scripts/quality_gate.ps1
```

If your Windows environment blocks native lint binaries by security policy, run:

```powershell
./scripts/quality_gate.ps1 -SkipStyleChecks
```

## Docker Compose (Backend + Redis)

From repository root:

```bash
docker compose up --build
```

Backend will run at http://127.0.0.1:8080.

### Docker Compose with Postgres

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

This starts PostgreSQL + Redis + backend with migration-first posture (`AUTO_CREATE_DB_SCHEMA=false`).

## Default Admin

On first startup, backend seeds an admin user from env vars:

- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`

Change these values before production deployment.
