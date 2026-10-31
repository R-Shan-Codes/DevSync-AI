# Conflict and Pipeline Intelligence

## Merge conflict analysis

The existing endpoint `POST /api/v1/projects/{project_id}/conflicts/analyze` is now surfaced in the Git & Reviews dashboard. It uses the backend-local repository and Git's `merge-tree` engine to compare two refs. It reports actual merge conflicts separately from files changed on both branches. The operation is read-only and never checks out, merges, resets or pushes either ref.

The repository path must resolve inside `WORKSPACE_ROOT`. The backend host must have Git 2.38 or newer for `git merge-tree --write-tree`. This does not analyze a remote GitHub branch unless that branch has first been fetched into the local repository.

## Smart development pipeline

Added `GET /api/v1/projects/{project_id}/pipeline`. It returns task stages, the suggested next human action, dependency blockers, open bug counts, latest code-review evidence and latest test-run evidence.

The endpoint is intentionally read-only. It does not change task status, assign work, approve reviews, run tests or merge code. A task is marked ready for the next step only when its recorded evidence has no known blocker:
- All declared prerequisites must be in `passed` or `merged`.
- Tasks in review/testing/delivery stages require an approved latest review.
- Tasks in passed/merge stages require a passing latest test run.
- Open bug reports are surfaced as blockers.

This is an evidence-based readiness view, not an enforcement boundary. Existing task transitions and permissions remain unchanged in this milestone.

## Dashboard

- Adds a Development Pipeline view with stage counts, per-task next actions, dependency blockers, review/test evidence and open bug counts.
- Adds a read-only conflict analyzer to Git & Reviews, using the existing local repository path and branch refs.

## Verification

New tests in `backend/tests/test_pipeline.py` cover stage reporting, prerequisite blockers and project isolation. Existing conflict validation tests remain in `backend/tests/test_conflicts.py`.

Run:

```bash
cd backend
pytest -q
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

These checks must run in the development environment; GitHub Actions results and local results should be reported separately.

## Workflow coordination

Unassigned, active tasks now include up to three suggested owners. The recommendation ranks active project members using task-keyword/role alignment and their count of active assigned tasks. It excludes inactive accounts and considers workload before display-name tie-breaking. These are transparent heuristics, not AI judgments or performance ratings. Suggestions never assign a task; a project member must make that decision through the existing task-management workflow.

## Persistent project context for the role assistant

The role assistant now receives a bounded snapshot of recent code reviews, test runs, open bug reports, developer handovers and VS Code development-event metadata alongside tasks, activity and commits. This lets it reason from recorded delivery history. The assistant is instructed to distinguish evidence from inference and say when context is insufficient. Only a bounded recent subset is included in each request; this is not an unlimited transcript or repository-content index.
