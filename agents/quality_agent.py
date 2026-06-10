from __future__ import annotations

import re

from agents.base import ClaudeReviewAgent
from agents.security_agent import _added_lines
from app.models import AgentReview, PullRequestContext, ReviewCategory, ReviewFinding, Severity
from prompts.quality_prompt import QUALITY_PROMPT


class CodeQualityAgent(ClaudeReviewAgent):
    agent_name = "CodeQualityAgent"
    system_prompt = QUALITY_PROMPT

    def fallback_review(self, context: PullRequestContext) -> AgentReview:
        findings: list[ReviewFinding] = []
        patterns = [
            (re.compile(r"\bexcept\s*:\s*$"), "Bare exception handler", "Catch the narrowest expected exception and preserve error context."),
            (re.compile(r"\b(TODO|FIXME)\b"), "Unresolved implementation note", "Resolve this before merge or link to a tracked issue."),
            (re.compile(r"print\("), "Debug output committed", "Use structured logging with an appropriate level."),
        ]
        for changed_file in context.files:
            for line_number, line in _added_lines(changed_file.patch):
                for pattern, title, suggestion in patterns:
                    if pattern.search(line):
                        findings.append(
                            ReviewFinding(
                                category=ReviewCategory.quality,
                                severity=Severity.medium if "except" in line else Severity.low,
                                title=title,
                                description=f"Added code weakens maintainability: `{line.strip()[:160]}`",
                                file=changed_file.filename,
                                line=line_number,
                                suggested_fix=suggestion,
                            )
                        )
        summary = "No obvious code quality issues found." if not findings else f"Found {len(findings)} maintainability concern(s)."
        return AgentReview(agent=self.agent_name, summary=summary, findings=findings)
