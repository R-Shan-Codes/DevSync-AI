# Core integration hardening milestone

This milestone builds on the existing backend, dashboard and VS Code extension rather than replacing them.

## Included changes

- Added authenticated project WebSocket tests covering successful member connection and ping/pong.
- Added negative WebSocket authorization tests for missing credentials and users outside the project.
- Added a complete task pipeline integration test from backlog through merged, including rejection of a skipped transition.
- Fixed dashboard WebSocket lifecycle handling: unmounted or project-switched views no longer schedule reconnect attempts, and reconnect delay backs off from 1 to 15 seconds.

## Existing core capabilities verified by source inspection

- FastAPI backend with SQLite/SQLAlchemy persistence, JWT authentication and project membership permissions.
- Project and task APIs with server-side workflow transition enforcement.
- Git status, branch and commit synchronization endpoints.
- Authenticated project-scoped WebSocket endpoint and broadcast manager.
- Development event and file metadata ingestion from the VS Code extension.
- React dashboard surfaces for projects, tasks, team access, Git, AI assistance and development intelligence.
- Gemini-backed task recommendations are persisted for explicit human review; they are not automatically applied.

## Verification status

The new tests and frontend build have been added to the repository but have not been executed in this assistant environment. Run the backend and frontend checks from the repository root:

### Backend (Windows CMD)

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
pytest -q
```

### Frontend

```cmd
cd frontend
npm install
npm run build
```

### VS Code extension

```cmd
cd vscode-extension
npm install
npm run compile
```

Do not treat source changes or a successful GitHub commit as proof that runtime verification passed. Configure a non-default `SECRET_KEY`, explicit `CORS_ORIGINS`, and optional `GEMINI_API_KEY` / GitHub OAuth settings before shared deployment.
