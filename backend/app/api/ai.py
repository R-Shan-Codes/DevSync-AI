import json
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member
from app.models import ActivityEvent, GitEvent, Task, TaskStatus, User
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
    by_status = {status.value: sum(t.status == status for t in tasks) for status in TaskStatus}
    by_contributor = {}
    for commit in commits:
        key = commit.author_email or commit.author
        item = by_contributor.setdefault(key, {"author": commit.author, "commits": 0, "branches": set()})
        item["commits"] += 1
        item["branches"].add(commit.branch)
    contributors = [{"author": x["author"], "commits": x["commits"], "active_branches": len(x["branches"])} for x in by_contributor.values()]
    contributors.sort(key=lambda x: x["commits"], reverse=True)
    return {"task_counts": by_status, "total_tasks": len(tasks), "completed_tasks": by_status["merged"] + by_status["passed"], "git_commits": len(commits), "activity_events": len(activity), "contributors": contributors}
