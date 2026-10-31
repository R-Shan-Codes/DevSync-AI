import json
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member
from app.models import ActivityEvent, CodeReview, DevelopmentEvent, FileChange, GitEvent, ProjectMember, Task, TaskStatus, TestRun, User
from app.schemas import AIAssistRequest
from app.permissions import normalize_role

router = APIRouter(prefix="/ai", tags=["AI assistance"])
ROLE_GUIDANCE = {
 "team_leader_project_manager":"Act as a technical project manager. Prioritize delivery, clarify scope, dependencies and risks.",
 "ui_ux_designer":"Act as a senior UI/UX designer. Improve user flows, accessibility, information architecture and visual consistency.",
 "frontend_developer":"Act as a senior frontend engineer. Build accessible, maintainable interfaces and explain implementation tradeoffs.",
 "backend_developer":"Act as a senior backend engineer. Design reliable APIs, data models and maintainable services.",
 "tester_qa_engineer":"Act as a senior QA engineer. Design test cases, edge cases, regression coverage and failure diagnosis.",
 "devops_engineer":"Act as a DevOps engineer. Improve CI/CD, deployments, observability and infrastructure reliability.",
 "security_engineer":"Act as an application security engineer. Identify threats and recommend practical mitigations.",
 "documentation_specialist":"Act as a technical writer. Produce accurate developer documentation and usage guidance.",
 "coder":"Act as a senior software engineer.","debugger":"Act as a senior debugging engineer.","tester":"Act as a senior QA engineer."
}

@router.post("/assist")
async def assist(data: AIAssistRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project, member = get_project_member(data.project_id, db, user)
    if data.role != normalize_role(member.role):
        raise HTTPException(status_code=403, detail="You can only use the assistant for your assigned project role")
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="AI is not configured. Add GEMINI_API_KEY to backend/.env and restart the API.")
    tasks = db.scalars(select(Task).where(Task.project_id == project.id).order_by(Task.updated_at.desc()).limit(20)).all()
    activity = db.scalars(select(ActivityEvent).where(ActivityEvent.project_id == project.id).order_by(ActivityEvent.created_at.desc()).limit(15)).all()
    commits = db.scalars(select(GitEvent).where(GitEvent.project_id == project.id).order_by(GitEvent.created_at.desc()).limit(10)).all()
    context = {
      "project": {"name": project.name, "description": project.description},
      "tasks": [{"title": t.title, "status": t.status.value, "description": t.description} for t in tasks],
      "recent_activity": [{"type": a.event_type, "payload": json.loads(a.payload)} for a in activity],
      "recent_commits": [{"branch": c.branch, "message": c.message, "hash": c.commit_hash[:10]} for c in commits]
    }
    prompt = f"{ROLE_GUIDANCE[data.role]}\nYou are DevSync AI, assisting project member role {data.role}. Use the project context only as evidence; do not invent repository details. If context is insufficient, say what is missing.\nPROJECT CONTEXT:\n{json.dumps(context, ensure_ascii=False)}\nUSER REQUEST:\n{data.prompt}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(url, params={"key": settings.gemini_api_key}, json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.3,"maxOutputTokens":2048}})
        response.raise_for_status()
        payload = response.json()
        answer = payload["candidates"][0]["content"]["parts"][0]["text"]
        return {"response": answer, "role": data.role, "model": settings.gemini_model}
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini API returned HTTP {exc.response.status_code}") from exc
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Unable to obtain a valid response from Gemini") from exc

@router.get("/insights/{project_id}")
def insights(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    tasks = db.scalars(select(Task).where(Task.project_id == project_id)).all()
    commits = db.scalars(select(GitEvent).where(GitEvent.project_id == project_id)).all()
    activity = db.scalars(select(ActivityEvent).where(ActivityEvent.project_id == project_id)).all()
    development_events = db.scalars(select(DevelopmentEvent).where(DevelopmentEvent.project_id == project_id)).all()
    file_changes = db.scalars(select(FileChange).where(FileChange.project_id == project_id)).all()
    reviews = db.scalars(select(CodeReview).where(CodeReview.project_id == project_id)).all()
    test_runs = db.scalars(select(TestRun).where(TestRun.project_id == project_id)).all()
    members = db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all()
    users = {member.user_id: db.get(User, member.user_id) for member in members}
    by_email = {u.email.lower(): u for u in users.values() if u}

    by_contributor = {}
    def contributor(key, display_name):
        item = by_contributor.setdefault(key, {
            "user_id": key if key in users else None,
            "author": display_name,
            "commits": 0,
            "active_branches": set(),
            "development_events": 0,
            "files_touched": 0,
            "tasks_assigned": 0,
            "tasks_completed": 0,
            "reviews_submitted": 0,
            "test_runs": 0,
            "tests_passed": 0,
            "tests_failed": 0,
        })
        return item

    for commit in commits:
        member_user = by_email.get((commit.author_email or "").lower())
        key = member_user.id if member_user else (commit.author_email or commit.author)
        item = contributor(key, member_user.display_name if member_user else commit.author)
        item["commits"] += 1
        item["active_branches"].add(commit.branch)

    for event in development_events:
        member_user = users.get(event.actor_id)
        if member_user:
            contributor(member_user.id, member_user.display_name)["development_events"] += 1
    for change in file_changes:
        member_user = users.get(change.actor_id)
        if member_user:
            contributor(member_user.id, member_user.display_name)["files_touched"] += 1
    for task in tasks:
        member_user = users.get(task.assignee_id) if task.assignee_id else None
        if member_user:
            item = contributor(member_user.id, member_user.display_name)
            item["tasks_assigned"] += 1
            if task.status in {TaskStatus.passed, TaskStatus.merged}:
                item["tasks_completed"] += 1
    for review in reviews:
        member_user = users.get(review.reviewer_id)
        if member_user:
            contributor(member_user.id, member_user.display_name)["reviews_submitted"] += 1
    for run in test_runs:
        member_user = users.get(run.tester_id)
        if member_user:
            item = contributor(member_user.id, member_user.display_name)
            item["test_runs"] += 1
            item["tests_passed"] += run.passed
            item["tests_failed"] += run.failed

    contributors = []
    for item in by_contributor.values():
        item["active_branches"] = len(item["active_branches"])
        contributors.append(item)
    contributors.sort(
        key=lambda item: (
            item["tasks_completed"], item["reviews_submitted"],
            item["test_runs"], item["commits"], item["development_events"],
        ),
        reverse=True,
    )
    by_status = {status.value: sum(t.status == status for t in tasks) for status in TaskStatus}
    return {
        "task_counts": by_status,
        "total_tasks": len(tasks),
        "completed_tasks": by_status["merged"] + by_status["passed"],
        "git_commits": len(commits),
        "activity_events": len(activity),
        "contributors": contributors,
        "contribution_methodology": "Counts observable project work: assigned task completion, reviews, recorded test runs, Git commits, development events and tracked file-change metadata. It is not a quality score or an individual performance ranking.",
    }
