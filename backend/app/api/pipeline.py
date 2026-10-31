from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member
from app.models import BugReport, CodeReview, ProjectMember, ProjectRole, Task, TaskDependency, TaskStatus, TestRun, User

router = APIRouter(prefix="/projects/{project_id}/pipeline", tags=["development pipeline"])

_COMPLETE_PREREQUISITE = {TaskStatus.passed, TaskStatus.merged}
_REVIEW_GATED = {
    TaskStatus.approved, TaskStatus.ready_for_testing, TaskStatus.testing,
    TaskStatus.passed, TaskStatus.ready_for_merge, TaskStatus.merged,
}
_TEST_GATED = {TaskStatus.passed, TaskStatus.ready_for_merge, TaskStatus.merged}


def _task_stage(status: TaskStatus) -> str:
    if status in {TaskStatus.backlog, TaskStatus.in_progress}:
        return "coding"
    if status in {TaskStatus.submitted, TaskStatus.in_review, TaskStatus.approved}:
        return "review"
    if status in {TaskStatus.ready_for_testing, TaskStatus.testing, TaskStatus.failed}:
        return "testing"
    if status in {TaskStatus.passed, TaskStatus.ready_for_merge}:
        return "merge"
    if status == TaskStatus.merged:
        return "complete"
    return "cancelled"


@router.get("")
def get_pipeline(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return an evidence-backed pipeline view; this endpoint never mutates tasks."""
    get_project_member(project_id, db, user)
    tasks = db.scalars(
        select(Task).where(Task.project_id == project_id).order_by(Task.updated_at.desc())
    ).all()
    task_by_id = {task.id: task for task in tasks}
    dependencies = db.scalars(
        select(TaskDependency).where(TaskDependency.project_id == project_id)
    ).all()
    reviews = db.scalars(
        select(CodeReview).where(CodeReview.project_id == project_id).order_by(CodeReview.created_at.desc())
    ).all()
    test_runs = db.scalars(
        select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc())
    ).all()
    bugs = db.scalars(
        select(BugReport).where(BugReport.project_id == project_id, BugReport.status == "open")
    ).all()

    prerequisites: dict[str, list[str]] = {}
    for dependency in dependencies:
        prerequisites.setdefault(dependency.task_id, []).append(dependency.depends_on_task_id)

    latest_review: dict[str, CodeReview] = {}
    for review in reviews:
        latest_review.setdefault(review.task_id, review)
    latest_test: dict[str, TestRun] = {}
    for run in test_runs:
        latest_test.setdefault(run.task_id, run)
    open_bugs: dict[str, int] = {}
    for bug in bugs:
        open_bugs[bug.task_id] = open_bugs.get(bug.task_id, 0) + 1

    members = db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all()
    member_users = {member.user_id: db.get(User, member.user_id) for member in members}
    workload = {}
    for existing in tasks:
        if existing.assignee_id and existing.status not in {TaskStatus.merged, TaskStatus.cancelled, TaskStatus.passed}:
            workload[existing.assignee_id] = workload.get(existing.assignee_id, 0) + 1

    role_keywords = {
        ProjectRole.frontend_developer: ("frontend", "ui", "component", "react", "css", "browser", "page", "dashboard"),
        ProjectRole.ui_ux_designer: ("design", "ux", "ui", "wireframe", "accessibility", "layout"),
        ProjectRole.backend_developer: ("api", "backend", "database", "server", "endpoint", "model", "auth"),
        ProjectRole.tester_qa_engineer: ("test", "qa", "regression", "coverage", "validate", "quality"),
        ProjectRole.tester: ("test", "qa", "regression", "coverage", "validate"),
        ProjectRole.debugger: ("bug", "fix", "debug", "error", "crash", "failure"),
        ProjectRole.devops_engineer: ("deploy", "ci", "cd", "pipeline", "infra", "docker", "release"),
        ProjectRole.security_engineer: ("security", "vulnerability", "permission", "secret", "audit"),
        ProjectRole.documentation_specialist: ("docs", "documentation", "readme", "guide"),
    }

    def suggest_assignees(task):
        text = f"{task.title} {task.description}".lower()
        preferred = {
            role for role, keywords in role_keywords.items()
            if any(keyword in text for keyword in keywords)
        }
        candidates = []
        for member in members:
            candidate = member_users.get(member.user_id)
            if not candidate or not candidate.is_active:
                continue
            role_match = member.role in preferred if preferred else True
            candidates.append({
                "user_id": candidate.id,
                "display_name": candidate.display_name,
                "role": member.role.value,
                "role_match": role_match,
                "active_task_count": workload.get(candidate.id, 0),
            })
        candidates.sort(key=lambda item: (
            not item["role_match"], item["active_task_count"], item["display_name"].lower()
        ))
        return [
            {
                **candidate,
                "reason": (
                    "Role aligns with task keywords and current workload is considered."
                    if candidate["role_match"]
                    else "Suggested by current workload; role match is not established."
                ),
            }
            for candidate in candidates[:3]
        ]

    rows = []
    for task in tasks:
        blocked_by = []
        for prerequisite_id in prerequisites.get(task.id, []):
            prerequisite = task_by_id.get(prerequisite_id)
            if prerequisite and prerequisite.status not in _COMPLETE_PREREQUISITE:
                blocked_by.append({"task_id": prerequisite.id, "title": prerequisite.title, "status": prerequisite.status.value})

        review = latest_review.get(task.id)
        test_run = latest_test.get(task.id)
        gates = []
        if blocked_by:
            gates.append("prerequisites_incomplete")
        if task.status in _REVIEW_GATED and (not review or review.decision != "approved"):
            gates.append("approved_review_missing")
        if task.status in _TEST_GATED and (not test_run or test_run.result != "passed"):
            gates.append("passing_test_run_missing")
        if open_bugs.get(task.id, 0):
            gates.append("open_bugs")

        next_action = {
            TaskStatus.backlog: "Start coding",
            TaskStatus.in_progress: "Submit for review",
            TaskStatus.submitted: "Request code review",
            TaskStatus.in_review: "Record review decision",
            TaskStatus.approved: "Begin testing",
            TaskStatus.ready_for_testing: "Start testing",
            TaskStatus.testing: "Record test results",
            TaskStatus.failed: "Fix failures and retest",
            TaskStatus.passed: "Prepare merge",
            TaskStatus.ready_for_merge: "Merge through your Git workflow",
            TaskStatus.merged: "Complete",
            TaskStatus.cancelled: "No action — task cancelled",
        }.get(task.status, "Review task")
        rows.append({
            "task_id": task.id,
            "title": task.title,
            "status": task.status.value,
            "stage": _task_stage(task.status),
            "assignee_id": task.assignee_id,\n            "assignment_suggestions": suggest_assignees(task) if not task.assignee_id and task.status not in {TaskStatus.merged, TaskStatus.cancelled} else [],
            "prerequisites": blocked_by,
            "open_bug_count": open_bugs.get(task.id, 0),
            "latest_review": {"decision": review.decision, "summary": review.summary} if review else None,
            "latest_test_run": {"result": test_run.result, "passed": test_run.passed, "failed": test_run.failed, "total": test_run.total} if test_run else None,
            "gates": gates,
            "ready_for_next_step": not gates and task.status not in {TaskStatus.merged, TaskStatus.cancelled},
            "next_action": next_action,
        })

    counts = {}
    for row in rows:
        counts[row["stage"]] = counts.get(row["stage"], 0) + 1
    return {"project_id": project_id, "total_tasks": len(rows), "stage_counts": counts, "tasks": rows}
