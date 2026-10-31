# Core integration hardening milestone

This milestone is now based on the consolidated product implementation on `main`.

## Included changes

- WebSocket database access uses FastAPI's injected `get_db` dependency, so tests and deployments use the configured database session.
- Authenticated project WebSocket tests cover successful member connection and ping/pong.
- Negative WebSocket authorization tests cover missing credentials and users outside the project.
- A complete task pipeline integration test exercises every valid transition from backlog through merged and rejects a skipped transition.
- The consolidated dashboard already includes bounded WebSocket reconnection, heartbeat messages and cleanup on project changes/unmount.

## Verification

GitHub Actions passed for the source hardening branch:
- Backend CI: success.
- Frontend CI: success.
- VS Code Extension CI: success.

The post-consolidation branch will run the same workflows before merge. CI does not replace live verification of GitHub OAuth, inbound webhook delivery or Gemini credentials; those still require deployment configuration.

## Local verification (Windows CMD)

```cmd
cd backend
.venv\Scripts\activate
pytest -q
```

```cmd
cd frontend
npm run build
```

```cmd
cd vscode-extension
npm run compile
```
