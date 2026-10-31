import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.github_security import decrypt_token, encrypt_token
from app.dependencies import get_current_user, get_project_member, record_activity
from app.models import GitEvent, GitHubAccount, Project, User
from app.permissions import require_permission
from app.realtime import manager

router = APIRouter(prefix="/github", tags=["GitHub integration"])
GITHUB_API = "https://api.github.com"
GITHUB_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

def require_oauth_config():
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.")
    if not settings.github_token_encryption_key:
        raise HTTPException(status_code=503, detail="GitHub token encryption is not configured. Set GITHUB_TOKEN_ENCRYPTION_KEY.")

def github_request(method: str, url: str, token: str, **kwargs):
    headers = {**GITHUB_HEADERS, "Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
    try:
        response = httpx.request(method, url, headers=headers, timeout=20, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not reach GitHub. Try again shortly.") from exc
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="GitHub authorization expired. Disconnect and connect your GitHub account again.")
    if response.status_code == 403:
        raise HTTPException(status_code=403, detail="GitHub denied this operation. Check the connected account's repository access and OAuth permissions.")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="GitHub repository or resource was not found or is not accessible to this account.")
    if not response.is_success:
        raise HTTPException(status_code=502, detail=f"GitHub API returned HTTP {response.status_code}.")
    return response

@router.get("/connect")
def connect(user: User = Depends(get_current_user)):
    require_oauth_config()
    state = jwt.encode({"sub": user.id, "purpose": "github_oauth", "nonce": secrets.token_urlsafe(16),
                        "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
                       settings.secret_key, algorithm="HS256")
    params = {"client_id": settings.github_client_id, "redirect_uri": settings.github_callback_url,
              "scope": "repo read:user", "state": state}
    return {"authorization_url": "https://github.com/login/oauth/authorize?" + urlencode(params)}

@router.get("/callback")
def callback(code: str = Query(min_length=1), state: str = Query(min_length=1),
             db: Session = Depends(get_db)):
    require_oauth_config()
    try:
        claims = jwt.decode(state, settings.secret_key, algorithms=["HS256"])
        if claims.get("purpose") != "github_oauth" or not claims.get("sub"):
            raise ValueError("Invalid OAuth state")
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="GitHub connection state is invalid or expired. Start the connection again.") from exc
    try:
        token_response = httpx.post("https://github.com/login/oauth/access_token",
            data={"client_id": settings.github_client_id, "client_secret": settings.github_client_secret,
                  "code": code, "redirect_uri": settings.github_callback_url},
            headers={"Accept": "application/json"}, timeout=20)
        token_response.raise_for_status()
        token_data = token_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="GitHub token exchange failed. Please retry.") from exc
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail=token_data.get("error_description", "GitHub did not return an access token."))
    profile = github_request("GET", GITHUB_API + "/user", access_token).json()
    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="DevSync account is no longer active.")
    account = db.scalar(select(GitHubAccount).where(GitHubAccount.user_id == user.id))
    values = {"github_user_id": str(profile["id"]), "login": profile["login"],
              "avatar_url": profile.get("avatar_url", ""), "access_token_encrypted": encrypt_token(access_token),
              "scopes": token_response.headers.get("X-OAuth-Scopes", "")}
    if account:
        for key, value in values.items(): setattr(account, key, value)
    else:
        account = GitHubAccount(user_id=user.id, **values)
        db.add(account)
    db.commit()
    return RedirectResponse(settings.frontend_url.rstrip("/") + "/?github=connected", status_code=303)

@router.get("/account")
def account_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account = db.scalar(select(GitHubAccount).where(GitHubAccount.user_id == user.id))
    if not account:
        return {"connected": False}
    return {"connected": True, "login": account.login, "avatar_url": account.avatar_url, "scopes": account.scopes}

@router.delete("/account", status_code=204)
def disconnect(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account = db.scalar(select(GitHubAccount).where(GitHubAccount.user_id == user.id))
    if account:
        db.delete(account)
        db.commit()

@router.get("/repositories")
def repositories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account = db.scalar(select(GitHubAccount).where(GitHubAccount.user_id == user.id))
    if not account:
        raise HTTPException(status_code=409, detail="Connect your GitHub account before selecting a repository.")
    token = decrypt_token(account.access_token_encrypted)
    response = github_request("GET", GITHUB_API + "/user/repos", token,
        params={"sort": "updated", "per_page": 100, "affiliation": "owner,collaborator,organization_member"})
    return [{"id": r["id"], "full_name": r["full_name"], "name": r["name"], "private": r["private"],
             "html_url": r["html_url"], "default_branch": r["default_branch"], "description": r.get("description") or ""}
            for r in response.json()]

@router.put("/projects/{project_id}/repository")
def attach_repository(project_id: str, data: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project, member = get_project_member(project_id, db, user)
    require_permission(member, "manage_team")
    full_name = str(data.get("full_name", "")).strip()
    if full_name.count("/") != 1 or any(not part or part in {".", ".."} for part in full_name.split("/")):
        raise HTTPException(status_code=422, detail="full_name must use owner/repository format.")
    account = db.scalar(select(GitHubAccount).where(GitHubAccount.user_id == user.id))
    if not account:
        raise HTTPException(status_code=409, detail="Connect your GitHub account before linking a repository.")
    token = decrypt_token(account.access_token_encrypted)
    repos = github_request("GET", GITHUB_API + "/user/repos", token,
        params={"sort": "updated", "per_page": 100, "affiliation": "owner,collaborator,organization_member"}).json()
    selected = next((r for r in repos if r["full_name"].lower() == full_name.lower()), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Repository is not accessible from the connected GitHub account.")
    project.github_repo_full_name = selected["full_name"]
    project.github_repo_url = selected["html_url"]
    project.github_default_branch = selected["default_branch"]
    record_activity(db, project_id, user.id, "github.repository_linked", {"repository": selected["full_name"]})
    db.commit()
    return {"project_id": project_id, "full_name": project.github_repo_full_name,
            "html_url": project.github_repo_url, "default_branch": project.github_default_branch}

@router.get("/projects/{project_id}/repository")
def project_repository(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project, _ = get_project_member(project_id, db, user)
    return {"connected": bool(project.github_repo_full_name), "full_name": project.github_repo_full_name,
            "html_url": project.github_repo_url, "default_branch": project.github_default_branch}

@router.post("/projects/{project_id}/sync")
async def sync_repository(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project, member = get_project_member(project_id, db, user)
    require_permission(member, "view")
    if not project.github_repo_full_name:
        raise HTTPException(status_code=409, detail="Link a GitHub repository to this project first.")
    account = db.scalar(select(GitHubAccount).where(GitHubAccount.user_id == user.id))
    if not account:
        raise HTTPException(status_code=409, detail="Connect your GitHub account to sync this repository.")
    token = decrypt_token(account.access_token_encrypted)
    owner, name = project.github_repo_full_name.split("/", 1)
    commits = github_request("GET", f"{GITHUB_API}/repos/{owner}/{name}/commits", token,
        params={"per_page": 30}).json()
    created = []
    for item in commits:
        commit = item["commit"]
        author = commit.get("author") or {}
        git_author = item.get("author") or {}
        commit_hash = item["sha"]
        if db.scalar(select(GitEvent).where(GitEvent.project_id == project_id, GitEvent.commit_hash == commit_hash)):
            continue
        event = GitEvent(project_id=project_id, actor_id=user.id,
            repository_path="github:" + project.github_repo_full_name,
            branch=project.github_default_branch or "unknown", commit_hash=commit_hash,
            author=git_author.get("login") or author.get("name") or "Unknown",
            author_email=author.get("email") or "", committed_at=author.get("date") or "",
            message=(commit.get("message") or "").splitlines()[0][:1000])
        db.add(event)
        created.append(event)
    record_activity(db, project_id, user.id, "github.repository_synced",
                    {"repository": project.github_repo_full_name, "new_commits": len(created)})
    db.commit()
    for event in created:
        db.refresh(event)
        await manager.broadcast(project_id, {"type": "git.commit", "data": {"id": event.id, "branch": event.branch,
            "commit_hash": event.commit_hash, "message": event.message, "author": event.author}})
    return {"repository": project.github_repo_full_name, "new_commits": len(created)}
