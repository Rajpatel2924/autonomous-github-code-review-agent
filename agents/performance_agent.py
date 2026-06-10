from __future__ import annotations

import re

from agents.base import ClaudeReviewAgent
from agents.security_agent import _added_lines
from app.models import AgentReview, PullRequestContext, ReviewCategory, ReviewFinding, Severity
from prompts.performance_prompt import PERFORMANCE_PROMPT


class PerformanceAgent(ClaudeReviewAgent):
    agent_name = "PerformanceAgent"
    system_prompt = PERFORMANCE_PROMPT

    def fallback_review(self, context: PullRequestContext) -> AgentReview:
        findings: list[ReviewFinding] = []
        patterns = [
            (re.compile(r"\bfor\b.*:\s*$"), "Review loop complexity", "Confirm this loop is bounded or replace repeated work with batching/caching."),
            (re.compile(r"requests\.(get|post|put|delete)\("), "Blocking HTTP call", "Use an async HTTP client inside async request paths."),
            (re.compile(r"\.all\(\)"), "Potential unbounded query", "Add pagination, limits, or filtering before loading all records."),
        ]
        for changed_file in context.files:
            for line_number, line in _added_lines(changed_file.patch):
                for pattern, title, suggestion in patterns:
                    if pattern.search(line):
                        findings.append(
                            ReviewFinding(
                                category=ReviewCategory.performance,
                                severity=Severity.low,
                                title=title,
                                description=f"Added code may introduce avoidable performance cost: `{line.strip()[:160]}`",
                                file=changed_file.filename,
                                line=line_number,
                                suggested_fix=suggestion,
                                confidence=0.45,
                            )
                        )
        summary = "No obvious performance issues found." if not findings else f"Found {len(findings)} performance concern(s)."
        return AgentReview(agent=self.agent_name, summary=summary, findings=findings)
