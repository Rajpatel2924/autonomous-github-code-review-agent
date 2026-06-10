from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.github_client import GitHubClient
from app.models import PullRequestContext
from rag.retriever import CodeRetriever
from rag.vector_store import VectorStore


@dataclass(slots=True)
class MCPTools:
    settings: Settings

    async def get_pr_files(self, owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
        github = GitHubClient(self.settings)
        try:
            files = await github.get_pr_files(owner, repo, pull_number)
            return [file.model_dump(mode="json") for file in files]
        finally:
            await github.close()

    async def search_codebase(self, owner: str, repo: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        retriever = CodeRetriever(VectorStore(self.settings))
        contexts = retriever.vector_store.query(f"{owner}/{repo}", query, limit)
        return [context.model_dump() for context in contexts]

    async def get_repo_structure(self, owner: str, repo: str, ref: str | None = None) -> list[str]:
        github = GitHubClient(self.settings)
        try:
            return await github.get_repo_structure(owner, repo, ref)
        finally:
            await github.close()

    async def get_similar_files(self, owner: str, repo: str, path: str, limit: int = 5) -> list[dict[str, Any]]:
        return await self.search_codebase(owner, repo, f"Find files similar to {path}", limit)

    async def post_review_comment(self, owner: str, repo: str, pull_number: int, body: str) -> dict[str, str]:
        github = GitHubClient(self.settings)
        try:
            context = PullRequestContext(owner=owner, repo=repo, number=pull_number, title="", files=[])
            await github.post_review_comment(context, body)
            return {"status": "posted"}
        finally:
            await github.close()

    async def get_changed_lines(self, owner: str, repo: str, pull_number: int) -> dict[str, list[int]]:
        files = await self.get_pr_files(owner, repo, pull_number)
        return {file["filename"]: _changed_lines(file.get("patch", "")) for file in files}


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {"name": "get_pr_files", "description": "Fetch changed files for a pull request."},
        {"name": "search_codebase", "description": "Semantic search over the indexed repository."},
        {"name": "get_repo_structure", "description": "Fetch repository file tree."},
        {"name": "get_similar_files", "description": "Find code chunks similar to a path or file topic."},
        {"name": "post_review_comment", "description": "Post a markdown review comment to a pull request."},
        {"name": "get_changed_lines", "description": "Return changed added-line numbers keyed by file."},
    ]


def _changed_lines(patch: str) -> list[int]:
    lines: list[int] = []
    new_line: int | None = None
    for line in patch.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
        elif line.startswith("+") and not line.startswith("+++"):
            if new_line is not None:
                lines.append(new_line)
                new_line += 1
        elif not line.startswith("-") and new_line is not None:
            new_line += 1
    return lines
