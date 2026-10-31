# DevSync AI

**One Team. Multiple Roles. One Synchronized Codebase.**

DevSync AI coordinates Coders, Debuggers and Testers through a shared development workflow, Git activity, real-time collaboration and AI-assisted engineering.

The initial implementation is being built phase by phase. See [`docs/architecture.md`](docs/architecture.md) and [`docs/development-roadmap.md`](docs/development-roadmap.md).

## Repository layout

- `backend/` — FastAPI application and tests
- `frontend/` — React dashboard (next implementation phase)
- `vscode-extension/` — VS Code extension (later phase)
- `shared/contracts/` — cross-client event and API contracts
- `docs/` — architecture and development documentation

## Current implementation

Backend foundation: configuration, SQLite/SQLAlchemy, authentication, projects, memberships, tasks, activity records and automated tests.

## Quick start

See [`backend/README.md`](backend/README.md) for setup and execution instructions.
