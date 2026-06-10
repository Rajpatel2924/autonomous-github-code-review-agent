from __future__ import annotations

from typing import TypedDict

from app.models import AgentReview, PullRequestContext, RetrievedContext, ReviewReport


class ReviewState(TypedDict, total=False):
    owner: str
    repo: str
    pull_number: int
    pr_context: PullRequestContext
    retrieved_context: list[RetrievedContext]
    security_review: AgentReview
    performance_review: AgentReview
    quality_review: AgentReview
    report: ReviewReport
    markdown: str
    posted: bool
