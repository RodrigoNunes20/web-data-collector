"""Collector for the public GitHub REST API (list a user's public repositories)."""
from __future__ import annotations

from typing import Any, Callable, Optional

API_URL = "https://api.github.com/users/{user}/repos"
COLUMNS = ["name", "description", "language", "stars", "forks", "open_issues", "updated_at", "is_fork", "url"]


def to_row(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": repo.get("name", ""),
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "stars": int(repo.get("stargazers_count") or 0),
        "forks": int(repo.get("forks_count") or 0),
        "open_issues": int(repo.get("open_issues_count") or 0),
        "updated_at": (repo.get("updated_at") or "")[:10],
        "is_fork": bool(repo.get("fork")),
        "url": repo.get("html_url", ""),
    }


def fetch_repos(
    get_json: Callable[..., Any],
    user: str,
    include_forks: bool = True,
    per_page: int = 100,
    max_pages: int = 10,
) -> list[dict[str, Any]]:
    """Download every public repo of `user` (paginated) and return flat rows sorted by stars."""
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = get_json(API_URL.format(user=user), params={"per_page": per_page, "page": page, "sort": "updated"})
        if not isinstance(data, list):
            raise ValueError("Unexpected response from the GitHub API")
        rows.extend(to_row(repo) for repo in data)
        if len(data) < per_page:
            break
    if not include_forks:
        rows = [row for row in rows if not row["is_fork"]]
    return sorted(rows, key=lambda r: (-r["stars"], r["name"].lower()))
