# Development Roadmap

This roadmap reflects the code currently present in the implementation branch. A feature is not considered production-verified merely because its code or mocked tests exist.

## Completed implementation foundations

1. **Backend and persistence foundation** — FastAPI, SQLAlchemy, SQLite, authentication, projects, memberships, permissions and automated tests.
2. **Role-based delivery workflow** — task creation, assignment, validated transitions, activity, review records and QA test-run evidence.
3. **Git and editor integration** — Git metadata synchronization, VS Code task actions, workspace events, commit persistence and explicit commit-to-task links.
4. **Dashboard foundation** — React dashboard for project overview, tasks, team, activity and engineering workflow views.
5. **Realtime collaboration** — authenticated project-scoped WebSockets and dashboard refresh behavior.
6. **AI development assistance** — role assistant, persisted conversations/recommendations, development memory and contribution evidence.
7. **Engineering intelligence** — dependency graph with cycle prevention, bug reports and impact analysis, conflict analysis, pipeline readiness, handovers and advisory owner suggestions.
8. **GitHub integration** — OAuth account connection, signed webhook processing, PR/CI activity, Gemini-assisted PR review and failed-CI diagnosis, AI analysis history and explicit task linking.
9. **Workflow evidence workspace** — task ownership, review decisions, QA outcomes and bug reports in a unified task-focused dashboard.

## Current verification boundary

The implementation branch's latest recorded GitHub Actions checks passed: backend 68 tests, frontend TypeScript check and production build, and VS Code extension TypeScript compilation. The checks include mocked external-service flows. Real OAuth, public inbound webhook delivery and live Gemini requests still require deployed secrets and a public HTTPS backend. The implementation PR must be reviewed and merged before these changes become part of `main`.

## Priority 0 — Stabilize and verify the integrated product

1. Review and merge the current implementation PR after owner approval.
2. Add Alembic migrations and a tested upgrade path from existing SQLite data.
3. Add production configuration validation, secret rotation guidance, token revocation/lifecycle handling, explicit CORS origins and rate limits.
4. Deploy backend and dashboard; configure GitHub OAuth, webhook secret, Fernet encryption key and Gemini credentials as deployment secrets.
5. Verify the full live path once: VS Code → API → database → WebSocket → dashboard, GitHub webhook → activity, GitHub OAuth/repository access and real Gemini review/CI diagnosis.

## Priority 1 — Complete the project-management essentials

These are the largest gaps relative to mature products such as Jira, Linear and Asana:

1. Task priority, due dates, labels/tags and richer task metadata.
2. Task comments, threaded discussion, @mentions and edit/delete history.
3. Subtasks/parent-child issue hierarchy and milestone association.
4. Search, filters, sorting, pagination and saved views.
5. Attachments with safe storage, access control and size/type limits.
6. In-app notifications and user notification preferences.

## Priority 2 — Planning and workflow customization

1. Sprints/cycles with start/end dates, goals and backlog planning.
2. Milestones and project roadmaps with progress rollups.
3. Configurable workflow states and transition rules.
4. Team capacity and workload planning.
5. Recurring tasks, templates and bulk task operations.

## Priority 3 — Automation and ecosystem

1. Rule-based automation with explicit triggers, conditions, actions, audit history and safe retry semantics.
2. Additional integrations such as Slack/Teams, issue trackers and deployment providers.
3. Rich GitHub PR checks, review assignment and release/deployment visibility.
4. Presence, typing/active collaboration signals and richer notification delivery.

## Priority 4 — Advanced DevSync intelligence

1. Repository-aware project memory with permission-aware indexing and retention controls.
2. Cross-task and cross-branch conflict prediction with explainable evidence.
3. Contribution insights that remain transparent, contextual and explicitly not employee rankings.
4. Smart pipeline policies that can be configured by project while preserving human approval gates.
5. AI-generated tests and debugging workflows connected to actual test execution evidence.

## Definition of done

A milestone is complete only when implementation, authorization checks, persistence, automated regression tests, client integration, documentation and CI are verified. Deployment-dependent integrations must additionally pass live checks. Do not label mocked external-service tests as live integration verification.
