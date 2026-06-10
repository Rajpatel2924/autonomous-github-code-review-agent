from __future__ import annotations

from collections import defaultdict

from app.models import AgentReview, ReviewCategory, ReviewFinding, ReviewReport, Severity


PENALTIES = {
    Severity.critical: 30,
    Severity.high: 15,
    Severity.medium: 7,
    Severity.low: 2,
}


class AggregatorAgent:
    def aggregate(self, reviews: list[AgentReview]) -> ReviewReport:
        unique: dict[tuple[str, int | None, str], ReviewFinding] = {}
        for review in reviews:
            for finding in review.findings:
                key = (finding.file, finding.line, finding.title)
                unique[key] = finding
        findings = list(unique.values())
        by_category: dict[ReviewCategory, list[ReviewFinding]] = defaultdict(list)
        for finding in findings:
            by_category[finding.category].append(finding)
        score = max(0, 100 - sum(PENALTIES[finding.severity] for finding in findings))
        executive = (
            "No actionable issues found. The pull request looks ready from the automated review perspective."
            if not findings
            else f"Found {len(findings)} actionable issue(s) across security, performance, and maintainability."
        )
        return ReviewReport(
            executive_summary=executive,
            security_summary=_summary_for(by_category[ReviewCategory.security], "security"),
            performance_summary=_summary_for(by_category[ReviewCategory.performance], "performance"),
            maintainability_summary=_summary_for(
                by_category[ReviewCategory.maintainability] + by_category[ReviewCategory.quality],
                "maintainability",
            ),
            suggested_fixes=[
                finding.suggested_fix
                for finding in findings
                if finding.suggested_fix
            ],
            score=score,
            findings=findings,
        )

    def render_markdown(self, report: ReviewReport) -> str:
        lines = [
            "# AI Review Report",
            "",
            f"Overall Score: {report.score}/100",
            "",
            "## Executive Summary",
            report.executive_summary,
            "",
            "## Security",
            report.security_summary,
            "",
            "## Performance",
            report.performance_summary,
            "",
            "## Code Quality",
            report.maintainability_summary,
        ]
        if report.findings:
            lines.extend(["", "## Findings", "", "| Severity | Category | Location | Finding |", "|---|---|---|---|"])
            for finding in report.findings:
                location = finding.file + (f":{finding.line}" if finding.line else "")
                lines.append(
                    f"| {finding.severity.value.upper()} | {finding.category.value} | "
                    f"`{location}` | **{finding.title}**: {finding.description} |"
                )
        lines.extend(["", "## Suggested Fixes"])
        if report.suggested_fixes:
            for fix in dict.fromkeys(report.suggested_fixes):
                lines.append(f"- {fix}")
        else:
            lines.append("- No automated fixes suggested.")
        patches = [finding.patch for finding in report.findings if finding.patch]
        for patch in patches:
            lines.extend(["", "```diff", patch.strip(), "```"])
        return "\n".join(lines)


def _summary_for(findings: list[ReviewFinding], label: str) -> str:
    if not findings:
        return f"No {label} issues found."
    highest = min(findings, key=lambda item: list(PENALTIES).index(item.severity)).severity.value
    return f"Found {len(findings)} {label} issue(s). Highest severity: {highest}."
