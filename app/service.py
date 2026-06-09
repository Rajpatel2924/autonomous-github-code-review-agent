import logging

import httpx

from app.config import Settings
from app.github_client import GitHubClient
from app.review_engine import (
    build_report,
    render_markdown,
    run_llm_review,
    run_static_review,
)

logger = logging.getLogger(__name__)


async def review_pull_request(
    owner: str, repo: str, number: int, settings: Settings
) -> None:
    github = GitHubClient(settings.github_token, settings.github_api_url)
    try:
        context = await github.get_pull_request(owner, repo, number)
        findings = run_static_review(context)
        try:
            findings.extend(
                await run_llm_review(
                    context,
                    settings.llm_api_key,
                    settings.llm_base_url,
                    settings.llm_model,
                    settings.max_patch_characters,
                )
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Continuing without LLM findings: %s", exc)
        report = build_report(findings)
        await github.post_review(context, render_markdown(report))
    finally:
        await github.close()
