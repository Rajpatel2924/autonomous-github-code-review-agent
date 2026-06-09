from typing import Any

import httpx

from app.models import PullRequestContext, PullRequestFile


class GitHubClient:
    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        self._client = httpx.AsyncClient(
            base_url=api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_pull_request(
        self, owner: str, repo: str, number: int
    ) -> PullRequestContext:
        pr_response = await self._client.get(f"/repos/{owner}/{repo}/pulls/{number}")
        pr_response.raise_for_status()
        pr: dict[str, Any] = pr_response.json()

        files: list[PullRequestFile] = []
        page = 1
        while True:
            response = await self._client.get(
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            response.raise_for_status()
            batch = response.json()
            files.extend(PullRequestFile.model_validate(item) for item in batch)
            if len(batch) < 100:
                break
            page += 1

        return PullRequestContext(
            owner=owner,
            repo=repo,
            number=number,
            title=pr["title"],
            body=pr.get("body") or "",
            files=files,
        )

    async def post_review(self, context: PullRequestContext, body: str) -> None:
        response = await self._client.post(
            f"/repos/{context.owner}/{context.repo}/issues/{context.number}/comments",
            json={"body": body},
        )
        response.raise_for_status()
