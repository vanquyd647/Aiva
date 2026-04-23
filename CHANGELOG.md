# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Backend admin governance API (`/api/v1/admin/*`) with:
  - Audit trail listing with filters.
  - Session governance (list and revoke sessions).
  - Usage overview endpoint with warning/exceeded user counts.
- Backend user usage API (`/api/v1/usage/me`) for per-user quota insight.
- Session-aware JWT login flow (`sid` claim + persisted `user_sessions`) and logout revocation support.
- Governance persistence layer:
  - `audit_logs`
  - `user_sessions`
  - `usage_events`
- Quota/metering service with alert levels (`ok`/`warning`/`exceeded`) and chat quota enforcement.
- New authenticated web search API (`/api/v1/search/web`) for citation retrieval.
- New backend test coverage for governance APIs, session revocation, and quota enforcement.
- Backend file upload API (`/api/v1/files/upload`) with authenticated access, extension validation, size limits, and text preview extraction.
- Desktop attachment workflow in chat composer:
  - Pick/clear pending attachments.
  - Upload-to-backend flow when backend streaming mode is enabled.
  - Local preview extraction fallback for text-like files.
- Multimodal image support for chat turns:
  - Desktop app now serializes selected image attachments as inline base64 payloads for the active send turn.
  - Backend and local Gemini adapters now map inline image payloads to Gemini SDK image parts.
- New backend test coverage for file upload and inline image attachment forwarding in chat stream.

### Changed
- Admin desktop app UI upgraded from text-list style to table/dashboard workflow:
  - User table view with row selection.
  - New Governance tab (sessions + audit stream + revoke actions).
  - New Usage/Quota tab (summary cards, progress bars, top-user consumption view, alert states).
- User desktop app top bar now includes live usage/quota badge and progress indicator when backend mode is enabled.
- Chat streaming now records usage events and enforces quota window limits before generation.
- Admin-sensitive user operations now emit structured audit entries and admin action usage events.
- Chat send pipeline now supports attachment-only turns by composing a fallback user instruction.
- Runtime attachment payloads are sent to model requests without persisting binary content to local conversation history.
- Chat streaming now supports optional web grounding context and emits citations in SSE `done` payload.
- Desktop user app can enable web citations from settings and appends source references to backend-streamed answers.
- Clean-code pass across backend + desktop modules:
  - Fixed async exception-capture closures that could trigger undefined-name lint errors.
  - Normalized SQLAlchemy relationship typing with forward-reference safe annotations.
  - Removed unused imports and aligned formatting to Black conventions.
  - Quality gate is green (`ruff`, `black --check`, `pytest`, `compileall`).

## [0.2.0] - 2026-04-23

### Added
- Admin API extensions for operational management:
  - User statistics endpoint.
  - User profile update endpoint.
  - User password reset endpoint.
  - Guardrails to prevent self-downgrade and self-deactivation for admins.
- New backend test coverage for admin management flows.
- Shared desktop i18n module (`core/i18n.py`) with Vietnamese/English dictionaries.
- Windows desktop packaging script (`scripts/build_desktop.ps1`) for user and admin executables.
- Release workflow Windows job to build and attach desktop executables (`AIAssistUser.exe`, `AIAssistAdmin.exe`).
- Admin desktop UX upgrades:
  - Logout action and authentication-state handling.
  - CSV export for current user table page.
  - Pagination controls now reflect first/last page states.
  - Keyboard shortcut for quick refresh.
  - End-to-end localized UI strings through the shared translation layer.
- User desktop UX upgrades:
  - Conversation search in sidebar.
  - Export current conversation to markdown.
  - Clear current conversation with confirmation.
  - Keyboard shortcuts for new chat/export/search focus.
  - End-to-end localized UI strings and language setting persistence.

## [0.1.0] - 2026-04-23

### Added
- Process uplift package:
  - CI workflow for lint, format check, tests, compile smoke check.
  - CI test matrix across Linux and Windows runners.
  - Release workflow with migration check and compile validation.
  - Release metadata validator script (SemVer tag + changelog version section).
  - Developer quality tooling (ruff, black, pytest, pre-commit).
  - Governance docs (README, CONTRIBUTING, SECURITY, LICENSE).
  - CODEOWNERS, issue/PR templates, and branch protection automation script.
  - Backend test suite baseline.
  - Docker and docker-compose for backend + Redis local stack.
  - Alembic migration baseline and DB migration script.
  - Postgres docker-compose profile for production-like local runs.
  - Release checklist documentation for consistent publishing process.

### Changed
- Hardened backend runtime settings validation for production mode.
- Safer default CORS origins for local development.
- Production docs endpoints disabled when ENV=production.
- Refined .gitignore to avoid blanket JSON exclusion.
- Added production guardrails for AUTO_CREATE_DB_SCHEMA setting.
