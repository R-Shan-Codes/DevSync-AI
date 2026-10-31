# Development Roadmap

## Delivered implementation foundations
1. FastAPI backend, SQLAlchemy persistence, authentication, projects, memberships and permissions.
2. Role-aware task lifecycle, assignment, activity, priority, due dates and task comments.
3. VS Code Git metadata synchronization, commit/task linking and dashboard realtime refresh.
4. React dashboard, team management, Git/GitHub views and task collaboration workspace.
5. GitHub OAuth connection, signed webhook processing, Gemini-assisted PR review and failed-CI diagnosis.
6. AI role assistance, project memory, contribution evidence, bug analysis, conflict analysis and read-only development pipeline.
7. Project cycles/sprints with goals, date ranges, status and task progress.
8. Milestones/roadmap cards with due dates, status and linked-task progress.
9. Task parent-child hierarchy with project-scoped validation and cycle prevention.

## Current verification boundary
Latest planning milestone CI: backend 75 tests passed, frontend TypeScript check and production build passed, and VS Code extension TypeScript compilation passed. External OAuth, inbound webhook delivery and live Gemini behavior remain deployment-dependent.

## P0 — Complete and stabilize planning milestone
- Verify cycle/milestone CRUD, date validation, project isolation and hierarchy cycle prevention.
- Verify frontend type-check/build and backend regression suite.
- Review and merge the stacked implementation PRs in dependency order after owner approval.

## P1 — Finish core project-management workflows
- Task estimates, labels/tags, typed custom fields and richer filters.
- Threaded comments, @mentions, comment editing and persistent notifications.
- Multi-level hierarchy tree, roll-up progress and bulk operations.
- Search, sorting, pagination and saved views.
- Attachments with secure storage, access control and upload limits.

## P2 — Advanced planning and workflow management
- Timeline/Gantt roadmap views and milestone dependencies.
- Sprint backlog planning, capacity, velocity and historical reporting.
- Configurable workflow states and transition rules.
- Recurring tasks, templates and bulk task operations.

## P3 — Automation and differentiated intelligence
- Audited trigger-condition-action automation with idempotency, retries and dry-run.
- Permission-aware repository/project memory with citations and retention.
- More predictive conflict intelligence and configurable evidence-backed pipeline gates.

## P4 — Production readiness and live acceptance
- Alembic migrations and a supported production database/backup plan.
- Secret rotation, token lifecycle/revocation, CORS, rate limiting and observability.
- Deploy dashboard/backend and verify GitHub OAuth, public webhook delivery and Gemini calls.
- Run one comprehensive end-to-end acceptance test across VS Code, API, database, WebSockets, dashboard and GitHub integrations.

## Definition of done
A milestone is complete only after implementation, authorization checks, persistence, regression tests, client integration, documentation and CI are verified. Deployment-dependent integrations additionally require live checks. Never describe mocked external-service tests as live verification.
