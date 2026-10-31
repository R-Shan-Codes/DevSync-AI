# DevSync AI Architecture

## Current system shape

DevSync is a modular FastAPI monolith serving two clients:

- A React + TypeScript dashboard.
- A TypeScript VS Code extension.

The backend exposes REST APIs under `/api/v1` and authenticated, project-scoped WebSockets at `/ws/projects/{project_id}`. SQLite is the initial database, accessed through SQLAlchemy ORM models. Git is the source of truth for branches, commits and merges; DevSync stores workflow metadata and links it to Git activity.

## Main components

### Backend

- Authentication and bearer-token authorization.
- Project creation, membership, role and permission management.
- Task creation, assignment, validated workflow transitions and dependency management.
- Activity, code-review, test-run and bug-report records.
- Git metadata ingestion, commit-to-task suggestions and explicit commit links.
- GitHub OAuth account connection, signed webhook ingestion and repository activity.
- Gemini-backed role assistance, task recommendations, pull-request review and failed-CI diagnosis.
- Project intelligence, developer handovers, contribution evidence and pipeline readiness.
- Authenticated project WebSockets for event notifications.

### Dashboard

The dashboard includes project overview, role workspace, task board and collaborative delivery workspace, team management, activity timeline, Git/conflict monitoring, GitHub AI review and integration diagnostics, AI assistant, development intelligence, development pipeline, and project memory.

### VS Code extension

The extension connects an authenticated user to a project, displays tasks, supports permitted task-stage actions and bug reporting, and sends bounded workspace/file/Git metadata events to the backend. Authentication tokens use VS Code SecretStorage. The telemetry path does not upload source file contents or diffs.

## Core data boundaries

- Roles and permissions are project-membership attributes, not global user roles.
- Project-scoped endpoints validate membership and permissions on the server.
- Git remains authoritative for repository state and merges.
- AI findings and task-owner suggestions are advisory; a human confirms changes.
- Review and QA records are evidence. Recording evidence does not itself approve a release or merge code.
- GitHub webhook deliveries are signature-verified and deduplicated.
- GitHub credentials are encrypted at rest; provider credentials remain on the backend.
- AI evidence is size-bounded and common secrets are redacted before Gemini requests.

## Delivery pipeline

Task creation → coding → submission → code review → approval → QA/testing → passed → ready for merge → merged.

The pipeline endpoint is a read-only projection of task state, dependencies, review/test evidence, open bugs and linked AI analyses. It reports blockers and next human actions; it does not execute transitions.

## Realtime behavior

Clients receive project-scoped event notifications over WebSockets. The dashboard refreshes persisted project data when notifications arrive and sends periodic heartbeats with bounded reconnect backoff. The VS Code extension batches metadata events and retries transient failures with a bounded queue.

## Current implementation constraints

- SQLite is the initial persistence target; production migration strategy and operational database choice still need to be finalized.
- SQLAlchemy metadata table creation is currently used for rapid iteration; Alembic migrations are a production-readiness requirement.
- Git conflict analysis operates on refs available in the backend's local workspace, not arbitrary remote refs unless fetched there first.
- Public webhook delivery and OAuth/Gemini behavior require deployment configuration and live verification.
- The current task model is intentionally lean; it does not yet include the full planning and collaboration surface of mature work-management products.

## Security and production hardening backlog

Before broad production use, complete and verify schema migrations, secure secret rotation, token lifecycle/revocation, explicit production CORS/origin policy, rate limiting, structured audit trails, backup/restore, observability, deployment health checks and a production database strategy. Keep secrets in deployment environment variables or a secret manager, never in source control.
