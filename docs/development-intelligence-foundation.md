# Development Intelligence Foundation

This change adds an additive foundation for the next DevSync AI capabilities. It does not replace the existing task, Git, project, or authentication APIs.

## Database behavior

The new SQLAlchemy models are registered through the existing `app.models` import used by `init_db()`. On startup, the existing `Base.metadata.create_all()` creates the new tables without altering or dropping existing tables:

- `development_events`
- `file_changes`
- `task_dependencies`
- `commit_task_links`
- `ai_conversations`
- `ai_messages`
- `ai_recommendations`
- `ai_overrides`
- `handover_records`

No existing columns are changed in this milestone. Back up the SQLite database before deploying any schema change. A versioned Alembic migration workflow remains a production-hardening task.

## New API routes

All routes except the existing WebSocket route use the standard bearer token.

| Method | Route | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/intelligence/events` | Ingest up to 100 development events in one batch |
| GET | `/projects/{project_id}/intelligence/events` | Read project development events |
| GET | `/projects/{project_id}/intelligence/files` | Read tracked file changes |
| GET | `/projects/{project_id}/intelligence/summary` | Read activity and recommendation counts |
| GET | `/projects/{project_id}/intelligence/my-memory` | Read current developer's assigned tasks, events, files and handovers |
| POST | `/projects/{project_id}/tasks/{task_id}/dependencies` | Add a task prerequisite; cycles are rejected |
| GET | `/projects/{project_id}/tasks/{task_id}/dependencies` | List prerequisites |
| DELETE | `/projects/{project_id}/tasks/{task_id}/dependencies/{dependency_id}` | Remove a prerequisite |
| POST | `/projects/{project_id}/intelligence/commit-links` | Link an existing synchronized commit to a task |
| GET | `/projects/{project_id}/intelligence/commit-links` | List commit/task links |
| POST | `/projects/{project_id}/ai/conversations` | Create a role-bound conversation |
| GET | `/projects/{project_id}/ai/conversations` | List the current user's conversations |
| GET | `/projects/{project_id}/ai/conversations/{conversation_id}/messages` | Read persisted messages |
| POST | `/projects/{project_id}/ai/conversations/{conversation_id}/messages` | Persist a user message and Gemini response |
| DELETE | `/projects/{project_id}/ai/conversations/{conversation_id}` | Delete an owned conversation and its messages |
| POST | `/projects/{project_id}/ai/recommendations` | Record a proposed AI recommendation |
| GET | `/projects/{project_id}/ai/recommendations` | List recommendations |
| POST | `/projects/{project_id}/ai/recommendations/{recommendation_id}/override` | Accept, reject or modify a recommendation with an audit record |
| POST | `/projects/{project_id}/handover` | Create a developer handover |
| GET | `/projects/{project_id}/handover` | Read project handover history |

## VS Code event synchronization

The extension now batches file create/change/delete events and sends them to the backend after a short debounce. It ignores common generated and dependency folders (`.git`, `node_modules`, `.venv`, `venv`, `dist`, `build`, `coverage`, `.next`). It sends file paths and metadata only; it does not upload file contents.

The event API requires project Edit permission and rejects absolute paths, traversal paths and event payloads larger than 12 KB.

## Important behavior and limitations

- Task dependencies are validated to prevent self-dependencies and cycles.
- Commit/task links are explicit and confidence-scored. The system does not infer task ownership from commit messages yet.
- AI conversations persist user messages before contacting Gemini. If Gemini is unavailable, the saved user message remains available for retry or review.
- Conversation access is restricted to the owning user and project; the conversation role must match the user's current project role.
- AI recommendations do not change task state. Human decisions are separately recorded as accepted, rejected or modified; modified decisions require a replacement value.
- Developer handovers are persisted and included in the personal project memory response.
- The existing project memory endpoint remains available and unchanged.

## Verification

Automated tests were added in `backend/tests/test_intelligence.py` for event ingestion, file tracking, path traversal rejection, dependency cycle prevention, persistent conversations, recommendation overrides and handovers.

Run locally:

```bash
cd backend
python -m pip install -r requirements.txt
pytest -q
```

Compile the VS Code extension:

```bash
cd vscode-extension
npm install
npm run compile
```

These commands must be executed in the development environment. A source update or successful GitHub commit does not establish that tests passed.
