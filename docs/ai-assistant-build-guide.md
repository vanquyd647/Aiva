# AI Assistant Build Guide (Gemini + ChatGPT Style)

This guide standardizes how to build, deploy, and operate AI assistant applications in this repository using clean architecture.

## 1) Reference Architecture

- Presentation layer:
  - Desktop UI and API adapters.
  - No provider secrets in clients.
- Application layer:
  - Use-case orchestration (chat stream, tool calls, quota checks, policy checks).
- Domain layer:
  - Conversation, message, governance, and usage rules.
- Infrastructure layer:
  - LLM provider clients, DB, cache, search connectors, and file storage.

Dependency rule: outer layers depend inward. Domain has zero dependencies on UI/provider SDKs.

## 2) Provider and Secret Management

- Keep provider API keys server-side only.
- Encrypt provider secrets at rest.
- Rotate keys via audited admin workflows.
- Never log plaintext keys or return them in API responses.
- Use masked fingerprints for troubleshooting.

## 3) Model Invocation Loop

1. Receive user message and attachments.
2. Apply auth, quota, and governance checks.
3. Build model input contract (messages + optional search context).
4. Stream response tokens to UI.
5. Persist final assistant message and usage metrics.
6. Emit audit/usage events for privileged operations.

## 4) Tool Calling and Structured Output

- Use explicit tool contracts and strongly typed schemas.
- Validate tool inputs/outputs before execution.
- Enforce maximum recursion/iteration caps for tool loops.
- Return structured JSON for machine-consumed operations.
- Keep user-visible text generation separated from control data.

## 5) Safety and Abuse Controls

- Login and privileged endpoints must be rate-limited.
- Add per-user quota windows (messages/tokens).
- Sanitize logs and audit payloads to redact secrets and tokens.
- Require admin role for governance and key-rotation actions.
- Add incident path to revoke/disable provider keys quickly.

## 6) Streaming UX Guidelines

- Emit stream metadata event first (model, conversation_id, request ids).
- Emit chunk events as soon as available.
- Emit done event with citations and final ids.
- Emit error event with safe messages (no stack traces/secrets).

## 7) Observability

- Track:
  - Request count, latency, token usage, cache mode, quota alerts.
- Audit:
  - Actor, action, status, target, timestamp, safe details.
- Dashboards:
  - Usage over time, exceeded quotas, provider error rates.

## 8) Testing Strategy

- Unit tests:
  - Secret encryption/decryption and key rotation behavior.
- API tests:
  - Admin key dry-run/rotate/status and authorization checks.
- Integration tests:
  - Chat stream continuity after key rotation without restart.
- Regression tests:
  - Ensure no secret leakage in responses/audit payloads.

## 9) Operational Checklist

- Before merge:
  - Update CHANGELOG.md and docs/ai-worklog.md.
  - Pass quality gate and CI.
- Before release:
  - Verify migrations and key management endpoints.
  - Validate runbook coverage for key rotation and rollback.

## Official References

- Google AI Gemini API docs:
  - https://ai.google.dev/gemini-api/docs
- Google AI API keys guidance:
  - https://ai.google.dev/gemini-api/docs/api-key
- OpenAI developer docs:
  - https://platform.openai.com/docs
- OpenAI function/tool calling:
  - https://platform.openai.com/docs/guides/function-calling
- OpenAI structured outputs:
  - https://platform.openai.com/docs/guides/structured-outputs
