# DevSync AI

**One Team. Multiple Roles. One Synchronized Codebase.**

DevSync AI is a collaborative engineering workspace that connects project tasks, role-based delivery, Git/GitHub activity, code review, QA evidence, real-time updates and AI-assisted development.

## Product modules

- **FastAPI backend** — authentication, project/team membership, role permissions, task workflow, GitHub OAuth/webhooks, AI endpoints and WebSockets.
- **React dashboard** — project overview, tasks, team permissions, activity, Git monitoring, GitHub AI review, development intelligence, pipeline, project memory and collaborative delivery workspace.
- **VS Code extension** — account/project connection, task workflow actions, bug reporting, Git metadata and workspace activity synchronization.
- **SQLite + SQLAlchemy** — initial persistent store.
- **Gemini integration** — role assistance, AI recommendations, GitHub pull-request review and failed-CI diagnosis.

## Current delivery workflow

Task creation → coding → submission → code review → approval → QA/testing → passed → ready for merge → merged.

The application records review and test evidence and surfaces pipeline readiness. It does not silently approve work, assign tasks, advance workflow stages or merge code. Humans retain control of consequential actions.

## Repository layout

- `backend/` — FastAPI application, SQLAlchemy models and automated tests.
- `frontend/` — React + TypeScript dashboard.
- `vscode-extension/` — TypeScript VS Code extension.
- `docs/` — architecture, API contracts, integration runbooks and product capability audit.

## Setup

- Backend: see [backend setup](backend/README.md).
- Dashboard: see [frontend setup](frontend/README.md).
- VS Code extension: see [extension setup](vscode-extension/README.md).
- GitHub/Gemini deployment: see [live integration runbook](docs/live-github-ai-integration.md).

## Product scope and next work

DevSync already has a functioning engineering workflow foundation, but it is **not yet a complete Jira/Linear/Asana replacement**. Advanced planning and work-management capabilities—such as cycles/sprints, milestones/roadmaps, task comments and mentions, attachments, labels/custom fields, saved views, rich search, configurable automation and notification preferences—remain product gaps.

See [the implementation-backed capability audit](docs/product-capability-audit.md) for what exists, what is partial and what should be built next. The [development roadmap](docs/development-roadmap.md) is ordered by product impact and delivery dependency.

## Verification status

The current open implementation PR reports passing GitHub Actions for backend (68 tests), frontend (TypeScript check and production build) and VS Code extension (TypeScript compilation). These are CI results for the PR branch, not a claim that deployment-dependent GitHub OAuth, inbound webhook delivery or live Gemini calls have been verified. The implementation PR remains subject to review and merge.
