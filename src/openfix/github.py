"""Open a pull request for a verified fix. OpenFix never merges."""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

import httpx

from .gitutil import git

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")


class PublishError(RuntimeError):
    pass


def repo_slug(repo: Path) -> str:
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    url = git(repo, "remote", "get-url", "origin", check=False).strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not m:
        raise PublishError(f"Cannot determine the GitHub repository from origin '{url}'. Set GITHUB_REPOSITORY.")
    return m.group(1)


def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok:
        raise PublishError("Set GITHUB_TOKEN (contents:write, pull-requests:write) to open pull requests.")
    return tok


def _client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=API,
        timeout=60,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "openfix",
        },
    )


def default_branch(slug: str, token: str) -> str:
    if os.environ.get("GITHUB_BASE_REF"):
        return os.environ["GITHUB_BASE_REF"]
    with _client(token) as c:
        r = c.get(f"/repos/{slug}")
        r.raise_for_status()
        return r.json()["default_branch"]


def open_pull_request(
    work: Path,
    *,
    branch: str,
    title: str,
    body: str,
    commit_message: str,
    labels: list[str],
    draft: bool,
    base_branch: str | None = None,
) -> str:
    token = _token()
    slug = repo_slug(work)
    base_branch = base_branch or default_branch(slug, token)
    git(work, "switch", "-c", branch)
    git(work, "add", "-A")
    git(
        work,
        "-c",
        "user.name=openfix[bot]",
        "-c",
        "user.email=openfix-bot@users.noreply.github.com",
        "commit",
        "--no-verify",
        "-m",
        commit_message,
    )
    auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    git(
        work,
        "-c",
        f"http.https://github.com/.extraheader=AUTHORIZATION: basic {auth}",
        "push",
        "--force-with-lease",
        "origin",
        f"HEAD:refs/heads/{branch}",
    )
    with _client(token) as c:
        r = c.post(
            f"/repos/{slug}/pulls",
            json={
                "title": title,
                "head": branch,
                "base": base_branch,
                "body": body,
                "draft": draft,
                "maintainer_can_modify": True,
            },
        )
        if r.status_code == 422 and "already exists" in r.text:
            existing = c.get(f"/repos/{slug}/pulls", params={"head": f"{slug.split('/')[0]}:{branch}"}).json()
            if existing:
                return existing[0]["html_url"]
        if r.status_code >= 300:
            raise PublishError(f"GitHub refused the pull request ({r.status_code}): {r.text[:300]}")
        pr = r.json()
        if labels:
            c.post(f"/repos/{slug}/issues/{pr['number']}/labels", json={"labels": labels})
        return pr["html_url"]
