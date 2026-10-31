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

DevSync already has a functioning engineering workflow foundation, but it is **not yet a complete Jira/Linear/Asana replacement**. DevSync now includes project cycles/sprints, milestone roadmap cards, task parent-child relationships, priority, due dates and basic task discussion in its active implementation branch. Remaining gaps include timeline/Gantt planning, estimates, labels/custom fields, threaded comments and mentions, saved views, rich search, attachments, configurable automation and persistent notification preferences.

See [the implementation-backed capability audit](docs/product-capability-audit.md) for what exists, what is partial and what should be built next. The [development roadmap](docs/development-roadmap.md) is ordered by product impact and delivery dependency.

## Verification status

The latest verified implementation baseline reported passing GitHub Actions for backend (71 tests), frontend (TypeScript check and production build) and VS Code extension (TypeScript compilation). The current planning milestone is under CI verification. These are CI results for feature branches, not a claim that deployment-dependent GitHub OAuth, inbound webhook delivery or live Gemini calls have been verified. Changes remain subject to review and merge.
