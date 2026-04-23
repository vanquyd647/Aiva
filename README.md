# AI Assist

Desktop AI assistant with a dedicated backend service for authentication, user management, and operational controls.

## Architecture

- Desktop user app: app.py
- Desktop admin app: admin_app.py
- Backend API: backend/app
- Data: SQLite by default, Postgres-ready by configuration
- Cache: Redis with in-memory fallback

## Backend Capability Highlights

- Auth and session governance
	- JWT login with session ID (`sid`) claim.
	- Persistent `user_sessions` tracking and logout/session revocation.

- Conversation and chat runtime
	- Server-side conversations and messages.
	- SSE chat streaming endpoint: `/api/v1/chat/stream`.

- Admin governance and usage insight
	- Audit trail API: `/api/v1/admin/audit`.
	- Session governance APIs: `/api/v1/admin/sessions` and revoke endpoints.
	- Usage overview API: `/api/v1/admin/usage`.
	- Per-user usage API: `/api/v1/usage/me`.

- Search and citation grounding
	- Authenticated web search endpoint: `/api/v1/search/web`.
	- Optional citation enrichment in chat streaming done payload.

- Metering and quota controls
	- Usage events for chat messages/tokens, uploads, and admin actions.
	- Alert levels: `ok`, `warning`, `exceeded`.
	- Quota enforcement at chat request time.

## Quick Start

1. Create and activate Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Configure environment variables:

```bash
copy .env.example .env
```

4. Run backend API:

```bash
python -m uvicorn app.main:app --app-dir backend --reload --port 8080
```

5. Apply database migrations:

```powershell
./scripts/db_migrate.ps1
```

6. Run desktop apps:

```bash
python app.py
python admin_app.py
```

## Build Windows Executables

Use PyInstaller to generate standalone executables for both desktop apps:

```powershell
./scripts/build_desktop.ps1
```

If PyInstaller is already installed in your environment (for example in CI), run:

```powershell
./scripts/build_desktop.ps1 -SkipInstallerInstall
```

Build outputs:

- `dist/desktop/AIAssistUser.exe`
- `dist/desktop/AIAssistAdmin.exe`

If Windows Smart App Control blocks unsigned `.exe` binaries, run source launchers instead (Smart App Control has no per-app allowlist):

- `run-user-app.cmd`
- `run-admin-app.cmd`
- `run-user-app.vbs` (windowless launcher)
- `run-admin-app.vbs` (windowless launcher)

## Desktop UX Highlights

- User app (`app.py`)
	- Sidebar conversation search.
	- Retry, regenerate, edit, and branch conversation actions.
	- Draft persistence while typing.
	- File and image attachments (local and backend-stream mode).
	- Backend branch sync support for server-side conversation branching.
	- Export current conversation to markdown.
	- Clear current conversation with confirmation.
	- Bilingual UI support (`vi`/`en`) with language setting persistence.
	- Optional backend SSE streaming mode (configure backend URL and access token in settings).
	- Optional web citation toggle + source count in settings.
	- Usage/quota badge and progress bar in top bar when backend mode is enabled.
	- Keyboard shortcuts: `Ctrl+N` (new conversation), `Ctrl+E` (export), `Ctrl+K` (focus search), `Ctrl+R` (retry), `Ctrl+O` (attach file).

- Admin app (`admin_app.py`)
	- Table-based user management UI (modernized from textbox list).
	- Live user statistics cards (total, active, inactive, admins).
	- Full user lifecycle controls: create, update profile, reset password, activate/deactivate, delete.
	- Governance tab for audit trail viewing and session revocation.
	- Usage/Quota tab with usage summary, quota progress bars, and top-user consumption list.
	- Alert feedback when warning/exceeded usage thresholds are detected.
	- Session controls: relogin and logout.
	- CSV export of current user page.
	- Bilingual UI support (`vi`/`en`) shared with desktop config.
	- Keyboard shortcut: `Ctrl+R` to refresh dashboard.

## Postgres Deployment Profile

Use this for local production-like stack (Postgres + Redis + backend):

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

## Quality Gate

Run this before opening a pull request:

```powershell
./scripts/quality_gate.ps1
```

If your Windows environment blocks native lint binaries by security policy, run:

```powershell
./scripts/quality_gate.ps1 -SkipStyleChecks
```

This runs:

- Ruff lint
- Black format check
- Pytest for backend tests
- Python compile smoke check

## CI

GitHub Actions pipeline is defined in .github/workflows/ci.yml and runs lint, format checks, tests, and compile checks on every push and pull request.

## Branch Protection

Baseline policy is documented at docs/branch-protection.md.

You can apply branch protection with:

```bash
python scripts/apply_branch_protection.py --owner <github-owner> --repo <repo-name> --branch main
python scripts/apply_branch_protection.py --owner <github-owner> --repo <repo-name> --branch develop
```

## Release Process

Tag-based release is automated by .github/workflows/release.yml.
The workflow validates tag format and CHANGELOG version section, then publishes source archive and Windows desktop executables.

Release checklist: docs/release-checklist.md

Example:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Security Notes

- Never commit .env to version control.
- Rotate GEMINI_API_KEY if it was ever exposed.
- Use strong SECRET_KEY and INITIAL_ADMIN_PASSWORD values in all non-local environments.
- Use Postgres and Redis in production.

## Process Artifacts

- CONTRIBUTING.md
- SECURITY.md
- CHANGELOG.md
- LICENSE
- .pre-commit-config.yaml
- pyproject.toml

