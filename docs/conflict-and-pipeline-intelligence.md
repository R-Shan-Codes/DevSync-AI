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

## AI review evidence in the development pipeline

AI pull-request reviews and CI diagnoses can be explicitly linked to a project task from the GitHub analysis detail view. Linking requires project edit permission and validates that both the analysis and task belong to the same project. Duplicate links are idempotent.

The Development Pipeline then displays the latest linked analysis summary, source identifier and finding count on that task. This is advisory context only: AI findings are not treated as confirmed bugs, do not create blockers, and never change task status or delivery readiness. A human must verify findings and use the existing bug-report workflow when an issue is confirmed.

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


## Collaborative delivery workspace

The Tasks tab now includes a unified collaboration workspace for each selected task. It connects the existing project APIs rather than introducing a second workflow store:

- **Ownership:** project managers with `manage_team` permission can assign a task to an active project member.
- **Code review:** members with `review` permission can record an approval, change request or comment, including summary and findings.
- **QA evidence:** members with `edit` permission can record passed, failed or blocked test runs with validated result counts and execution notes.
- **Bug reporting:** members with `edit` permission can create severity-ranked bug reports linked to the selected task.
- **Evidence history:** the selected task shows its persisted reviews, test runs and bug reports together.

The UI hides or disables actions when the current member lacks the corresponding permission, while the backend remains authoritative and enforces permissions and project/task ownership. Recording a review, test run or bug does not automatically transition a task, close an issue, approve a release or merge code. The existing explicit task transition API remains the workflow authority.

Backend regression coverage in `backend/tests/test_collaboration_workflow.py` verifies evidence creation, pipeline visibility, cross-project task isolation and test-count validation.


## VS Code → backend → dashboard synchronization

The VS Code extension now emits workspace-opened, branch-changed and commit-created metadata in addition to file-change metadata. It polls the active workspace's Git branch and latest commit every 15 seconds, batches event ingestion through the authenticated project API and retains failed batches for retry. It uploads commit metadata only; it does not upload source code or diffs.

The backend persists valid commit-created events as Git events with project-scoped commit-hash deduplication. This connects editor-observed commits to the existing commit-to-task matching flow: the dashboard proposes heuristic task matches, and a member with edit permission explicitly confirms a link. No task association is silently created.

The dashboard's project WebSocket now triggers refreshes of the Activity timeline, AI Development Intelligence and Development Pipeline. The Activity timeline combines project activity records with individual developer events. This keeps connected clients synchronized without treating a WebSocket notification as the source of truth; views re-fetch persisted records from the API.
