from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import Settings
from app.models import PullRequestContext, PullRequestFile, RepositoryRef

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self._client = httpx.AsyncClient(
            base_url=settings.github_api_url,
            headers=headers,
            timeout=settings.request_timeout_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = await self._client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json() if response.content else None
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == 3:
                    break
                await asyncio.sleep(0.5 * attempt)
        raise RuntimeError(f"GitHub request failed: {method} {url}") from last_error

    async def get_repository_metadata(self, owner: str, repo: str) -> RepositoryRef:
        data = await self._request("GET", f"/repos/{owner}/{repo}")
        return RepositoryRef(
            owner=owner,
            name=repo,
            full_name=data["full_name"],
            clone_url=data.get("clone_url"),
            default_branch=data.get("default_branch") or "main",
        )

    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequestContext:
        pr = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")
        files = await self.get_pr_files(owner, repo, number)
        repository = await self.get_repository_metadata(owner, repo)
        structure = await self.get_repo_structure(owner, repo, pr["head"]["sha"])
        return PullRequestContext(
            owner=owner,
            repo=repo,
            number=number,
            title=pr["title"],
            body=pr.get("body") or "",
            base_sha=pr["base"]["sha"],
            head_sha=pr["head"]["sha"],
            author=pr.get("user", {}).get("login", ""),
            files=files,
            repository=repository,
            metadata={"url": pr.get("html_url"), "state": pr.get("state")},
            structure=structure,
        )

    async def get_pr_files(self, owner: str, repo: str, number: int) -> list[PullRequestFile]:
        files: list[PullRequestFile] = []
        page = 1
        while True:
            batch = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            files.extend(PullRequestFile.model_validate(item) for item in batch)
            if len(batch) < 100:
                break
            page += 1
        return files

    async def get_repo_structure(
        self, owner: str, repo: str, ref: str | None = None, max_items: int = 500
    ) -> list[str]:
        params = {"recursive": "1"}
        if ref:
            params["ref"] = ref
        tree = await self._request("GET", f"/repos/{owner}/{repo}/git/trees/{ref or 'HEAD'}", params=params)
        paths = [
            item["path"]
            for item in tree.get("tree", [])
            if item.get("type") == "blob" and not _is_ignored_path(item.get("path", ""))
        ]
        return paths[:max_items]

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str | None = None) -> str:
        headers = {"Accept": "application/vnd.github.raw"}
        params = {"ref": ref} if ref else None
        response = await self._client.get(f"/repos/{owner}/{repo}/contents/{path}", params=params, headers=headers)
        response.raise_for_status()
        return response.text

    async def post_review_comment(self, context: PullRequestContext, body: str) -> None:
        await self._request(
            "POST",
            f"/repos/{context.owner}/{context.repo}/issues/{context.number}/comments",
            json={"body": body},
        )


def _is_ignored_path(path: str) -> bool:
    ignored_parts = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", ".chroma"}
    return any(part in ignored_parts for part in path.split("/"))
