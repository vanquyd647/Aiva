# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- (no entries yet)

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
