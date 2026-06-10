from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import Header, HTTPException, Request


SUPPORTED_PR_ACTIONS = {"opened", "reopened", "synchronize"}


def valid_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not secret:
        return True
    if not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def parse_github_webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str | None = Header(default=None),
    secret: str = "",
) -> tuple[str, dict[str, Any]]:
    body = await request.body()
    if not valid_signature(body, x_hub_signature_256, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    payload = await request.json()
    return x_github_event, payload


def is_supported_pull_request_event(event: str, payload: dict[str, Any]) -> bool:
    return event == "pull_request" and payload.get("action") in SUPPORTED_PR_ACTIONS
