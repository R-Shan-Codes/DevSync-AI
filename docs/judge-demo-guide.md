# DevSync AI — Judge Demo Guide

This guide provides a repeatable walkthrough for evaluating the current implementation. It distinguishes the interactive sample experience from features backed by the API.

## 1. Fastest way to open the interactive demo

The standalone demo does not require a backend, account, database, GitHub OAuth app or Gemini key.

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173/?demo=1**.

The public demo route is intentionally read-only with respect to the real application: it loads sample members, tasks, bugs and activity in browser memory. It makes no API calls and does not persist changes. A visible **SIMULATED ENVIRONMENT / DEMO DATA ONLY** banner identifies this clearly.

## 2. Suggested 3–5 minute judge walkthrough

1. **Team role switching** — choose Team Leader / Project Manager, Frontend Developer, Backend Developer and Tester / QA Engineer. Explain how the visible task list changes by role.
2. **Task lifecycle** — move a sample task through In Progress, Submitted, In Review, Ready for Testing, Testing and Passed. Point out the activity stream updates immediately.
3. **QA / bug intake** — switch to Tester / QA Engineer, report a sample defect, and show the new simulated bug and activity entry.
4. **Collaboration concept** — explain that the full authenticated workspace persists tasks, assignments, review decisions, test evidence and bug reports through the FastAPI backend.
5. **Planning and intelligence** — in the authenticated application, show the Planning, AI Intelligence, Development Pipeline, GitHub and Insights & Memory tabs when configured.

Do not present sample records or browser-only demo interactions as persisted backend data.

## 3. Run the full application

Use two terminals.

### Backend

```bash
cd backend
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Then:

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

On Windows PowerShell, use `Copy-Item .env.example .env` instead of `cp`.

Backend health: **http://127.0.0.1:8000/health**  
Interactive API documentation: **http://127.0.0.1:8000/docs**

### Dashboard

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** (without `?demo=1`) to register an account, sign in and create a project.

## 4. Optional integrations

- **Gemini AI:** set `GEMINI_API_KEY` in `backend/.env` to enable AI role assistance, task recommendations and AI GitHub review/CI analysis.
- **GitHub:** configure GitHub OAuth client ID, client secret, callback URL and token encryption key in `backend/.env`; then connect an account and link a repository from the GitHub tab.
- **GitHub webhooks:** configure `GITHUB_WEBHOOK_SECRET` and a publicly reachable HTTPS webhook endpoint as described in [the live integration runbook](live-github-ai-integration.md).
- These external integrations are not required for the standalone demo. Do not put secrets in frontend environment files or screenshots.

## 5. What is implemented vs. what the demo simulates

| Area | Evaluation status |
|---|---|
| Public role-switching demo, sample task transitions, sample bug intake and activity | Interactive browser-only simulation |
| Authentication, projects, team roles and permissions | Backend-backed |
| Tasks, review decisions, QA test evidence and bug reports | Backend-backed |
| Cycles, milestones and task hierarchy | Backend-backed |
| Development pipeline, contribution intelligence and project memory | Backend-backed |
| VS Code workspace/Git metadata events and dashboard synchronization | Implemented; requires configured extension and running backend |
| GitHub OAuth, webhook delivery and Gemini-powered analysis | Implemented integration paths; require credentials and live deployment verification |

The latest planning feature branch has reported passing GitHub Actions: backend tests, frontend TypeScript/production build and VS Code extension TypeScript compilation. Those CI results do not prove that this application has been deployed or that credential-dependent integrations work in a live environment.

## 6. If asked what makes DevSync different

DevSync connects the development lifecycle rather than stopping at a task board:

**Task → Coding → Submission → Review → QA evidence → Merge readiness**

It combines role-aware workspaces, Git activity, AI assistance, conflict analysis, project memory and an evidence-based pipeline. Consequential actions such as approval, task transitions and merging remain under human control.
