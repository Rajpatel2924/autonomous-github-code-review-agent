from __future__ import annotations

import re

from agents.base import ClaudeReviewAgent
from app.models import AgentReview, PullRequestContext, ReviewCategory, ReviewFinding, Severity
from prompts.security_prompt import SECURITY_PROMPT


class SecurityAgent(ClaudeReviewAgent):
    agent_name = "SecurityAgent"
    system_prompt = SECURITY_PROMPT

    def fallback_review(self, context: PullRequestContext) -> AgentReview:
        findings: list[ReviewFinding] = []
        rules = [
            (re.compile(r"""(?i)(api[_-]?key|secret|token|password)\s*=\s*["'][^"']{6,}["']"""), "Possible hardcoded secret", "Move secrets to environment variables or a managed secret store."),
            (re.compile(r"(?i)\b(eval|exec)\s*\("), "Dynamic code execution", "Avoid evaluating strings; use explicit dispatch or a constrained parser."),
            (re.compile(r"""(?i)(SELECT|INSERT|UPDATE|DELETE).*\{[^}]+\}"""), "Possible SQL injection", "Use parameterized queries instead of string interpolation."),
            (re.compile(r"(?i)verify\s*=\s*False"), "TLS verification disabled", "Keep certificate verification enabled for outbound requests."),
        ]
        for changed_file in context.files:
            for line_number, line in _added_lines(changed_file.patch):
                for pattern, title, suggestion in rules:
                    if pattern.search(line):
                        findings.append(
                            ReviewFinding(
                                category=ReviewCategory.security,
                                severity=Severity.high,
                                title=title,
                                description=f"Added code matches a risky security pattern: `{line.strip()[:160]}`",
                                file=changed_file.filename,
                                line=line_number,
                                suggested_fix=suggestion,
                            )
                        )
        summary = "No obvious security issues found." if not findings else f"Found {len(findings)} security issue(s)."
        return AgentReview(agent=self.agent_name, summary=summary, findings=findings)


def _added_lines(patch: str) -> list[tuple[int | None, str]]:
    added: list[tuple[int | None, str]] = []
    new_line: int | None = None
    for line in patch.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
        elif line.startswith("+") and not line.startswith("+++"):
            added.append((new_line, line[1:]))
            if new_line is not None:
                new_line += 1
        elif not line.startswith("-") and new_line is not None:
            new_line += 1
    return added
