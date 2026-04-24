# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Gemma 4 advanced generation controls across backend + desktop runtime:
  - Thinking mode controls (`<|think|>` prompt tag, thinking level, thinking budget, optional thought return).
  - Native function-calling contract (tool declarations, function-calling mode, allow-list, streaming tool-call events).
  - Structured output controls (`response_mime_type`, `response_schema`, `response_json_schema`).
  - Extended multimodal request support for audio/video/PDF inputs (base64 and URI attachment forms).
- Chat SSE stream now emits `tool_call` events and includes aggregated `tool_calls` in final `done` payload.
- New chat-stream service unit tests for advanced config mapping, multimodal attachment conversion, and tool-call extraction.
- Backend secure Gemini key management:
  - New encrypted `provider_secrets` storage and migration.
  - Admin API for key status and key rotation (`/api/v1/admin/gemini-key`).
  - Dry-run key validation mode before persistence.
  - Runtime Gemini client refresh after rotation without backend restart.
- Admin desktop API Keys tab:
  - View masked key fingerprint/source/version.
  - Test key flow and rotate key flow with confirmation.
- New backend tests for key dry-run/rotation and chat client credential refresh.
- New process guard script `scripts/validate_change_docs.py` to require:
  - `CHANGELOG.md` update for code changes.
  - `docs/ai-worklog.md` update for code changes.
- New documentation package:
  - `docs/ai-assistant-build-guide.md`
  - `docs/provider-comparison-gemini-chatgpt.md`
  - `docs/ai-worklog.md`
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
- Removed obsolete Phase-1 standalone CLI entrypoint (`assistant.py`) to avoid duplicated runtime paths.
- Removed legacy research draft (`research_gemma4_ai_assistant.md`) after consolidating maintained docs under `docs/`.
- CI/release/local quality-gate scripts were updated to stop lint/compile checks for removed legacy files.
- Desktop attachment runtime serialization upgraded from image-only to multimodal inline payloads (image/audio/video/PDF).
- File upload allow-list extended to support common audio/video formats for Gemma multimodal workflows.
- Removed empty placeholder package file (`ui/__init__.py`) because it has no imports or runtime references.
- Removed stale planning document (`docs/premium-product-roadmap.md`) after audit confirmed it is not referenced by runtime, CI, or core docs.
- Chat Gemini client now resolves credentials from encrypted backend storage first, with optional env fallback.
- Admin Gemini key route logic was refactored into dedicated application service (`admin_gemini_keys`) to keep API routes thin.
- Desktop default config now enables backend streaming mode (`use_backend_stream=true`) for backend-managed key flow.
- CI and local quality gate now enforce change-doc guard (`CHANGELOG.md` + `docs/ai-worklog.md`) when code changes are detected.
- CONTRIBUTING and release checklist updated with mandatory AI worklog process.
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
- Fixed desktop conversation-switch crash on Python 3.14 + CustomTkinter by replacing unsupported `CTkTextbox.cget("state")` checks with internal input-state tracking.
- User settings dialog was modernized to tabbed sections and now exposes full Gemma 4 advanced controls (thinking, function-calling, schemas, tools, safety, and media resolution).
- User settings now support backend login to fetch access token directly, with clearer auth-failure prompts and automatic backend-stream disable when token is missing.
- Fixed Gemini request compatibility by sending `stream_function_call_arguments` only when the installed SDK/API supports the field.
- User desktop runtime is now hard-locked to backend-only mode (local Gemini route removed from send/attachment/branching flows and backend-stream setting is forced on).
- Admin Gemini key test/rotate validation default now targets `gemma-4-31b-it` (config + env examples) instead of `gemini-2.0-flash-lite`.
- Improved admin dashboard readability by increasing table/log text contrast (users/sessions Treeview + governance/usage text areas), including selected-row text color.
- Added admin backend runtime monitor (`/api/v1/admin/backend-monitor`) and integrated it into Admin app with live snapshot fields (DB/cache/session/audit/usage/Gemini key source/model).
- User app now surfaces Gemma tool/function-calling output in chat responses (tool name + args), not only in settings.
- Clean-code pass across backend + desktop modules:
  - Fixed async exception-capture closures that could trigger undefined-name lint errors.
  - Normalized SQLAlchemy relationship typing with forward-reference safe annotations.
  - Removed unused imports and aligned formatting to Black conventions.
  - Quality gate is green (`ruff`, `black --check`, `pytest`, `compileall`).
- Final integration pass aligned env templates, route/service wiring, and tests into one consolidated commit-ready state.

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
