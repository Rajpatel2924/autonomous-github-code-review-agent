import json
import re
from collections.abc import Iterable

import httpx

from app.models import Finding, PullRequestContext, ReviewReport, Severity
from app.prompts import SYSTEM_PROMPT


RULES = [
    (
        re.compile(r"""(?i)(api[_-]?key|secret|token|password)\s*=\s*["'][^"']{6,}["']"""),
        "security",
        Severity.high,
        "Possible hardcoded secret",
        "Move secrets to environment variables or a managed secret store.",
    ),
    (
        re.compile(r"(?i)\b(eval|exec)\s*\("),
        "security",
        Severity.high,
        "Dynamic code execution",
        "Avoid executing untrusted strings; use a constrained parser or explicit dispatch.",
    ),
    (
        re.compile(r"""(?i)(SELECT|INSERT|UPDATE|DELETE).*\{[^}]+\}"""),
        "security",
        Severity.high,
        "Possible SQL injection",
        "Use parameterized queries instead of interpolating values into SQL.",
    ),
    (
        re.compile(r"(?i)verify\s*=\s*False"),
        "security",
        Severity.medium,
        "TLS verification disabled",
        "Keep certificate verification enabled in production.",
    ),
    (
        re.compile(r"\bexcept\s*:\s*$"),
        "quality",
        Severity.medium,
        "Bare exception handler",
        "Catch the narrowest expected exception and handle it explicitly.",
    ),
    (
        re.compile(r"\b(TODO|FIXME)\b"),
        "quality",
        Severity.low,
        "Unresolved implementation note",
        "Resolve the note or link it to a tracked issue before merging.",
    ),
]

SCORE_PENALTY = {
    Severity.critical: 30,
    Severity.high: 15,
    Severity.medium: 7,
    Severity.low: 2,
}


def _added_lines(patch: str) -> Iterable[tuple[int | None, str]]:
    new_line: int | None = None
    for line in patch.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
        elif line.startswith("+") and not line.startswith("+++"):
            yield new_line, line[1:]
            if new_line is not None:
                new_line += 1
        elif not line.startswith("-") and new_line is not None:
            new_line += 1


def run_static_review(context: PullRequestContext) -> list[Finding]:
    findings: list[Finding] = []
    for changed_file in context.files:
        for line_number, line in _added_lines(changed_file.patch):
            for pattern, category, severity, title, suggestion in RULES:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            category=category,
                            severity=severity,
                            title=title,
                            description=f"Added code matches a risky pattern: `{line.strip()[:160]}`",
                            file=changed_file.filename,
                            line=line_number,
                            suggestion=suggestion,
                        )
                    )
    return findings


async def run_llm_review(
    context: PullRequestContext,
    api_key: str,
    base_url: str,
    model: str,
    max_patch_characters: int,
) -> list[Finding]:
    if not api_key:
        return []

    diff = "\n\n".join(
        f"FILE: {item.filename}\n{item.patch}" for item in context.files if item.patch
    )[:max_patch_characters]
    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"PR title: {context.title}\nPR body: {context.body}\n\n{diff}",
            },
        ],
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        response = await client.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    result = json.loads(content)
    return [Finding.model_validate(item) for item in result.get("findings", [])]


def build_report(findings: list[Finding]) -> ReviewReport:
    unique: dict[tuple[str, int | None, str], Finding] = {}
    for finding in findings:
        unique[(finding.file, finding.line, finding.title)] = finding
    deduplicated = list(unique.values())
    score = max(0, 100 - sum(SCORE_PENALTY[item.severity] for item in deduplicated))
    summary = (
        "No actionable issues found."
        if not deduplicated
        else f"Found {len(deduplicated)} actionable issue(s) across the pull request."
    )
    return ReviewReport(summary=summary, score=score, findings=deduplicated)


def render_markdown(report: ReviewReport) -> str:
    lines = [
        "## Autonomous Code Review",
        "",
        f"**Quality score:** {report.score}/100",
        "",
        report.summary,
    ]
    if not report.findings:
        lines.extend(["", "No security, performance, or quality issues were detected."])
        return "\n".join(lines)

    lines.extend(["", "| Severity | Category | Location | Finding |", "|---|---|---|---|"])
    for finding in report.findings:
        location = finding.file + (f":{finding.line}" if finding.line else "")
        lines.append(
            f"| {finding.severity.value.upper()} | {finding.category} | "
            f"`{location}` | **{finding.title}**: {finding.description} |"
        )
        if finding.suggestion:
            lines.extend(["", f"**Suggestion for `{location}`:** {finding.suggestion}"])
    return "\n".join(lines)
