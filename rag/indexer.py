from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.github_client import GitHubClient
from app.models import CodeChunk
from rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".rb",
    ".rs",
    ".php",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".sql",
}


def language_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
        ".rs": "rust",
        ".sql": "sql",
    }.get(suffix, suffix.removeprefix(".") or "text")


def chunk_code(repository: str, path: str, content: str, max_lines: int = 80, overlap: int = 12) -> list[CodeChunk]:
    lines = content.splitlines()
    chunks: list[CodeChunk] = []
    start = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        chunk_lines = lines[start:end]
        chunk_content = "\n".join(chunk_lines).strip()
        if chunk_content:
            digest = hashlib.sha256(f"{repository}:{path}:{start}:{chunk_content}".encode()).hexdigest()[:16]
            chunks.append(
                CodeChunk(
                    id=f"{path}:{start + 1}:{digest}",
                    repository=repository,
                    path=path,
                    language=language_for_path(path),
                    start_line=start + 1,
                    end_line=end,
                    content=chunk_content,
                )
            )
        if end == len(lines):
            break
        start = max(0, end - overlap)
    return chunks


class RepositoryIndexer:
    def __init__(self, github: GitHubClient, vector_store: VectorStore) -> None:
        self.github = github
        self.vector_store = vector_store

    async def index_repository(self, owner: str, repo: str, branch: str | None = None) -> int:
        metadata = await self.github.get_repository_metadata(owner, repo)
        ref = branch or metadata.default_branch
        paths = await self.github.get_repo_structure(owner, repo, ref)
        repository = f"{owner}/{repo}"
        chunks: list[CodeChunk] = []
        for path in paths:
            if not _is_indexable(path):
                continue
            try:
                content = await self.github.get_file_content(owner, repo, path, ref)
            except Exception as exc:  # pragma: no cover - network guard
                logger.warning("Skipping %s during indexing: %s", path, exc)
                continue
            chunks.extend(chunk_code(repository, path, content))
        return self.vector_store.upsert_chunks(repository, chunks)


def _is_indexable(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in TEXT_EXTENSIONS and not any(part.startswith(".") and part != ".github" for part in path.split("/"))
