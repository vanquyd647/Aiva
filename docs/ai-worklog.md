# AI Worklog

Track every AI-assisted code change here. This file is mandatory for code-change PRs.

## 2026-04-24

### Scope
- Added secure backend-only Gemini key rotation architecture.
- Added encrypted provider secret storage, admin rotation API, and runtime client refresh.
- Added admin desktop API Keys tab for test/rotate/status workflows.
- Updated desktop default config to backend streaming mode for backend-managed key posture.
- Added CI/local guard requiring CHANGELOG + ai-worklog updates for code changes.
- Added technical guides for assistant architecture and provider comparison.
- Refactored Gemini key business logic from route to dedicated backend service layer (`admin_gemini_keys`).

### Files Changed (high level)
- Backend: config, models, services, admin routes, schemas, alembic migration, tests.
- Desktop: admin_app.py, core/i18n.py.
- Process: CI workflow, quality gate, release checklist, contributing guide.
- Docs: AI assistant build guide, provider comparison guide.

### Verification
- Python compile checks passed for backend and desktop modules.
- New and modified backend tests added for key dry-run, rotation, and key cache refresh behavior.
- Security posture validated by design: no plaintext key storage, masked fingerprint only, audit trails for key operations.
- Full quality gate passed after refactor: ruff, black, doc guard, pytest (32 passed), compileall.

### Follow-up
- Execute full test suite after migration in clean environment.
- Add optional dual-approval flow for production key rotation if required by policy.

### Gemma 4 Capability Completion
- Extended chat request contract to expose advanced Gemma controls:
	- thinking controls (`enable_thinking`, `include_thoughts`, `thinking_budget_tokens`, `thinking_level`),
	- function-calling controls (`tools`, function mode, allow-list, streaming argument flag),
	- structured output controls (`response_mime_type`, JSON schema options),
	- additional generation knobs (`candidate_count`, `stop_sequences`, `seed`, penalties, safety settings, media resolution).
- Refactored backend stream service to map advanced request fields into `google-genai` config safely, including enum normalization and graceful handling of invalid optional settings.
- Added server-side extraction of streamed function/tool calls and surfaced them through SSE (`tool_call` events + `done.tool_calls`).
- Expanded multimodal attachment pipeline end-to-end:
	- backend chat service now accepts image/audio/video/PDF attachment parts,
	- desktop app now serializes inline payloads for supported media instead of image-only,
	- file picker and backend upload extension allow-list now include common audio/video formats.
- Added focused automated coverage:
	- route tests for advanced config forwarding and tool-call events,
	- route test for attachment-only user turns,
	- service tests for multimodal part mapping and advanced SDK config mapping.

### Verification (Gemma 4 completion scope)
- Targeted test suite passed:
	- `backend/tests/test_chat_stream.py`
	- `backend/tests/test_chat_stream_service.py`

### Cleanup Pass
- Removed legacy standalone CLI prototype `assistant.py` (Phase-1 path) to keep a single supported desktop runtime flow.
- Removed obsolete research draft `research_gemma4_ai_assistant.md` to reduce duplicate/outdated documentation.
- Removed empty placeholder module file `ui/__init__.py` after reference audit confirmed no imports/usages.
- Removed unreferenced roadmap document `docs/premium-product-roadmap.md` after repository-wide reference audit.
- Updated automation pipelines to match cleanup:
	- `.github/workflows/ci.yml`
	- `.github/workflows/release.yml`
	- `scripts/quality_gate.ps1`

### Verification (cleanup scope)
- Full quality-gate rerun completed after file removal:
	- `ruff` passed
	- `black --check` passed
	- doc guard passed
	- `pytest` passed (`36 passed`)
	- `python -m compileall` smoke passed
- Follow-up rerun after removing unused `ui/__init__.py` also passed with the same gate results.
- Final rerun after repository-wide stale-doc audit and cleanup also passed with identical results.

### Final Integration Pass
- Consolidated remaining backend/desktop/env-template/test changes into a single full-repo commit scope.

### Desktop Stability Fix
- Resolved runtime crash when loading conversations caused by `CTkTextbox.cget("state")` not being supported in current CustomTkinter.
- Updated chat input state handling to use an internal `_input_enabled` flag for safe enable/disable checks.

### User UX Remediation (Gemma4 + Auth)
- Modernized `SettingsDialog` from a linear form into tabbed settings (`General`, `Gemma 4`, `Backend/Auth`) for better discoverability.
- Exposed full Gemma4 advanced runtime controls in user settings:
	- generation knobs (`top_p`, `top_k`, `max_output_tokens`, `candidate_count`, stop sequences, seed, penalties),
	- thinking controls,
	- function-calling controls,
	- structured output schema fields,
	- tools/safety JSON controls,
	- media resolution.
- Added backend user login flow directly in user settings to fetch and store access token without using admin app.
- Added auth-aware UX guardrails:
	- preflight check before backend streaming when token is missing,
	- clearer authentication-failure message,
	- prompt to open settings for re-login,
	- auto-disable backend streaming at save time when token is empty.

### Gemini API Compatibility Fix
- Added SDK/API capability guard for `stream_function_call_arguments` in both backend and local Gemini adapters.
- Runtime now omits this field when unsupported to avoid request failure: `stream_function_call_arguments parameter is not supported in Gemini API`.

### User App Backend-Only Lock
- Hard-locked user desktop runtime to backend-only mode:
	- removed runtime fallback path that called local `core.gemini` directly,
	- forced `use_backend_stream=True` at startup and on settings save,
	- disabled backend-stream toggle in settings UI and added explicit backend-only notice,
	- removed local attachment routing branch so uploads always go through backend APIs.

### Gemini Key Validation Model Switch
- Switched backend default key-validation model from `gemini-2.0-flash-lite` to `gemma-4-31b-it`.
- Updated both root and backend `.env.example` templates to keep runtime defaults aligned with backend config.

### Admin Readability Color Fix
- Increased visual contrast for admin tables/log panes to resolve unreadable text reports:
	- tuned `Admin.Treeview` colors (row text, heading colors, selected-row foreground/background),
	- set explicit high-contrast colors for governance audit textbox and usage top-users textbox.

### Backend Monitor + Gemma Runtime Visibility
- Added backend monitor endpoint `GET /api/v1/admin/backend-monitor` to expose runtime operations snapshot:
	- DB/cache status,
	- active/revoked sessions,
	- audit/usage event activity (24h),
	- Gemini key source + validation model + quota threshold.
- Integrated new Backend Monitor tab into `admin_app.py` and wired it into login/refresh/governance refresh flows.
- Added backend test coverage for the monitor endpoint in `backend/tests/test_admin_governance.py`.
- User app now appends Gemma function-calling/tool-call details (tool name and args) into final backend response rendering.

### User Quick Controls (Gemini-Web Style)
- Added a persistent quick-controls bar on the user chat screen so common runtime options can be changed immediately without opening Settings.
- Wired quick controls directly to runtime config persistence (`config.json`) and backend payload settings:
	- model selector,
	- temperature slider with debounced save,
	- thinking toggle,
	- web citations toggle,
	- function-calling mode selector.
- Added new user i18n keys (vi/en) for quick-control labels and function-mode choices.
- Extended quick controls with phase-2 interaction patterns:
	- style presets (`Balanced`, `Creative`, `Precise`) that apply coordinated `temperature/top_p/top_k` bundles,
	- one-tap JSON response mode toggle (`response_mime_type=application/json`),
	- collapsible secondary controls row to reduce visual noise and keep chat focus.
