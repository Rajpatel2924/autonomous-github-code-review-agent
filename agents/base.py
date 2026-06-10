from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import Settings
from app.models import AgentReview, PullRequestContext, RetrievedContext, ReviewFinding

logger = logging.getLogger(__name__)


class ClaudeReviewAgent(ABC):
    agent_name: str
    system_prompt: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def review(
        self, context: PullRequestContext, retrieved_context: list[RetrievedContext]
    ) -> AgentReview:
        if not self.settings.anthropic_api_key:
            return self.fallback_review(context)
        try:
            payload = self._build_user_prompt(context, retrieved_context)
            raw = await self._call_claude(payload)
            return self._parse_review(raw)
        except Exception as exc:  # pragma: no cover - defensive production fallback
            logger.warning("%s failed, using fallback review: %s", self.agent_name, exc)
            return self.fallback_review(context)

    async def _call_claude(self, user_prompt: str) -> str:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise RuntimeError("Install anthropic to run Claude reviews.") from exc
        client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        message = await client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=self.settings.anthropic_max_tokens,
            temperature=self.settings.anthropic_temperature,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "\n".join(block.text for block in message.content if getattr(block, "type", "") == "text")

    def _build_user_prompt(
        self, context: PullRequestContext, retrieved_context: list[RetrievedContext]
    ) -> str:
        diff = "\n\n".join(
            f"FILE: {changed_file.filename}\n{changed_file.patch}"
            for changed_file in context.files
            if changed_file.patch
        )[: self.settings.max_patch_characters]
        rag = "\n\n".join(
            f"CONTEXT FILE: {item.path}\n{item.content}" for item in retrieved_context
        )
        return (
            f"Repository: {context.owner}/{context.repo}\n"
            f"PR #{context.number}: {context.title}\n"
            f"Description:\n{context.body}\n\n"
            f"Repository structure sample:\n{chr(10).join(context.structure[:200])}\n\n"
            f"Relevant retrieved context:\n{rag}\n\n"
            f"Pull request diff:\n{diff}\n\n"
            "Return strict JSON with keys: agent, summary, findings. Findings must include "
            "category, severity, title, description, file, line, suggested_fix, patch, confidence."
        )

    def _parse_review(self, raw: str) -> AgentReview:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data: dict[str, Any] = json.loads(clean)
        data.setdefault("agent", self.agent_name)
        data.setdefault("findings", [])
        return AgentReview.model_validate(data)

    @abstractmethod
    def fallback_review(self, context: PullRequestContext) -> AgentReview:
        raise NotImplementedError


def finding_from_dict(data: dict[str, Any]) -> ReviewFinding:
    return ReviewFinding.model_validate(data)
