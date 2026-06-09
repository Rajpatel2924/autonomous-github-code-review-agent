import hashlib
import hmac
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.config import get_settings
from app.service import review_pull_request

app = FastAPI(title="Autonomous GitHub Code Review Agent", version="0.1.0")


def valid_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    settings = get_settings()
    body = await request.body()
    if not valid_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload: dict[str, Any] = await request.json()
    if x_github_event != "pull_request" or payload.get("action") not in {
        "opened",
        "reopened",
        "synchronize",
    }:
        return {"status": "ignored"}

    repository = payload["repository"]
    background_tasks.add_task(
        review_pull_request,
        repository["owner"]["login"],
        repository["name"],
        payload["pull_request"]["number"],
        settings,
    )
    return {"status": "review_queued"}
