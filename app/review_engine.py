from __future__ import annotations

from agents.aggregator_agent import AggregatorAgent
from agents.security_agent import SecurityAgent
from app.config import get_settings
from app.models import AgentReview, PullRequestContext, ReviewFinding, ReviewReport


def run_static_review(context: PullRequestContext) -> list[ReviewFinding]:
    return SecurityAgent(get_settings()).fallback_review(context).findings


def build_report(findings: list[ReviewFinding]) -> ReviewReport:
    return AggregatorAgent().aggregate([AgentReview(agent="StaticReview", summary="", findings=findings)])


def render_markdown(report: ReviewReport) -> str:
    return AggregatorAgent().render_markdown(report)
