# API v1 Overview

Base path: /api/v1

## Authentication
- POST /auth/register — create an account (email, display_name, password).
- POST /auth/login — OAuth2 form fields username=email and password=password; returns a bearer token.
- GET /auth/me — current authenticated user.

## Projects
- POST /projects — create a project; creator becomes administrator.
- GET /projects — list projects for current user.
- GET /projects/{project_id} — project details.
- GET /projects/{project_id}/members — list project members.
- POST /projects/{project_id}/members — administrator adds a registered user by email and role.

## Tasks
- POST /projects/{project_id}/tasks — create task (administrator or coder).
- GET /projects/{project_id}/tasks — list project tasks.
- PATCH /projects/{project_id}/tasks/{task_id} — update task and move through validated workflow states.

## Activity
- GET /projects/{project_id}/activity?limit=50 — newest project activity (limit 1–200).

All project endpoints require membership. Use Authorization: Bearer <access_token>. Interactive OpenAPI documentation is available at /docs when the API is running.


## GitHub webhook receiver
- POST /github/webhooks — public GitHub webhook endpoint. Requires a configured `GITHUB_WEBHOOK_SECRET` and valid `X-Hub-Signature-256`, `X-GitHub-Delivery`, and `X-GitHub-Event` headers. Handles push, pull_request, check_run, and check_suite events for repositories linked to a project. Delivery IDs are persisted to prevent duplicate processing.


## AI GitHub review and CI diagnosis
- POST /github/projects/{project_id}/pull-requests/{pull_number}/review — creates a persisted Gemini-assisted review.
- POST /github/projects/{project_id}/checks/{commit_sha}/analyze — analyzes failed GitHub Actions evidence.
- GET /github/projects/{project_id}/ai-analyses — lists project-scoped analysis history.
- POST /github/projects/{project_id}/ai-analyses/{artifact_id}/tasks — explicitly links an analysis to a task; requires project edit permission.
- GET /github/projects/{project_id}/ai-analyses/{artifact_id}/tasks — lists task links for an analysis.
- GET /projects/{project_id}/pipeline — includes the latest task-linked AI analysis as advisory evidence. AI findings do not automatically create bugs, block tasks, change statuses, approve or merge.


## VS Code development-event synchronization
- POST /projects/{project_id}/intelligence/events — authenticated, edit-permission event ingestion (1–100 events per batch). Supported event types include file.created/changed/deleted, workspace.opened, branch.changed and commit.created.
- GET /projects/{project_id}/intelligence/events — recent project development events.
- GET /projects/{project_id}/intelligence/files — recent file-change metadata.
- A valid 40-character Git commit hash in a commit.created event is also persisted as a project Git event (idempotent per project/commit), making it available to the existing commit-task suggestion and explicit commit-link endpoints.
- The dashboard WebSocket at /ws/projects/{project_id} broadcasts event notifications; connected dashboard views refresh activity, development intelligence and pipeline data.


## GitHub integration hardening
- GitHub OAuth requests `repo read:user`; the access token is encrypted at rest with `GITHUB_TOKEN_ENCRYPTION_KEY` (Fernet).
- POST /github/webhooks — HMAC-SHA256 authenticated; request body capped at 2 MB; exact repository matching; duplicate delivery and commit protection.
- AI PR diff downloads are capped at 2 MB before text truncation/redaction. GitHub Actions log downloads are streamed with a 10 MB cap; ZIP extraction is limited to 20 log files and 45,000 characters.
- Gemini API key is sent using the `x-goog-api-key` header. Common GitHub, Google, AWS, bearer, JWT, Slack and npm credential formats are redacted before analysis.
- Live OAuth, webhook delivery and Gemini API verification are deployment-dependent; see `docs/live-github-ai-integration.md`.

### POST /github/projects/{project_id}/integration-check
Requires project view permission. Runs a live, non-persistent diagnostic of GitHub OAuth configuration, the connected GitHub account, access to the project's linked repository, Gemini API connectivity and webhook-secret configuration. Returns an overall status and per-integration status/detail records. It never returns credentials. A configured webhook secret is reported as a warning because public inbound delivery must be verified from GitHub's webhook delivery history.
