from __future__ import annotations

from app.models import PullRequestContext, RetrievedContext
from rag.vector_store import VectorStore


class CodeRetriever:
    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store

    def retrieve_for_pr(self, context: PullRequestContext, limit: int) -> list[RetrievedContext]:
        query_parts = [context.title, context.body]
        query_parts.extend(f"{file.filename}\n{file.patch}" for file in context.files if file.patch)
        query = "\n\n".join(part for part in query_parts if part)
        return self.vector_store.query(f"{context.owner}/{context.repo}", query[:20_000], limit)
