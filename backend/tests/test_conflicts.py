import pytest

from app.api.conflicts import parse_merge_conflicts, validate_git_ref


def test_validate_git_ref_accepts_branch_and_commit_like_refs():
    assert validate_git_ref("feature/new-api") == "feature/new-api"
    assert validate_git_ref("main") == "main"


@pytest.mark.parametrize(
    "ref",
    ["", "-c", "../main", "feature//bad", "feature/name.lock", "main@{1}", "bad\\ref"],
)
def test_validate_git_ref_rejects_malformed_refs(ref):
    with pytest.raises(ValueError):
        validate_git_ref(ref)


def test_parse_merge_conflicts_extracts_unique_paths():
    output = (
        "abc123\n"
        "CONFLICT (content): Merge conflict in backend/app/main.py\n"
        "CONFLICT (modify/delete): Merge conflict in README.md\n"
        "CONFLICT (content): Merge conflict in backend/app/main.py\n"
    )
    assert parse_merge_conflicts(output) == ["README.md", "backend/app/main.py"]


def test_parse_merge_conflicts_returns_empty_for_clean_merge():
    assert parse_merge_conflicts("abc123\n") == []
