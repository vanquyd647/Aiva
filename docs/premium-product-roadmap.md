# AI Assist Premium Product Roadmap (12 Weeks)

Date: 2026-04-24
Owner: Product + Engineering
Target: Premium-grade release in 2-3 months
Audience: Individual/prosumer
Deployment: Hybrid (cloud + local mode)
Experience direction: Distinct pro dashboard + studio feel
Current status: Foundation + core chat UX + multimodal/file baseline + governance/quota dashboard + web search/citation v1 delivered.

## 1. Why This Roadmap

This roadmap upgrades AI Assist from a useful desktop assistant to a production-grade product with:
- Practical multimodal workflows
- Trustworthy answers with citations
- Strong recovery/error handling
- Real admin governance and auditability
- Usage metering and plan/quota controls

## 2. Research Anchors

The plan is based on repeatable patterns from:
- ChatGPT release notes: edit/regenerate, branching, retries, file library, projects, memory, connectors, code blocks, sharing, temporary chats.
- Google Gemini product updates: deep research, interactive simulations, personalized multimodal experiences.
- NN/g usability heuristics: visibility of status, user control/freedom, error prevention and recovery, recognition over recall, flexibility and efficiency.
- WCAG 2.2: keyboard support, focus visibility, contrast, status messages, target size, robust error messaging.
- OWASP logging guidance: structured event logging, sensitive-data exclusion, tamper protection, monitoring and retention.

## 3. Current Baseline

Existing strengths:
- Desktop user app and admin app with vi/en support.
- FastAPI backend with auth, user management, stats, health probes, conversation/message APIs.
- SSE backend chat streaming with desktop client adapter.
- File upload and inline image attachment path in chat runtime.
- Admin governance surface: audit trail, session revocation, and usage overview.
- Quota metering and per-user usage dashboard with alert levels.
- Redis cache fallback and stable local chat history.

Primary gaps:
- No project/workspace memory knowledge layer yet.
- No generalized tool calling + connectors yet.
- No sandbox execution for advanced analysis workflows yet.
- Need deeper observability package (latency/error dashboards, SLO reporting).
- Need accessibility-focused UI hardening pass (WCAG 2.2 AA checklist closure).

## 4. Target Platform Changes

### New backend entities
- Conversation
- Message
- Attachment
- Project
- ProjectSource
- MemoryItem
- ToolRun
- UsageEvent
- AuditLog
- UserSession

### New backend routes
- /chat/stream (SSE)
- /conversations
- /messages
- /files
- /projects
- /memory
- /search/web
- /tools
- /usage
- /admin/audit
- /admin/sessions

### New backend services
- chat_orchestrator
- citation_service
- file_ingestion_service
- embeddings_service
- tool_registry_service
- connector_service
- usage_metering_service
- audit_service
- background jobs

## 5. Delivery Plan (12 Weeks)

### Phase 0 (Week 1): Foundation and Safety
Goals:
- Establish data schema and service skeletons.
- Add interaction IDs and standard error envelopes.
Deliverables:
- DB migrations for new entities.
- Correlation middleware.
- Feature flags for phased rollout.
- Error taxonomy for retry paths.

### Phase 1 (Weeks 2-3): Core Chat UX Upgrade
Goals:
- Remove demo-like friction in core chat.
Deliverables:
- Message edit/regenerate/retry.
- Branch conversation from any message.
- Draft persistence.
- Better inline error recovery.

### Phase 2 (Weeks 4-5): Multimodal + Files + Projects/Memory
Goals:
- Support real user work inputs.
Deliverables:
- File/image upload + preview.
- Projects for grouped chats/files/instructions.
- Memory controls and scope handling.
- First document retrieval pipeline.

### Phase 3 (Weeks 6-7): Web Search + Citations + Tool Base
Goals:
- Improve trust and actionability.
Deliverables:
- Web search endpoint + source citations.
- Citation cards in chat responses.
- Tool calling allowlist framework.
- Initial connectors (start small, harden first).

### Phase 4 (Weeks 8-9): Data Analysis and Code Sandbox
Goals:
- Add pro-level productivity workflows.
Deliverables:
- Isolated sandbox for analysis tasks.
- Structured outputs for tables/charts/scripts.
- Guardrails for CPU/time/memory/output limits.

### Phase 5 (Weeks 10-11): Admin Governance + Usage/Quota
Goals:
- Make operation and monetization practical.
Deliverables:
- Audit trail explorer with filters/export.
- Session governance (list/revoke/force logout).
- Usage metering and plan quota enforcement.
- Basic pricing/consumption dashboard.

### Phase 6 (Week 12): Studio UX Polish + Accessibility + Launch
Goals:
- Reach premium quality bar.
Deliverables:
- Visual design pass across user/admin apps.
- WCAG 2.2 AA-focused hardening.
- Performance pass and release rollback plan.
- Launch notes and post-launch monitoring setup.

## 6. File Map for Initial Work

User app:
- app.py
- core/gemini.py
- core/history.py
- core/config.py
- core/i18n.py

Admin app:
- admin_app.py

Backend extension points:
- backend/app/main.py
- backend/app/api/routes/auth.py
- backend/app/api/routes/users.py
- backend/app/models/user.py
- backend/app/schemas/auth.py
- backend/app/schemas/user.py
- backend/app/services/cache.py

## 7. KPI Gates

User KPIs:
- Median time-to-first-token <= 1.5s (local), <= 2.5s (cloud)
- Message failure rate <= 1.5%
- Retry success >= 95%
- 7-day return users +20% vs current baseline

Ops/Security KPIs:
- P95 non-generation API latency <= 800ms
- Audit coverage for privileged actions = 100%
- No P0 data leak findings in release gate

Accessibility KPIs:
- Keyboard-only completion for core flows
- Focus visibility in all interactive controls
- Contrast and error message checks pass AA

## 8. Immediate Backlog (Next 7-10 Days)

1. Ship web search + source citation pipeline for answer trust.
2. Expand citation UX from text-append to dedicated citation cards in desktop chat bubbles.
3. Introduce projects/memory MVP (project-level context and retrieval hooks).
4. Add tool registry allowlist with execution safety guardrails.
5. Add observability pack (request tracing IDs, latency/error metrics, quota breach telemetry).
6. Complete accessibility hardening pass for user/admin desktop flows.

## 9. PR Execution Order

Completed:
- PR-1: Data models + migrations + route skeletons
- PR-2: Streaming transport + desktop client handling
- PR-3: Edit/regenerate/retry/branch UX
- PR-4: Audit logging baseline + admin viewer v1
- PR-5: File upload + attachment runtime integration
- PR-6: Search endpoint + citation grounding in chat stream

Next:
- PR-7: Citation cards UX + project/memory retrieval layer MVP
- PR-8: Tool registry + connector starter pack
- PR-9: Observability + governance hardening
- PR-10: Accessibility and launch polish
