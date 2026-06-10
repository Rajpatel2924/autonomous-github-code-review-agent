from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.config import Settings, get_settings
from app.github_client import GitHubClient
from app.models import ReindexRequest, ReviewRequest, StatusResponse
from app.webhook import is_supported_pull_request_event, parse_github_webhook, valid_signature
from graph.workflow import ReviewWorkflow
from rag.indexer import RepositoryIndexer
from rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger.info("Starting %s", settings.app_name)
    yield


app = FastAPI(
    title="Autonomous GitHub Code Review Agent",
    version=get_settings().app_version,
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    settings = get_settings()
    repositories = VectorStore(settings).list_repositories()
    return StatusResponse(status="ok", indexed_repositories=repositories, version=settings.app_version)


@app.post("/webhook", status_code=202)
@app.post("/webhook/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    settings = get_settings()
    event, payload = await parse_github_webhook(
        request,
        x_github_event=x_github_event,
        x_hub_signature_256=x_hub_signature_256,
        secret=settings.github_webhook_secret,
    )
    if not is_supported_pull_request_event(event, payload):
        return {"status": "ignored"}
    repository = payload["repository"]
    pull_request = payload["pull_request"]
    background_tasks.add_task(
        review_pull_request,
        repository["owner"]["login"],
        repository["name"],
        int(pull_request["number"]),
        settings,
    )
    return {"status": "review_queued"}


@app.post("/review", status_code=202)
async def review(request: ReviewRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    settings = get_settings()
    background_tasks.add_task(review_pull_request, request.owner, request.repo, request.pull_number, settings)
    return {"status": "review_queued"}


@app.post("/reindex")
async def reindex(request: ReindexRequest) -> dict[str, Any]:
    settings = get_settings()
    github = GitHubClient(settings)
    try:
        count = await RepositoryIndexer(github, VectorStore(settings)).index_repository(
            request.owner, request.repo, request.branch
        )
        return {"status": "indexed", "chunks": count}
    finally:
        await github.close()


async def review_pull_request(owner: str, repo: str, pull_number: int, settings: Settings) -> None:
    workflow = ReviewWorkflow(settings)
    try:
        await workflow.run(owner, repo, pull_number)
    except Exception as exc:  # pragma: no cover - background task logging
        logger.exception("Review workflow failed for %s/%s#%s: %s", owner, repo, pull_number, exc)
    finally:
        await workflow.close()


def extract_pr_from_payload(payload: dict[str, Any]) -> tuple[str, str, int]:
    try:
        repository = payload["repository"]
        pull_request = payload["pull_request"]
        return repository["owner"]["login"], repository["name"], int(pull_request["number"])
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="Invalid pull_request webhook payload") from exc
