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
- POST /github/projects/{project_id}/pull-requests/{pull_number}/review — fetches the linked repository pull-request diff and creates a persisted Gemini-assisted review. Requires project review permission and a connected GitHub account with repository access.
- POST /github/projects/{project_id}/checks/{commit_sha}/analyze — finds failed Actions runs for a commit, collects failed job/step evidence and available logs, and creates a persisted Gemini diagnosis. Requires project membership and a connected GitHub account with Actions log access.
- GET /github/projects/{project_id}/ai-analyses?limit=20 — lists persisted AI review and CI diagnosis history for project members.

AI analysis requires GEMINI_API_KEY. Diffs/logs are truncated and common credential patterns are redacted before sending to Gemini. AI findings are advisory, require human verification, and never approve, merge, or modify code.
