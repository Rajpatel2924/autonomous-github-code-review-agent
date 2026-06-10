from __future__ import annotations

import re
from functools import cached_property

from app.config import Settings
from app.models import CodeChunk, RetrievedContext
from rag.embeddings import EmbeddingModel


class VectorStore:
    def __init__(self, settings: Settings, embeddings: EmbeddingModel | None = None) -> None:
        self.settings = settings
        self.embeddings = embeddings or EmbeddingModel(settings.embedding_model)

    @cached_property
    def _client(self) -> object:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("Install chromadb to use the vector store.") from exc
        return chromadb.PersistentClient(path=self.settings.chroma_path)

    def _collection_name(self, repository: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]+", "_", repository).strip("_").lower()
        return f"{self.settings.collection_prefix}_{clean}"

    def upsert_chunks(self, repository: str, chunks: list[CodeChunk]) -> int:
        if not chunks:
            return 0
        collection = self._client.get_or_create_collection(self._collection_name(repository))
        embeddings = self.embeddings.embed([chunk.content for chunk in chunks])
        collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "repository": chunk.repository,
                    "path": chunk.path,
                    "language": chunk.language,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    **chunk.metadata,
                }
                for chunk in chunks
            ],
            embeddings=embeddings,
        )
        return len(chunks)

    def query(self, repository: str, query: str, limit: int) -> list[RetrievedContext]:
        collection = self._client.get_or_create_collection(self._collection_name(repository))
        query_embedding = self.embeddings.embed([query])[0]
        results = collection.query(query_embeddings=[query_embedding], n_results=limit)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        contexts: list[RetrievedContext] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            contexts.append(
                RetrievedContext(
                    path=str(metadata.get("path", "")),
                    content=document,
                    score=None if distance is None else 1 / (1 + float(distance)),
                    metadata=metadata,
                )
            )
        return contexts

    def list_repositories(self) -> list[str]:
        try:
            collections = self._client.list_collections()
        except RuntimeError:
            return []
        prefix = f"{self.settings.collection_prefix}_"
        return [collection.name.removeprefix(prefix) for collection in collections if collection.name.startswith(prefix)]
