import re
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member, record_activity
from app.models import User
from app.schemas import ConflictAnalyzeRequest
from app.permissions import require_permission
from app.realtime import manager

router = APIRouter(prefix="/projects/{project_id}/conflicts", tags=["conflict detection"])

_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_CONFLICT_PATTERN = re.compile(r"^CONFLICT .*? in (.+)$", re.MULTILINE)


def validate_git_ref(ref: str) -> str:
    """Reject option-like or malformed refs before passing them to Git."""
    if (
        not ref
        or not _REF_PATTERN.fullmatch(ref)
        or ".." in ref
        or "@{" in ref
        or "//" in ref
        or ref.endswith(("/", ".", ".lock"))
        or "\\" in ref
    ):
        raise ValueError("Invalid Git reference")
    return ref


def parse_merge_conflicts(output: str) -> list[str]:
    """Extract unique paths from git merge-tree conflict diagnostics."""
    paths = {match.strip() for match in _CONFLICT_PATTERN.findall(output) if match.strip()}
    return sorted(paths)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Git conflict analysis timed out") from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Git is unavailable on the backend host") from exc
    if check and result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "Git command failed")
    return result


def _resolve_commit(repo: Path, ref: str) -> str:
    try:
        safe_ref = validate_git_ref(ref)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = _git(repo, "rev-parse", "--verify", "--quiet", f"{safe_ref}^{{commit}}", check=False)
    if result.returncode != 0:
        raise HTTPException(status_code=422, detail=f"Git reference does not resolve to a commit: {safe_ref}")
    return result.stdout.strip()


def _changed_files(repo: Path, base: str, ref: str) -> list[str]:
    result = _git(repo, "diff", "--name-only", "--diff-filter=ACDMRT", f"{base}..{ref}")
    return sorted(path for path in result.stdout.splitlines() if path)


@router.post("/analyze")
async def analyze_conflicts(
    project_id: str,
    data: ConflictAnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Use Git's merge engine to detect real conflicts between two local refs."""
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "view")

    repository_path = data.repository_path.strip()
    target_ref = data.target_ref.strip()
    source_ref = data.source_ref.strip()
    if target_ref == source_ref:
        raise HTTPException(status_code=422, detail="Choose two different Git references")

    root = Path(settings.workspace_root).resolve()
    repo = (root / repository_path).resolve()
    if repo == root or root not in repo.parents:
        raise HTTPException(status_code=400, detail="Repository path must be inside WORKSPACE_ROOT")
    if not (repo / ".git").exists():
        raise HTTPException(status_code=400, detail="No Git repository found at the supplied path")

    target_sha = _resolve_commit(repo, target_ref)
    source_sha = _resolve_commit(repo, source_ref)
    merge_base_result = _git(repo, "merge-base", target_sha, source_sha, check=False)
    if merge_base_result.returncode != 0:
        raise HTTPException(status_code=409, detail="The selected branches have no common merge base")
    merge_base = merge_base_result.stdout.strip()

    target_changed = _changed_files(repo, merge_base, target_sha)
    source_changed = _changed_files(repo, merge_base, source_sha)
    overlapping_files = sorted(set(target_changed).intersection(source_changed))

    merge_result = _git(repo, "merge-tree", "--write-tree", target_sha, source_sha, check=False)
    if merge_result.returncode not in (0, 1):
        raise HTTPException(
            status_code=503,
            detail="Git merge-tree is unavailable or failed. Install Git 2.38 or newer on the backend host.",
        )
    conflicted_files = parse_merge_conflicts(merge_result.stdout + "\n" + merge_result.stderr)
    has_conflicts = merge_result.returncode == 1 or bool(conflicted_files)

    result = {
        "project_id": project_id,
        "repository_path": repository_path,
        "target_ref": target_ref,
        "source_ref": source_ref,
        "merge_base": merge_base,
        "mergeable": not has_conflicts,
        "conflict_count": len(conflicted_files),
        "conflicted_files": conflicted_files,
        "overlapping_files": overlapping_files,
        "target_changed_files": target_changed,
        "source_changed_files": source_changed,
        "analysis_engine": "git-merge-tree",
    }
    record_activity(
        db,
        project_id,
        user.id,
        "conflict.analysis_completed",
        {
            "target_ref": target_ref,
            "source_ref": source_ref,
            "mergeable": result["mergeable"],
            "conflict_count": result["conflict_count"],
        },
    )
    db.commit()
    await manager.broadcast(project_id, {"type": "conflict.analysis_completed", "data": result})
    return result
