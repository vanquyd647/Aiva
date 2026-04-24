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
