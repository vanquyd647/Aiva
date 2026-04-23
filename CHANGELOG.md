# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- TBD

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
