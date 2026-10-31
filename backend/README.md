# Backend setup

Python 3.11+ required. From this directory:

    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\\Scripts\\Activate.ps1
    pip install -r requirements.txt
    cp .env.example .env        # Windows: Copy-Item .env.example .env
    uvicorn app.main:app --reload

API docs: http://127.0.0.1:8000/docs
Health: http://127.0.0.1:8000/health
Tests: pytest -q

Default local SQLite file is devsync.db. Change SECRET_KEY and configure DATABASE_URL/CORS_ORIGINS before any shared deployment. Login accepts OAuth2 form fields username=email and password=password.


## GitHub webhook setup

Set `GITHUB_WEBHOOK_SECRET` in the backend environment to a long random secret. In the linked GitHub repository, create a webhook targeting `https://YOUR_API_HOST/api/v1/github/webhooks`, choose **application/json**, use the exact same secret, and subscribe to **Push**, **Pull requests**, **Check runs**, and **Check suites**. The endpoint verifies GitHub's `X-Hub-Signature-256` header, records delivery IDs for idempotency, stores commit/pull-request/check activity, and broadcasts project events over the existing WebSocket channel. Unlinked repositories are acknowledged but ignored. Do not expose the webhook secret in frontend or extension code.


## AI GitHub review and CI diagnosis

After connecting GitHub and linking a repository to a project, open the **GitHub** tab in the dashboard. Members with the project `review` permission can enter a pull-request number and request an AI code review. Project members can enter a full commit SHA to analyze failed GitHub Actions runs. Results are saved in project analysis history.

Set `GEMINI_API_KEY` in the backend environment to enable AI analysis. The selected PR diff or failed workflow logs are sent to the configured Gemini model after size limits and common-secret redaction. Review findings are advisory only; developers must verify them. DevSync does not post review comments to GitHub, approve PRs, change code, or merge automatically.
